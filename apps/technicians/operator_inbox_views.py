"""
Operator (workspace) inbox — same ``TechnicianInbox*`` tables, scoped by
``operator_contact`` (or full tenant for staff/superuser).
"""

import logging

from django.contrib.auth import get_user_model
from django.db.models import Exists, Max, OuterRef, Q, Value
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.technicians.inbox_helpers import (
    annotate_last_messages_read_for_reader,
    inbox_unread_subquery_for_reader,
    last_message_ids_needing_receipt,
)
from apps.technicians.inbox_models import (
    TechnicianInboxMessage,
    TechnicianInboxMessageReceipt,
    TechnicianInboxThread,
    TechnicianInboxSenderType,
    TechnicianInboxThreadType,
)
from apps.technicians.inbox_serializers import (
    OperatorInboxStartThreadSerializer,
    OperatorInboxThreadSerializer,
    TechnicianInboxMessageSerializer,
    TechnicianInboxSendSerializer,
    TechnicianInboxThreadPinSerializer,
    TechnicianRecipientSerializer,
)
from apps.technicians.operator_inbox_permissions import IsOperatorInboxUser
from apps.users.models import UserRole

logger = logging.getLogger(__name__)
User = get_user_model()


def _operator_thread_queryset(request):
    tenant_id = getattr(request.user, "tenant_id", None)
    if not tenant_id:
        return TechnicianInboxThread.objects.none()
    u = request.user
    qs = TechnicianInboxThread.objects.filter(tenant_id=tenant_id)
    if getattr(u, "is_staff", False) or getattr(u, "is_superuser", False):
        return qs
    return qs.filter(operator_contact=u)


def _get_operator_thread(request, thread_id):
    return (
        _operator_thread_queryset(request)
        .filter(id=thread_id)
        .select_related("job", "technician")
        .first()
    )


class OperatorInboxThreadListView(APIView):
    """
    GET /api/v1/operator/inbox/threads/
    """

    permission_classes = [IsAuthenticated, IsOperatorInboxUser]

    def get(self, request):
        tenant_id = getattr(request.user, "tenant_id", None)
        if not tenant_id:
            return Response([])

        reader = request.user
        unread_sq = inbox_unread_subquery_for_reader(reader)

        qs = (
            _operator_thread_queryset(request)
            .select_related("job", "technician")
            .annotate(_unread_count=Coalesce(unread_sq, Value(0)))
            .order_by("-is_pinned", "-last_activity_at")
        )

        threads = list(qs)
        thread_ids = [t.id for t in threads]

        if thread_ids:
            newest_per_thread = (
                TechnicianInboxMessage.objects.filter(
                    thread_id__in=thread_ids,
                )
                .values("thread_id")
                .annotate(max_created=Max("created_at"))
            )
            max_dates = {
                row["thread_id"]: row["max_created"] for row in newest_per_thread
            }

            if max_dates:
                q_filter = Q()
                for tid, max_dt in max_dates.items():
                    q_filter |= Q(thread_id=tid, created_at=max_dt)

                last_messages = list(
                    TechnicianInboxMessage.objects.filter(q_filter).select_related(
                        "job"
                    )
                )
                msg_by_thread: dict = {}
                for msg in last_messages:
                    existing = msg_by_thread.get(msg.thread_id)
                    if existing is None or msg.pk > existing.pk:
                        msg_by_thread[msg.thread_id] = msg
            else:
                msg_by_thread = {}

            for thread in threads:
                thread._prefetched_last_message = msg_by_thread.get(thread.id)

            last_msgs = [
                m
                for m in (
                    getattr(t, "_prefetched_last_message", None) for t in threads
                )
                if m is not None
            ]
            ids_needing_receipt = last_message_ids_needing_receipt(
                last_msgs, reader
            )
            receipt_msg_ids = set(
                TechnicianInboxMessageReceipt.objects.filter(
                    message_id__in=ids_needing_receipt,
                    reader=reader,
                ).values_list("message_id", flat=True)
            )
            annotate_last_messages_read_for_reader(
                last_msgs, reader, receipt_msg_ids
            )
        else:
            for thread in threads:
                thread._prefetched_last_message = None

        serializer = OperatorInboxThreadSerializer(
            threads, many=True, context={"request": request}
        )
        return Response(serializer.data)


