from __future__ import annotations

from datetime import datetime, timedelta

from django.db.models import Exists, OuterRef, Q
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsTenantWorkspaceStaff
from apps.jobs.models import Job, JobStatus
from apps.service_requests.models import ServiceRequest, ServiceRequestStatus
from apps.technicians.inbox_models import (
    TechnicianInboxMessage,
    TechnicianInboxMessageReceipt,
    TechnicianInboxThread,
)
from apps.technicians.models import (
    ApplicationStatus,
    TechnicianApplication,
)


def _combine_booking_datetime(date_value, time_value):
    if not date_value:
        return None
    raw = datetime.combine(date_value, time_value or datetime.min.time())
    if timezone.is_naive(raw):
        return timezone.make_aware(raw, timezone.get_current_timezone())
    return raw


def _job_context(job: Job) -> dict:
    booking = job.booking
    assigned = job.assigned_to
    return {
        "job_id": str(job.id),
        "title": job.title,
        "status": job.status,
        "scheduled_date": booking.scheduled_date if booking else None,
        "scheduled_start_time": (
            booking.scheduled_start_time.isoformat()
            if booking and booking.scheduled_start_time
            else None
        ),
        "scheduled_end_time": (
            booking.scheduled_end_time.isoformat()
            if booking and booking.scheduled_end_time
            else None
        ),
        "technician": (
            {
                "id": str(assigned.id),
                "name": assigned.full_name,
            }
            if assigned
            else None
        ),
        "location": {
            "address": (booking.address if booking else "") or "",
        },
        "service_request_id": (
            str(job.service_request_id) if job.service_request_id else None
        ),
        "updated_at": job.updated_at,
    }


