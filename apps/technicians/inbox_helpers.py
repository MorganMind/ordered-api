"""
Shared subqueries and small helpers for technician + operator inbox views.
"""

from django.db.models import Count, IntegerField, OuterRef, Subquery

from apps.technicians.inbox_models import TechnicianInboxMessage


def inbox_unread_subquery_for_reader(reader):
    """
    Annotate ``TechnicianInboxThread`` with unread count for ``reader``.

    A message counts as unread if it is not authored by ``reader``
    (``sender_user``) and has no ``read_receipts`` row for ``reader``.
    """

    return Subquery(
        TechnicianInboxMessage.objects.filter(
            thread_id=OuterRef("pk"),
        )
        .exclude(sender_user=reader)
        .exclude(read_receipts__reader=reader)
        .values("thread_id")
        .annotate(c=Count("id"))
        .values("c")[:1],
        output_field=IntegerField(),
    )


def annotate_last_messages_read_for_reader(last_messages, reader, receipt_msg_ids: set):
    """Set ``_is_read`` on each message for list prefetch (same rules as serializers)."""
    for m in last_messages:
        if m.sender_user_id == reader.id:
            m._is_read = True
        else:
            m._is_read = m.id in receipt_msg_ids


def last_message_ids_needing_receipt(last_messages, reader):
    return [
        m.id
        for m in last_messages
        if m.sender_user_id != reader.id
    ]