class OperatorInboxThreadDetailView(APIView):
    permission_classes = [IsAuthenticated, IsOperatorInboxUser]

    def patch(self, request, thread_id):
        thread = _get_operator_thread(request, thread_id)
        if not thread:
            return Response(
                {"detail": "Thread not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = TechnicianInboxThreadPinSerializer(
            thread, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        reader = request.user
        unread_sq = inbox_unread_subquery_for_reader(reader)
        thread = (
            TechnicianInboxThread.objects.filter(pk=thread.pk)
            .select_related("job", "technician")
            .annotate(_unread_count=Coalesce(unread_sq, Value(0)))
            .first()
        )

        last_msg = (
            TechnicianInboxMessage.objects.filter(thread=thread)
            .select_related("job")
            .order_by("-created_at")
            .first()
        )
        thread._prefetched_last_message = last_msg
        if last_msg:
            if last_msg.sender_user_id == reader.id:
                last_msg._is_read = True
            else:
                last_msg._is_read = TechnicianInboxMessageReceipt.objects.filter(
                    message=last_msg, reader=reader
                ).exists()

        out = OperatorInboxThreadSerializer(
            thread, context={"request": request}
        )
        return Response(out.data)


class OperatorInboxMessageListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsOperatorInboxUser]

    def get(self, request, thread_id):
        thread = _get_operator_thread(request, thread_id)
        if not thread:
            return Response(
                {"detail": "Thread not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        reader = request.user

        receipt_exists = TechnicianInboxMessageReceipt.objects.filter(
            message_id=OuterRef("pk"),
            reader=reader,
        )

        qs = (
            TechnicianInboxMessage.objects.filter(thread=thread)
            .select_related("job")
            .annotate(
                _has_receipt=Exists(receipt_exists),
            )
            .order_by("created_at")
        )

        messages = list(qs)
        for msg in messages:
            if msg.sender_user_id == reader.id:
                msg._is_read = True
            else:
                msg._is_read = bool(getattr(msg, "_has_receipt", False))

        serializer = TechnicianInboxMessageSerializer(
            messages, many=True, context={"request": request}
        )
        return Response(serializer.data)

    def post(self, request, thread_id):
        thread = _get_operator_thread(request, thread_id)
        if not thread:
            return Response(
                {"detail": "Thread not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if thread.thread_type == TechnicianInboxThreadType.SYSTEM_ALERT:
            return Response(
                {"detail": "Replies not supported for system threads."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = TechnicianInboxSendSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        body = serializer.validated_data["body"]
        op = request.user

        first = getattr(op, "first_name", "") or ""
        last = getattr(op, "last_name", "") or ""
        sender_name = f"{first} {last}".strip() or op.email or "Operator"

        msg = TechnicianInboxMessage.objects.create(
            tenant_id=thread.tenant_id,
            thread=thread,
            sender_type=TechnicianInboxSenderType.OPERATOR,
            sender_user=op,
            sender_name=sender_name,
            body=body,
            job=thread.job,
        )

        thread.last_activity_at = msg.created_at
        thread.save(update_fields=["last_activity_at", "updated_at"])

        logger.info(
            "Operator %s sent message %s in thread %s",
            op.id,
            msg.id,
            thread.id,
        )

        msg._is_read = True
        out = TechnicianInboxMessageSerializer(
            msg, context={"request": request}
        )
        return Response(out.data, status=status.HTTP_201_CREATED)


class OperatorInboxMarkReadView(APIView):
    permission_classes = [IsAuthenticated, IsOperatorInboxUser]

    def post(self, request, thread_id):
        tenant_id = getattr(request.user, "tenant_id", None)
        if not tenant_id:
            return Response(
                {"detail": "Thread not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        reader = request.user
        thread = _get_operator_thread(request, thread_id)
        if not thread:
            return Response(
                {"detail": "Thread not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        unread_msgs = (
            TechnicianInboxMessage.objects.filter(thread=thread)
            .exclude(sender_user=reader)
            .exclude(read_receipts__reader=reader)
        )

        receipts_to_create = [
            TechnicianInboxMessageReceipt(
                tenant_id=tenant_id,
                message=msg,
                reader=reader,
            )
            for msg in unread_msgs
        ]

        if receipts_to_create:
            TechnicianInboxMessageReceipt.objects.bulk_create(
                receipts_to_create,
                ignore_conflicts=True,
            )
            logger.info(
                "Marked %d messages as read for operator %s in thread %s",
                len(receipts_to_create),
                reader.id,
                thread_id,
            )

        return Response(status=status.HTTP_204_NO_CONTENT)


class OperatorInboxTechnicianRecipientsView(APIView):
    """
    GET /api/v1/operator/inbox/technicians/

    Technicians on the tenant; each row notes whether an ``operator_direct``
    thread exists for this operator + technician pair.
    """

    permission_classes = [IsAuthenticated, IsOperatorInboxUser]

    def get(self, request):
        tenant_id = getattr(request.user, "tenant_id", None)
        if not tenant_id:
            return Response([])

        op = request.user

        technicians = (
            User.objects.filter(
                tenant_id=tenant_id,
                is_active=True,
                role=UserRole.TECHNICIAN,
            )
            .exclude(id=op.id)
            .order_by("first_name", "last_name", "email")
        )

        existing_threads = dict(
            TechnicianInboxThread.objects.filter(
                tenant_id=tenant_id,
                operator_contact=op,
                thread_type=TechnicianInboxThreadType.OPERATOR_DIRECT,
                technician_id__isnull=False,
            ).values_list("technician_id", "id")
        )

        results = []
        for tech in technicians:
            tech.has_existing_thread = tech.id in existing_threads
            tech.existing_thread_id = existing_threads.get(tech.id)
            results.append(tech)

        serializer = TechnicianRecipientSerializer(results, many=True)
        return Response(serializer.data)


class OperatorInboxStartThreadView(APIView):
    """
    POST /api/v1/operator/inbox/threads/start/

    Creates or reuses one ``operator_direct`` thread per operator ↔ technician
    pair and appends the given message (sender = operator).
    """

    permission_classes = [IsAuthenticated, IsOperatorInboxUser]

    def post(self, request):
        tenant_id = getattr(request.user, "tenant_id", None)
        if not tenant_id:
            return Response(
                {"detail": "Tenant not found."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = OperatorInboxStartThreadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        technician_id = serializer.validated_data["technician_id"]
        body = serializer.validated_data["body"]
        op = request.user

        try:
            technician_user = User.objects.get(
                id=technician_id,
                tenant_id=tenant_id,
                is_active=True,
                role=UserRole.TECHNICIAN,
            )
        except User.DoesNotExist:
            return Response(
                {"detail": "Technician not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        op_first = getattr(op, "first_name", "") or ""
        op_last = getattr(op, "last_name", "") or ""
        op_name = f"{op_first} {op_last}".strip() or op.email

        op_sender_name = op_name or "You"

        existing_thread = TechnicianInboxThread.objects.filter(
            tenant_id=tenant_id,
            technician=technician_user,
            operator_contact=op,
            thread_type=TechnicianInboxThreadType.OPERATOR_DIRECT,
        ).first()

        now = timezone.now()
        created = False

        if existing_thread:
            thread = existing_thread
        else:
            thread = TechnicianInboxThread.objects.create(
                tenant_id=tenant_id,
                technician=technician_user,
                thread_type=TechnicianInboxThreadType.OPERATOR_DIRECT,
                title=op_name,
                subtitle="Operator",
                participant_name=op_name,
                participant_avatar_url=getattr(op, "avatar_url", None),
                operator_contact=op,
                last_activity_at=now,
            )
            created = True
            logger.info(
                "Operator %s started thread %s with technician %s",
                op.id,
                thread.id,
                technician_user.id,
            )

        msg = TechnicianInboxMessage.objects.create(
            tenant_id=tenant_id,
            thread=thread,
            sender_type=TechnicianInboxSenderType.OPERATOR,
            sender_user=op,
            sender_name=op_sender_name,
            body=body,
        )

        thread.last_activity_at = msg.created_at
        thread.save(update_fields=["last_activity_at", "updated_at"])

        unread_sq = inbox_unread_subquery_for_reader(op)
        thread = (
            TechnicianInboxThread.objects.filter(pk=thread.pk)
            .select_related("job", "technician")
            .annotate(_unread_count=Coalesce(unread_sq, Value(0)))
            .first()
        )
        msg = (
            TechnicianInboxMessage.objects.filter(pk=msg.pk)
            .select_related("job")
            .first()
        )
        msg._is_read = True
        thread._prefetched_last_message = msg

        out = OperatorInboxThreadSerializer(
            thread, context={"request": request}
        )
        resp_status = (
            status.HTTP_201_CREATED if created else status.HTTP_200_OK
        )
        return Response(out.data, status=resp_status)
