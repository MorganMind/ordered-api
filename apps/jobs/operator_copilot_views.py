from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsTenantWorkspaceStaff
from apps.events.models import EntityType, EventType
from apps.events.services import record_event
from apps.jobs.models import Job, JobStatus
from apps.pricing.services import create_price_snapshot_from_service_request
from apps.service_requests.models import ServiceRequest, ServiceRequestStatus
from apps.technicians.models import (
    ApplicationStatus,
    TechnicianApplication,
)
from apps.users.models import UserRole

User = get_user_model()


class OperatorCopilotChatView(APIView):
    """
    Operator-facing copilot endpoint with explicit read/write tool calls.

    Expected body:
    {
      "message": "what is at risk today?",
      "include_context": true,
      "dry_run": false,
      "tools": [
        {"type": "get_risk_summary"},
        {"type": "assign_technician", "input": {"job_id": "...", "technician_id": "..."}}
      ]
    }
    """

    permission_classes = [IsAuthenticated, IsTenantWorkspaceStaff]

    def post(self, request):
        tenant_id = getattr(request.user, "tenant_id", None)
        if not tenant_id:
            return Response(
                {"detail": "Tenant context is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        body = request.data if isinstance(request.data, dict) else {}
        message = (body.get("message") or "").strip()
        include_context = bool(body.get("include_context", True))
        dry_run = bool(body.get("dry_run", False))
        tools = body.get("tools") or []
        if not isinstance(tools, list):
            return Response(
                {"detail": "Field 'tools' must be a list."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        context = self._build_context(tenant_id) if include_context else {}
        tool_results = []
        for tool_call in tools:
            result = self._run_tool_call(
                tool_call=tool_call,
                tenant_id=tenant_id,
                actor=request.user,
                request=request,
                dry_run=dry_run,
            )
            tool_results.append(result)

        assistant_message = self._build_assistant_message(
            message=message,
            context=context,
            tool_results=tool_results,
        )

        return Response(
            {
                "assistant": {
                    "message": assistant_message,
                    "message_type": "operational",
                },
                "context": context,
                "tool_results": tool_results,
                "meta": {
                    "dry_run": dry_run,
                    "tenant_id": str(tenant_id),
                    "generated_at": timezone.now(),
                },
            }
        )

    def _build_context(self, tenant_id):
        now = timezone.now()
        today = now.date()
        soon_cutoff = now + timedelta(hours=4)

        jobs = Job.objects.filter(tenant_id=tenant_id)
        active_q = Job.objects.filter(
            tenant_id=tenant_id,
            status__in=[JobStatus.OPEN, JobStatus.ASSIGNED, JobStatus.IN_PROGRESS],
        )
        at_risk_count = active_q.filter(
            booking__isnull=False,
            booking__scheduled_date=today,
            booking__scheduled_start_time__isnull=False,
            booking__scheduled_start_time__lte=soon_cutoff.time(),
        ).count()

        return {
            "snapshot": {
                "open_unassigned": jobs.filter(
                    status=JobStatus.OPEN, assigned_to__isnull=True
                ).count(),
                "assigned": jobs.filter(status=JobStatus.ASSIGNED).count(),
                "in_progress": jobs.filter(status=JobStatus.IN_PROGRESS).count(),
                "completed_today": jobs.filter(
                    status=JobStatus.COMPLETED, updated_at__date=today
                ).count(),
                "at_risk_today": at_risk_count,
            },
            "service_requests": {
                "new": ServiceRequest.objects.filter(
                    tenant_id=tenant_id, status=ServiceRequestStatus.NEW
                ).count(),
                "reviewing": ServiceRequest.objects.filter(
                    tenant_id=tenant_id, status=ServiceRequestStatus.REVIEWING
                ).count(),
                "priced": ServiceRequest.objects.filter(
                    tenant_id=tenant_id, status=ServiceRequestStatus.PRICED
                ).count(),
            },
            "technician_applications": {
                "new": TechnicianApplication.objects.filter(
                    tenant_id=tenant_id, status=ApplicationStatus.NEW
                ).count(),
                "reviewing": TechnicianApplication.objects.filter(
                    tenant_id=tenant_id, status=ApplicationStatus.REVIEWING
                ).count(),
            },
        }

    def _run_tool_call(self, tool_call, tenant_id, actor, request, dry_run):
        if not isinstance(tool_call, dict):
            return {"ok": False, "error": "Invalid tool call payload."}
        tool_type = tool_call.get("type")
        payload = tool_call.get("input") or {}

        if tool_type == "get_risk_summary":
            return {"ok": True, "type": tool_type, "data": self._build_context(tenant_id)}
        if tool_type == "assign_technician":
            return self._assign_technician(payload, tenant_id, actor, request, dry_run)
        if tool_type == "trigger_pricing":
            return self._trigger_pricing(payload, tenant_id, actor, request, dry_run)
        if tool_type == "approve_technician_application":
            return self._approve_application(payload, tenant_id, actor, request, dry_run)

        return {
            "ok": False,
            "type": tool_type,
            "error": "Unknown tool. Allowed: get_risk_summary, assign_technician, trigger_pricing, approve_technician_application.",
        }

    def _assign_technician(self, payload, tenant_id, actor, request, dry_run):
        job_id = payload.get("job_id")
        technician_id = payload.get("technician_id")
        if not job_id or not technician_id:
            return {
                "ok": False,
                "type": "assign_technician",
                "error": "job_id and technician_id are required.",
            }

        try:
            job = Job.objects.get(id=job_id, tenant_id=tenant_id)
        except Job.DoesNotExist:
            return {"ok": False, "type": "assign_technician", "error": "Job not found."}

        try:
            tech = User.objects.get(id=technician_id, tenant_id=tenant_id)
        except User.DoesNotExist:
            return {
                "ok": False,
                "type": "assign_technician",
                "error": "Technician user not found.",
            }

        if getattr(tech, "role", None) != UserRole.TECHNICIAN:
            return {
                "ok": False,
                "type": "assign_technician",
                "error": "Target user is not a technician.",
            }

        if dry_run:
            return {
                "ok": True,
                "type": "assign_technician",
                "dry_run": True,
                "data": {"job_id": str(job.id), "technician_id": str(tech.id)},
            }

        job.assigned_to = tech
        if job.status == JobStatus.OPEN:
            job.status = JobStatus.ASSIGNED
        job.save(update_fields=["assigned_to", "status", "updated_at"])

        record_event(
            tenant_id=tenant_id,
            actor=actor,
            event_type=EventType.JOB_ASSIGNED,
            entity_type=EntityType.JOB,
            entity_id=job.id,
            payload={"action": "copilot_assign_technician", "technician_id": str(tech.id)},
            request=request,
        )
        return {
            "ok": True,
            "type": "assign_technician",
            "data": {"job_id": str(job.id), "status": job.status, "technician_id": str(tech.id)},
        }

    def _trigger_pricing(self, payload, tenant_id, actor, request, dry_run):
        sr_id = payload.get("service_request_id")
        if not sr_id:
            return {
                "ok": False,
                "type": "trigger_pricing",
                "error": "service_request_id is required.",
            }
        try:
            sr = ServiceRequest.objects.get(id=sr_id, tenant_id=tenant_id)
        except ServiceRequest.DoesNotExist:
            return {"ok": False, "type": "trigger_pricing", "error": "Service request not found."}

        if sr.status not in [ServiceRequestStatus.NEW, ServiceRequestStatus.REVIEWING]:
            return {
                "ok": False,
                "type": "trigger_pricing",
                "error": f"Service request must be new/reviewing. Current: {sr.status}.",
            }

        if dry_run:
            return {
                "ok": True,
                "type": "trigger_pricing",
                "dry_run": True,
                "data": {"service_request_id": str(sr.id), "next_status": ServiceRequestStatus.PRICED},
            }

        with transaction.atomic():
            snap = create_price_snapshot_from_service_request(sr)
            sr.status = ServiceRequestStatus.PRICED
            sr.save(update_fields=["status", "updated_at"])

        record_event(
            tenant_id=tenant_id,
            actor=actor,
            event_type=EventType.SERVICE_REQUEST_PRICED,
            entity_type=EntityType.SERVICE_REQUEST,
            entity_id=sr.id,
            payload={"action": "copilot_trigger_pricing", "price_snapshot_id": str(snap.id)},
            request=request,
        )
        return {
            "ok": True,
            "type": "trigger_pricing",
            "data": {
                "service_request_id": str(sr.id),
                "price_snapshot_id": str(snap.id),
                "status": sr.status,
            },
        }

    def _approve_application(self, payload, tenant_id, actor, request, dry_run):
        application_id = payload.get("application_id")
        reviewer_notes = (payload.get("reviewer_notes") or "").strip()
        if not application_id:
            return {
                "ok": False,
                "type": "approve_technician_application",
                "error": "application_id is required.",
            }
        try:
            app = TechnicianApplication.objects.get(id=application_id, tenant_id=tenant_id)
        except TechnicianApplication.DoesNotExist:
            return {
                "ok": False,
                "type": "approve_technician_application",
                "error": "Technician application not found.",
            }

        if app.status in [ApplicationStatus.APPROVED, ApplicationStatus.REJECTED, ApplicationStatus.WITHDRAWN]:
            return {
                "ok": False,
                "type": "approve_technician_application",
                "error": f"Application is already terminal: {app.status}.",
            }

        if dry_run:
            return {
                "ok": True,
                "type": "approve_technician_application",
                "dry_run": True,
                "data": {"application_id": str(app.id), "next_status": ApplicationStatus.APPROVED},
            }

        app.status = ApplicationStatus.APPROVED
        app.status_changed_at = timezone.now()
        app.reviewed_by = actor
        app.reviewed_at = timezone.now()
        if reviewer_notes:
            app.reviewer_notes = (
                f"{app.reviewer_notes}\n{reviewer_notes}" if app.reviewer_notes else reviewer_notes
            )
        app.save(
            update_fields=[
                "status",
                "status_changed_at",
                "reviewed_by",
                "reviewed_at",
                "reviewer_notes",
                "updated_at",
            ]
        )

        record_event(
            tenant_id=tenant_id,
            actor=actor,
            event_type=EventType.TECHNICIAN_APPLICATION_APPROVED,
            entity_type=EntityType.TECHNICIAN_APPLICATION,
            entity_id=app.id,
            payload={"action": "copilot_approve_application"},
            request=request,
        )
        return {
            "ok": True,
            "type": "approve_technician_application",
            "data": {"application_id": str(app.id), "status": app.status},
        }

    def _build_assistant_message(self, message, context, tool_results):
        if tool_results:
            success_count = sum(1 for r in tool_results if r.get("ok"))
            fail_count = len(tool_results) - success_count
            return (
                f"Processed {len(tool_results)} tool call(s): "
                f"{success_count} succeeded, {fail_count} failed. "
                "Use tool_results for details."
            )

        snapshot = context.get("snapshot", {})
        if "risk" in message.lower() or "at risk" in message.lower():
            return (
                f"Current at-risk jobs: {snapshot.get('at_risk_today', 0)}. "
                f"In progress: {snapshot.get('in_progress', 0)}, "
                f"open unassigned: {snapshot.get('open_unassigned', 0)}."
            )
        return (
            "Operational context ready. Provide tools[] calls for controlled actions "
            "or ask focused operational questions."
        )
