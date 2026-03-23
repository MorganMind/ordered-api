import uuid
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.tenants.models import Tenant, TenantStatus
from apps.users.models import User, UserRole
from apps.technicians.inbox_models import (
    TechnicianInboxMessage,
    TechnicianInboxMessageReceipt,
    TechnicianInboxThread,
    TechnicianInboxSenderType,
    TechnicianInboxThreadType,
)


class InboxTestMixin:
    def _create_tenant(self):
        return Tenant.objects.create(
            name="Test Tenant",
            slug=f"inbox-{uuid.uuid4().hex[:16]}",
            status=TenantStatus.ACTIVE,
        )

    def _create_user(self, tenant, *, email, role, **kwargs):
        return User.objects.create_user(
            email=email,
            password="testpass123",
            tenant=tenant,
            role=role,
            **kwargs,
        )

    def _set_up_tenant_and_users(self):
        self.tenant = self._create_tenant()
        self.technician = self._create_user(
            self.tenant,
            email="tech@example.com",
            role=UserRole.TECHNICIAN,
            first_name="Alex",
            last_name="Tech",
        )
        self.operator = self._create_user(
            self.tenant,
            email="operator@example.com",
            role=UserRole.ADMIN,
            first_name="Sarah",
            last_name="Ops",
        )
        self.other_tech = self._create_user(
            self.tenant,
            email="other@example.com",
            role=UserRole.TECHNICIAN,
            first_name="Other",
            last_name="Tech",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.technician)

    def _make_thread(self, **overrides):
        defaults = dict(
            tenant=self.tenant,
            technician=self.technician,
            thread_type=TechnicianInboxThreadType.OPERATOR_DIRECT,
            title="Dispatch Team",
            subtitle="Operator messages",
            participant_name="Sarah",
            last_activity_at=timezone.now(),
        )
        defaults.update(overrides)
        return TechnicianInboxThread.objects.create(**defaults)

    def _make_message(self, thread, **overrides):
        defaults = dict(
            tenant=self.tenant,
            thread=thread,
            sender_type=TechnicianInboxSenderType.OPERATOR,
            sender_user=self.operator,
            sender_name="Sarah",
            body="Hello from operator",
        )
        defaults.update(overrides)
        return TechnicianInboxMessage.objects.create(**defaults)


class TechnicianInboxThreadListTests(InboxTestMixin, TestCase):
    def setUp(self):
        self._set_up_tenant_and_users()
        self.url = "/api/v1/technicians/me/inbox/threads/"

    def test_empty_inbox(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data, [])

    def test_returns_own_threads_only(self):
        own = self._make_thread(title="My Thread")
        self._make_thread(title="Other Thread", technician=self.other_tech)

        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        ids = [t["id"] for t in resp.data]
        self.assertIn(str(own.id), ids)
        self.assertEqual(len(ids), 1)

    def test_ordering_pinned_first(self):
        self._make_thread(
            title="Old",
            last_activity_at=timezone.now() - timedelta(hours=2),
        )
        self._make_thread(
            title="New",
            last_activity_at=timezone.now(),
        )
        self._make_thread(
            title="Pinned",
            is_pinned=True,
            last_activity_at=timezone.now() - timedelta(hours=5),
        )

        resp = self.client.get(self.url)
        titles = [t["title"] for t in resp.data]
        self.assertEqual(titles[0], "Pinned")
        self.assertEqual(titles[1], "New")
        self.assertEqual(titles[2], "Old")

    def test_last_message_included(self):
        thread = self._make_thread()
        self._make_message(thread, body="Latest message")

        resp = self.client.get(self.url)
        thread_data = resp.data[0]
        self.assertIsNotNone(thread_data["last_message"])
        self.assertEqual(
            thread_data["last_message"]["body"], "Latest message"
        )

    def test_unread_count(self):
        thread = self._make_thread()
        self._make_message(thread, body="msg 1")
        self._make_message(thread, body="msg 2")
        self._make_message(
            thread,
            body="my reply",
            sender_type=TechnicianInboxSenderType.TECHNICIAN,
            sender_user=self.technician,
            sender_name="You",
        )

        resp = self.client.get(self.url)
        self.assertEqual(resp.data[0]["unread_count"], 2)

    def test_unread_count_after_read(self):
        thread = self._make_thread()
        msg = self._make_message(thread, body="msg 1")
        TechnicianInboxMessageReceipt.objects.create(
            tenant=self.tenant,
            message=msg,
            reader=self.technician,
        )

        resp = self.client.get(self.url)
        self.assertEqual(resp.data[0]["unread_count"], 0)

    def test_thread_fields(self):
        self._make_thread(
            thread_type=TechnicianInboxThreadType.CLIENT_JOB,
            title="Jennifer Martinez",
            subtitle="AC Repair",
            participant_name="Jennifer",
            is_pinned=False,
        )

        resp = self.client.get(self.url)
        data = resp.data[0]
        self.assertEqual(data["thread_type"], "client_job")
        self.assertEqual(data["title"], "Jennifer Martinez")
        self.assertEqual(data["subtitle"], "AC Repair")
        self.assertEqual(data["participant_name"], "Jennifer")
        self.assertFalse(data["is_pinned"])

    def test_unauthenticated_rejected(self):
        self.client.force_authenticate(user=None)
        resp = self.client.get(self.url)
        self.assertIn(
            resp.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )


