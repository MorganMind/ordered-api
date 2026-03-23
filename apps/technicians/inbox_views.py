import logging

from django.contrib.auth import get_user_model
from django.db.models import Exists, Max, OuterRef, Q, Value
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsTechnician
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
    OperatorRecipientSerializer,
    TechnicianInboxMessageSerializer,
    TechnicianInboxSendSerializer,
    TechnicianInboxStartThreadSerializer,
    TechnicianInboxThreadPinSerializer,
    TechnicianInboxThreadSerializer,
)
from apps.users.models import UserRole

logger = logging.getLogger(__name__)

User = get_user_model()

# Staff roles that may receive technician direct messages. JWT / Supabase may use
# ``"operator"`` while Django rows often use ``UserRole.ADMIN``.
MESSAGABLE_STAFF_ROLES = [UserRole.ADMIN, "operator"]


class TechnicianInboxThreadListView(APIView):
    """
    GET /api/v1/technicians/me/inbox/threads/
    """

    permission_classes = [IsAuthenticated, IsTechnician]

    def get(self, request):
        tenant_id = getattr(request.user, "tenant_id", None)
        if not tenant_id:
            return Response([])

        tech = request.user

        unread_sq = inbox_unread_subquery_for_reader(tech)

        qs = (
            TechnicianInboxThread.objects.filter(
                tenant_id=tenant_id,
                technician=tech,
            )
            .select_related("job")
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
                row["thread_id"]: row["max_created"]
                for row in newest_per_thread
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
                last_msgs, tech
            )
            receipt_msg_ids = set(
                TechnicianInboxMessageReceipt.objects.filter(
                    message_id__in=ids_needing_receipt,
                    reader=tech,
                ).values_list("message_id", flat=True)
            )
            annotate_last_messages_read_for_reader(
                last_msgs, tech, receipt_msg_ids
            )
        else:
            for thread in threads:
                thread._prefetched_last_message = None

        serializer = TechnicianInboxThreadSerializer(
            threads, many=True, context={"request": request}
        )
        return Response(serializer.data)