class OperatorDashboardView(APIView):
    """
    Single high-signal operational payload for operator dashboards.
    """

    permission_classes = [IsAuthenticated, IsTenantWorkspaceStaff]

    def get(self, request):
        tenant_id = getattr(request.user, "tenant_id", None)
        if not tenant_id:
            return Response(
                {
                    "snapshot": {},
                    "today_action_data": {},
                    "attention_items": [],
                    "cross_system_summary": {},
                    "quick_actions": {},
                }
            )

        now = timezone.now()
        today = now.date()
        limit = max(1, min(int(request.query_params.get("limit", 7)), 20))

        soon_hours = max(
            1, min(int(request.query_params.get("soon_hours", 4)), 24)
        )
        soon_cutoff = now + timedelta(hours=soon_hours)
        stale_unassigned_hours = max(
            1, min(int(request.query_params.get("stale_unassigned_hours", 4)), 72)
        )
        stalled_hours = max(
            1, min(int(request.query_params.get("stalled_hours", 2)), 72)
        )

        jobs_qs = Job.objects.filter(tenant_id=tenant_id).select_related(
            "booking", "assigned_to"
        )

        open_unassigned_q = Q(status=JobStatus.OPEN, assigned_to__isnull=True)
        assigned_q = Q(status=JobStatus.ASSIGNED)
        in_progress_q = Q(status=JobStatus.IN_PROGRESS)
        active_q = Q(status__in=[JobStatus.OPEN, JobStatus.ASSIGNED, JobStatus.IN_PROGRESS])

        overdue_q = (
            active_q
            & Q(booking__isnull=False)
            & Q(booking__scheduled_date__lt=today)
        )
        at_risk_q = (
            active_q
            & Q(booking__isnull=False)
            & Q(booking__scheduled_date=today)
            & Q(booking__scheduled_start_time__isnull=False)
            & Q(booking__scheduled_start_time__lte=soon_cutoff.time())
        )
        overdue_or_risk_q = overdue_q | at_risk_q

        snapshot = {
            "open_jobs_unassigned": {
                "count": jobs_qs.filter(open_unassigned_q).count(),
                "job_filter": {"status": JobStatus.OPEN, "assigned_to__isnull": True},
            },
            "assigned_jobs": {
                "count": jobs_qs.filter(assigned_q).count(),
                "job_filter": {"status": JobStatus.ASSIGNED},
            },
            "in_progress_jobs": {
                "count": jobs_qs.filter(in_progress_q).count(),
                "job_filter": {"status": JobStatus.IN_PROGRESS},
            },
            "overdue_or_at_risk_jobs": {
                "count": jobs_qs.filter(overdue_or_risk_q).distinct().count(),
                "job_filter": {
                    "status__in": [JobStatus.OPEN, JobStatus.ASSIGNED, JobStatus.IN_PROGRESS],
                    "schedule_state": "overdue_or_starting_soon",
                    "soon_hours": soon_hours,
                },
            },
            "completed_today": {
                "count": jobs_qs.filter(
                    status=JobStatus.COMPLETED, updated_at__date=today
                ).count(),
                "job_filter": {"status": JobStatus.COMPLETED, "updated_at__date": str(today)},
            },
        }

        assign_soon_jobs = (
            jobs_qs.filter(
                open_unassigned_q,
                booking__isnull=False,
                booking__scheduled_date__gte=today,
                booking__scheduled_date__lte=today + timedelta(days=2),
            )
            .order_by("booking__scheduled_date", "booking__scheduled_start_time", "created_at")[
                :limit
            ]
        )
        in_progress_jobs = jobs_qs.filter(in_progress_q).order_by("updated_at", "created_at")[
            :limit
        ]
        recently_completed = jobs_qs.filter(status=JobStatus.COMPLETED).order_by(
            "-updated_at"
        )[:limit]

        today_action_data = {
            "jobs_needing_assignment_soon": {
                "items": [_job_context(job) for job in assign_soon_jobs],
                "sort": "scheduled_date_asc_then_start_time_asc",
            },
            "jobs_currently_in_progress": {
                "items": [_job_context(job) for job in in_progress_jobs],
                "sort": "oldest_status_update_first",
            },
            "recently_completed_jobs": {
                "items": [_job_context(job) for job in recently_completed],
                "sort": "recently_completed_first",
            },
        }

        attention_items: list[dict] = []

        stale_unassigned_jobs = jobs_qs.filter(
            open_unassigned_q,
            created_at__lt=now - timedelta(hours=stale_unassigned_hours),
        ).order_by("created_at")[: limit * 2]
        for job in stale_unassigned_jobs:
            attention_items.append(
                {
                    "type": "unassigned_stale",
                    "severity": "high",
                    "reference": {"job_id": str(job.id)},
                    "message": f"Job '{job.title}' has been unassigned for over {stale_unassigned_hours}h.",
                    "action": {"type": "assign_technician", "job_id": str(job.id)},
                }
            )

        soon_unassigned_jobs = jobs_qs.filter(
            open_unassigned_q,
            booking__isnull=False,
            booking__scheduled_date=today,
            booking__scheduled_start_time__isnull=False,
            booking__scheduled_start_time__lte=soon_cutoff.time(),
        ).order_by("booking__scheduled_start_time")[: limit * 2]
        for job in soon_unassigned_jobs:
            attention_items.append(
                {
                    "type": "starting_soon_without_technician",
                    "severity": "critical",
                    "reference": {"job_id": str(job.id)},
                    "message": f"Job '{job.title}' starts soon but has no technician assigned.",
                    "action": {"type": "assign_technician", "job_id": str(job.id)},
                }
            )

        missing_data_jobs = jobs_qs.filter(
            active_q, booking__isnull=False
        ).filter(
            Q(booking__address__exact="")
            | Q(booking__client_phone__exact="")
            | Q(booking__client_name__exact="")
        )[: limit * 2]
        for job in missing_data_jobs:
            attention_items.append(
                {
                    "type": "missing_required_job_data",
                    "severity": "medium",
                    "reference": {"job_id": str(job.id)},
                    "message": f"Job '{job.title}' is missing customer contact or location data.",
                    "action": {"type": "update_job_or_booking_data", "job_id": str(job.id)},
                }
            )

        stalled_jobs = jobs_qs.filter(
            status=JobStatus.IN_PROGRESS,
            updated_at__lt=now - timedelta(hours=stalled_hours),
        ).order_by("updated_at")[: limit * 2]
        for job in stalled_jobs:
            attention_items.append(
                {
                    "type": "stalled_job",
                    "severity": "high",
                    "reference": {"job_id": str(job.id)},
                    "message": f"Job '{job.title}' appears stalled (no updates for {stalled_hours}h).",
                    "action": {"type": "follow_up_with_technician", "job_id": str(job.id)},
                }
            )

        blocked_transition_jobs = jobs_qs.filter(
            Q(status=JobStatus.ASSIGNED, assigned_to__isnull=True)
            | Q(status=JobStatus.IN_PROGRESS, assigned_to__isnull=True)
        )[: limit * 2]
        for job in blocked_transition_jobs:
            attention_items.append(
                {
                    "type": "blocked_transition",
                    "severity": "critical",
                    "reference": {"job_id": str(job.id)},
                    "message": f"Job '{job.title}' has an invalid assignment state for its current status.",
                    "action": {"type": "repair_job_assignment_state", "job_id": str(job.id)},
                }
            )

        attention_items = attention_items[: max(limit * 3, 10)]

        receipt_exists = TechnicianInboxMessageReceipt.objects.filter(
            message_id=OuterRef("pk"),
            reader=request.user,
        )
        unread_msg_exists = (
            TechnicianInboxMessage.objects.filter(thread_id=OuterRef("pk"))
            .exclude(sender_user=request.user)
            .annotate(has_receipt=Exists(receipt_exists))
            .filter(has_receipt=False)
        )
        unread_thread_count = TechnicianInboxThread.objects.filter(
            tenant_id=tenant_id
        ).filter(
            Exists(unread_msg_exists)
        ).count()

        cross_system_summary = {
            "new_service_requests": {
                "count": ServiceRequest.objects.filter(
                    tenant_id=tenant_id, status=ServiceRequestStatus.NEW
                ).count(),
                "filter": {"status": ServiceRequestStatus.NEW},
            },
            "pending_price_reviews": {
                "count": ServiceRequest.objects.filter(
                    tenant_id=tenant_id, status=ServiceRequestStatus.REVIEWING
                ).count(),
                "filter": {"status": ServiceRequestStatus.REVIEWING},
            },
            "technician_applications_pending": {
                "count": TechnicianApplication.objects.filter(
                    tenant_id=tenant_id,
                    status__in=[ApplicationStatus.NEW, ApplicationStatus.REVIEWING],
                ).count(),
                "filter": {"status__in": [ApplicationStatus.NEW, ApplicationStatus.REVIEWING]},
            },
            "unread_inbox_threads": {
                "count": unread_thread_count,
                "filter": {"has_unread": True},
            },
        }

        quick_actions = {
            "create_service_request": {"method": "POST", "path": "/api/v1/service-requests/"},
            "create_job": {"method": "POST", "path": "/api/v1/jobs/"},
            "assign_technician": {"method": "PATCH", "path": "/api/v1/jobs/{job_id}/"},
            "approve_technician": {
                "method": "POST",
                "path": "/api/v1/admin/technician-applications/{application_id}/approve/",
            },
            "trigger_pricing": {
                "method": "POST",
                "path": "/api/v1/service-requests/{service_request_id}/price/",
            },
        }

        return Response(
            {
                "generated_at": now,
                "snapshot": snapshot,
                "today_action_data": today_action_data,
                "attention_items": attention_items,
                "cross_system_summary": cross_system_summary,
                "quick_actions": quick_actions,
            }
        )