class TechnicianInboxThreadDetailTests(InboxTestMixin, TestCase):
    def setUp(self):
        self._set_up_tenant_and_users()

    def test_pin_thread(self):
        thread = self._make_thread(is_pinned=False)
        url = f"/api/v1/technicians/me/inbox/threads/{thread.id}/"

        resp = self.client.patch(
            url,
            data={"is_pinned": True},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["is_pinned"])

        thread.refresh_from_db()
        self.assertTrue(thread.is_pinned)

    def test_unpin_thread(self):
        thread = self._make_thread(is_pinned=True)
        url = f"/api/v1/technicians/me/inbox/threads/{thread.id}/"

        resp = self.client.patch(
            url,
            data={"is_pinned": False},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(resp.data["is_pinned"])

    def test_cannot_patch_other_techs_thread(self):
        thread = self._make_thread(technician=self.other_tech)
        url = f"/api/v1/technicians/me/inbox/threads/{thread.id}/"

        resp = self.client.patch(
            url,
            data={"is_pinned": True},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_nonexistent_thread_returns_404(self):
        url = f"/api/v1/technicians/me/inbox/threads/{uuid.uuid4()}/"
        resp = self.client.patch(
            url,
            data={"is_pinned": True},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)


class TechnicianInboxMessageListTests(InboxTestMixin, TestCase):
    def setUp(self):
        self._set_up_tenant_and_users()

    def test_list_messages_chronological(self):
        thread = self._make_thread()
        self._make_message(thread, body="first")
        self._make_message(thread, body="second")

        url = f"/api/v1/technicians/me/inbox/threads/{thread.id}/messages/"
        resp = self.client.get(url)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 2)
        self.assertEqual(resp.data[0]["body"], "first")
        self.assertEqual(resp.data[1]["body"], "second")

    def test_message_fields(self):
        thread = self._make_thread()
        msg = self._make_message(
            thread,
            body="Test body",
            sender_type=TechnicianInboxSenderType.OPERATOR,
            sender_name="Sarah",
        )

        url = f"/api/v1/technicians/me/inbox/threads/{thread.id}/messages/"
        resp = self.client.get(url)

        data = resp.data[0]
        self.assertEqual(data["id"], str(msg.id))
        self.assertEqual(data["thread_id"], str(thread.id))
        self.assertEqual(data["sender_name"], "Sarah")
        self.assertEqual(data["sender_type"], "operator")
        self.assertEqual(data["body"], "Test body")
        self.assertIn("timestamp", data)
        self.assertIn("is_read", data)

    def test_is_read_false_for_unread(self):
        thread = self._make_thread()
        self._make_message(thread)

        url = f"/api/v1/technicians/me/inbox/threads/{thread.id}/messages/"
        resp = self.client.get(url)
        self.assertFalse(resp.data[0]["is_read"])

    def test_is_read_true_for_own_messages(self):
        thread = self._make_thread()
        self._make_message(
            thread,
            sender_type=TechnicianInboxSenderType.TECHNICIAN,
            sender_user=self.technician,
            sender_name="You",
            body="my message",
        )

        url = f"/api/v1/technicians/me/inbox/threads/{thread.id}/messages/"
        resp = self.client.get(url)
        self.assertTrue(resp.data[0]["is_read"])

    def test_is_read_true_after_receipt(self):
        thread = self._make_thread()
        msg = self._make_message(thread)
        TechnicianInboxMessageReceipt.objects.create(
            tenant=self.tenant,
            message=msg,
            reader=self.technician,
        )

        url = f"/api/v1/technicians/me/inbox/threads/{thread.id}/messages/"
        resp = self.client.get(url)
        self.assertTrue(resp.data[0]["is_read"])

    def test_cannot_list_other_techs_thread(self):
        thread = self._make_thread(technician=self.other_tech)
        url = f"/api/v1/technicians/me/inbox/threads/{thread.id}/messages/"
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)