class TechnicianInboxThreadDetailView(APIView):
    permission_classes = [IsAuthenticated, IsTechnician]

    def _get_thread(self, request, thread_id):
        tenant_id = getattr(request.user, "tenant_id", None)
        if not tenant_id:
            return None
        return (
            TechnicianInboxThread.objects.filter(
                id=thread_id,
                tenant_id=tenant_id,
                technician=request.user,
            )
            .select_related("job")
            .first()
        )

    def patch(self, request, thread_id):
        thread = self._get_thread(request, thread_id)
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

        unread_sq = inbox_unread_subquery_for_reader(request.user)
        thread = (
            TechnicianInboxThread.objects.filter(pk=thread.pk)
            .select_related("job")
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
            tech = request.user
            if last_msg.sender_user_id == tech.id:
                last_msg._is_read = True
            else:
                last_msg._is_read = TechnicianInboxMessageReceipt.objects.filter(
                    message=last_msg, reader=tech
                ).exists()

        out = TechnicianInboxThreadSerializer(
            thread, context={"request": request}
        )
        return Response(out.data)


class TechnicianInboxMessageListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsTechnician]

    def _get_thread(self, request, thread_id):
        tenant_id = getattr(request.user, "tenant_id", None)
        if not tenant_id:
            return None
        return (
            TechnicianInboxThread.objects.filter(
                id=thread_id,
                tenant_id=tenant_id,
                technician=request.user,
            )
            .select_related("job")
            .first()
        )

    def get(self, request, thread_id):
        thread = self._get_thread(request, thread_id)
        if not thread:
            return Response(
                {"detail": "Thread not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        tech = request.user

        receipt_exists = TechnicianInboxMessageReceipt.objects.filter(
            message_id=OuterRef("pk"),
            reader=tech,
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
            if msg.sender_user_id == tech.id:
                msg._is_read = True
            else:
                msg._is_read = bool(getattr(msg, "_has_receipt", False))

        serializer = TechnicianInboxMessageSerializer(
            messages, many=True, context={"request": request}
        )
        return Response(serializer.data)

    def post(self, request, thread_id):
        thread = self._get_thread(request, thread_id)
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
        tech = request.user

        first = getattr(tech, "first_name", "") or ""
        last = getattr(tech, "last_name", "") or ""
        sender_name = f"{first} {last}".strip() or "You"

        msg = TechnicianInboxMessage.objects.create(
            tenant_id=thread.tenant_id,
            thread=thread,
            sender_type=TechnicianInboxSenderType.TECHNICIAN,
            sender_user=tech,
            sender_name=sender_name,
            body=body,
            job=thread.job,
        )

        thread.last_activity_at = msg.created_at
        thread.save(update_fields=["last_activity_at", "updated_at"])

        logger.info(
            "Technician %s sent message %s in thread %s",
            tech.id,
            msg.id,
            thread.id,
        )

        msg._is_read = True
        out = TechnicianInboxMessageSerializer(
            msg, context={"request": request}
        )
        return Response(out.data, status=status.HTTP_201_CREATED)


class TechnicianInboxMarkReadView(APIView):
    permission_classes = [IsAuthenticated, IsTechnician]

    def post(self, request, thread_id):
        tenant_id = getattr(request.user, "tenant_id", None)
        if not tenant_id:
            return Response(
                {"detail": "Thread not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        tech = request.user

        thread = TechnicianInboxThread.objects.filter(
            id=thread_id,
            tenant_id=tenant_id,
            technician=tech,
        ).first()
        if not thread:
            return Response(
                {"detail": "Thread not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        unread_msgs = (
            TechnicianInboxMessage.objects.filter(thread=thread)
            .exclude(sender_user=tech)
            .exclude(read_receipts__reader=tech)
        )

        receipts_to_create = [
            TechnicianInboxMessageReceipt(
                tenant_id=tenant_id,
                message=msg,
                reader=tech,
            )
            for msg in unread_msgs
        ]

        if receipts_to_create:
            TechnicianInboxMessageReceipt.objects.bulk_create(
                receipts_to_create,
                ignore_conflicts=True,
            )
            logger.info(
                "Marked %d messages as read for technician %s in thread %s",
                len(receipts_to_create),
                tech.id,
                thread_id,
            )

        return Response(status=status.HTTP_204_NO_CONTENT)


class TechnicianInboxOperatorRecipientsView(APIView):
    """
    GET /api/v1/technicians/me/inbox/operators/

    Operators and admins on the same tenant; each row notes whether an
    ``operator_direct`` thread already exists for this technician.
    """

    permission_classes = [IsAuthenticated, IsTechnician]

    def get(self, request):
        tenant_id = getattr(request.user, "tenant_id", None)
        if not tenant_id:
            return Response([])

        tech = request.user

        operators = (
            User.objects.filter(
                tenant_id=tenant_id,
                is_active=True,
                role__in=MESSAGABLE_STAFF_ROLES,
            )
            .exclude(id=tech.id)
            .order_by("first_name", "last_name", "email")
        )

        existing_threads = dict(
            TechnicianInboxThread.objects.filter(
                tenant_id=tenant_id,
                technician=tech,
                thread_type=TechnicianInboxThreadType.OPERATOR_DIRECT,
                operator_contact__isnull=False,
            ).values_list("operator_contact_id", "id")
        )

        results = []
        for op in operators:
            op.has_existing_thread = op.id in existing_threads
            op.existing_thread_id = existing_threads.get(op.id)
            results.append(op)

        serializer = OperatorRecipientSerializer(results, many=True)
        return Response(serializer.data)


class TechnicianInboxStartThreadView(APIView):
    """
    POST /api/v1/technicians/me/inbox/threads/start/

    Creates or reuses a single ``operator_direct`` thread per technician ↔
    operator pair and appends the given message.
    """

    permission_classes = [IsAuthenticated, IsTechnician]

    def post(self, request):
        tenant_id = getattr(request.user, "tenant_id", None)
        if not tenant_id:
            return Response(
                {"detail": "Tenant not found."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = TechnicianInboxStartThreadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        operator_id = serializer.validated_data["operator_id"]
        body = serializer.validated_data["body"]
        tech = request.user

        try:
            operator_user = User.objects.get(
                id=operator_id,
                tenant_id=tenant_id,
                is_active=True,
                role__in=MESSAGABLE_STAFF_ROLES,
            )
        except User.DoesNotExist:
            return Response(
                {"detail": "Operator not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        op_first = getattr(operator_user, "first_name", "") or ""
        op_last = getattr(operator_user, "last_name", "") or ""
        op_name = f"{op_first} {op_last}".strip() or operator_user.email

        tech_first = getattr(tech, "first_name", "") or ""
        tech_last = getattr(tech, "last_name", "") or ""
        tech_sender_name = f"{tech_first} {tech_last}".strip() or "You"

        existing_thread = TechnicianInboxThread.objects.filter(
            tenant_id=tenant_id,
            technician=tech,
            operator_contact=operator_user,
            thread_type=TechnicianInboxThreadType.OPERATOR_DIRECT,
        ).first()

        now = timezone.now()
        created = False

        if existing_thread:
            thread = existing_thread
        else:
            thread = TechnicianInboxThread.objects.create(
                tenant_id=tenant_id,
                technician=tech,
                thread_type=TechnicianInboxThreadType.OPERATOR_DIRECT,
                title=op_name,
                subtitle="Operator",
                participant_name=op_name,
                participant_avatar_url=getattr(
                    operator_user, "avatar_url", None
                ),
                operator_contact=operator_user,
                last_activity_at=now,
            )
            created = True
            logger.info(
                "Technician %s started thread %s with operator %s",
                tech.id,
                thread.id,
                operator_user.id,
            )

        msg = TechnicianInboxMessage.objects.create(
            tenant_id=tenant_id,
            thread=thread,
            sender_type=TechnicianInboxSenderType.TECHNICIAN,
            sender_user=tech,
            sender_name=tech_sender_name,
            body=body,
        )

        thread.last_activity_at = msg.created_at
        thread.save(update_fields=["last_activity_at", "updated_at"])

        unread_sq = inbox_unread_subquery_for_reader(tech)
        thread = (
            TechnicianInboxThread.objects.filter(pk=thread.pk)
            .select_related("job")
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

        out = TechnicianInboxThreadSerializer(
            thread, context={"request": request}
        )
        resp_status = (
            status.HTTP_201_CREATED if created else status.HTTP_200_OK
        )
        return Response(out.data, status=resp_status)