class TechnicianInboxSendMessageTests(InboxTestMixin, TestCase):
    def setUp(self):
        self._set_up_tenant_and_users()

    def test_send_message(self):
        thread = self._make_thread()
        url = f"/api/v1/technicians/me/inbox/threads/{thread.id}/messages/"

        resp = self.client.post(
            url,
            data={"body": "Hello from tech"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["body"], "Hello from tech")
        self.assertEqual(resp.data["sender_type"], "technician")
        self.assertEqual(resp.data["thread_id"], str(thread.id))

    def test_send_updates_thread_activity(self):
        thread = self._make_thread(
            last_activity_at=timezone.now() - timedelta(hours=5)
        )
        old_activity = thread.last_activity_at
        url = f"/api/v1/technicians/me/inbox/threads/{thread.id}/messages/"

        self.client.post(
            url,
            data={"body": "bump"},
            format="json",
        )
        thread.refresh_from_db()
        self.assertGreater(thread.last_activity_at, old_activity)

    def test_cannot_send_to_system_thread(self):
        thread = self._make_thread(
            thread_type=TechnicianInboxThreadType.SYSTEM_ALERT,
            title="System",
        )
        url = f"/api/v1/technicians/me/inbox/threads/{thread.id}/messages/"

        resp = self.client.post(
            url,
            data={"body": "reply attempt"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("system", str(resp.data).lower())

    def test_empty_body_rejected(self):
        thread = self._make_thread()
        url = f"/api/v1/technicians/me/inbox/threads/{thread.id}/messages/"

        resp = self.client.post(
            url,
            data={"body": ""},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_missing_body_rejected(self):
        thread = self._make_thread()
        url = f"/api/v1/technicians/me/inbox/threads/{thread.id}/messages/"

        resp = self.client.post(url, data={}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_send_to_other_techs_thread(self):
        thread = self._make_thread(technician=self.other_tech)
        url = f"/api/v1/technicians/me/inbox/threads/{thread.id}/messages/"

        resp = self.client.post(
            url,
            data={"body": "sneaky"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_sender_name_uses_user_name(self):
        thread = self._make_thread()
        url = f"/api/v1/technicians/me/inbox/threads/{thread.id}/messages/"

        resp = self.client.post(
            url,
            data={"body": "test"},
            format="json",
        )
        msg = TechnicianInboxMessage.objects.get(id=resp.data["id"])
        self.assertEqual(msg.sender_name, "Alex Tech")


class TechnicianInboxMarkReadTests(InboxTestMixin, TestCase):
    def setUp(self):
        self._set_up_tenant_and_users()

    def test_mark_read_creates_receipts(self):
        thread = self._make_thread()
        m1 = self._make_message(thread, body="msg 1")
        m2 = self._make_message(thread, body="msg 2")

        url = (
            f"/api/v1/technicians/me/inbox/threads/{thread.id}/mark-read/"
        )
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)

        self.assertTrue(
            TechnicianInboxMessageReceipt.objects.filter(
                message=m1, reader=self.technician
            ).exists()
        )
        self.assertTrue(
            TechnicianInboxMessageReceipt.objects.filter(
                message=m2, reader=self.technician
            ).exists()
        )

    def test_mark_read_skips_own_messages(self):
        thread = self._make_thread()
        own_msg = self._make_message(
            thread,
            sender_type=TechnicianInboxSenderType.TECHNICIAN,
            sender_user=self.technician,
            sender_name="You",
            body="my own",
        )

        url = (
            f"/api/v1/technicians/me/inbox/threads/{thread.id}/mark-read/"
        )
        self.client.post(url)

        self.assertFalse(
            TechnicianInboxMessageReceipt.objects.filter(
                message=own_msg, reader=self.technician
            ).exists()
        )

    def test_mark_read_idempotent(self):
        thread = self._make_thread()
        msg = self._make_message(thread)

        url = (
            f"/api/v1/technicians/me/inbox/threads/{thread.id}/mark-read/"
        )
        self.client.post(url)
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)

        self.assertEqual(
            TechnicianInboxMessageReceipt.objects.filter(
                message=msg, reader=self.technician
            ).count(),
            1,
        )

    def test_cannot_mark_read_other_techs_thread(self):
        thread = self._make_thread(technician=self.other_tech)
        url = (
            f"/api/v1/technicians/me/inbox/threads/{thread.id}/mark-read/"
        )
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_unread_count_zero_after_mark_read(self):
        thread = self._make_thread()
        self._make_message(thread, body="msg 1")
        self._make_message(thread, body="msg 2")

        list_url = "/api/v1/technicians/me/inbox/threads/"
        resp = self.client.get(list_url)
        self.assertEqual(resp.data[0]["unread_count"], 2)

        mark_url = (
            f"/api/v1/technicians/me/inbox/threads/{thread.id}/mark-read/"
        )
        self.client.post(mark_url)

        resp = self.client.get(list_url)
        self.assertEqual(resp.data[0]["unread_count"], 0)
