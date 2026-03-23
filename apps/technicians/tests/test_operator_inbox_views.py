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
from apps.technicians.tests.test_inbox_views import InboxTestMixin


class OperatorInboxTests(InboxTestMixin, TestCase):
    def setUp(self):
        self._set_up_tenant_and_users()
        self.operator_client = APIClient()
        self.operator_client.force_authenticate(user=self.operator)

    def _make_thread_operator_scoped(self, **overrides):
        defaults = dict(
            tenant=self.tenant,
            technician=self.technician,
            operator_contact=self.operator,
            thread_type=TechnicianInboxThreadType.OPERATOR_DIRECT,
            title="Sarah Ops",
            subtitle="Operator",
            participant_name="Sarah Ops",
            last_activity_at=timezone.now(),
        )
        defaults.update(overrides)
        return TechnicianInboxThread.objects.create(**defaults)

    def test_operator_list_threads(self):
        self._make_thread_operator_scoped()
        resp = self.operator_client.get("/api/v1/operator/inbox/threads/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 1)
        row = resp.data[0]
        self.assertEqual(row["technician_id"], str(self.technician.id))
        self.assertEqual(row["title"], "Alex Tech")
        self.assertIn("thread_type", row)

    def test_operator_list_excludes_other_operator_threads(self):
        other_op = self._create_user(
            self.tenant,
            email="otherop@example.com",
            role=UserRole.ADMIN,
            first_name="Other",
            last_name="Op",
        )
        self._make_thread_operator_scoped()
        self._make_thread_operator_scoped(
            operator_contact=other_op,
            technician=self.other_tech,
        )

        resp = self.operator_client.get("/api/v1/operator/inbox/threads/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 1)

    def test_operator_unread_and_mark_read(self):
        thread = self._make_thread_operator_scoped()
        self._make_message(
            thread,
            body="from tech",
            sender_type=TechnicianInboxSenderType.TECHNICIAN,
            sender_user=self.technician,
            sender_name="Alex Tech",
        )

        list_url = "/api/v1/operator/inbox/threads/"
        resp = self.operator_client.get(list_url)
        self.assertEqual(resp.data[0]["unread_count"], 1)

        mark_url = f"/api/v1/operator/inbox/threads/{thread.id}/mark-read/"
        r2 = self.operator_client.post(mark_url)
        self.assertEqual(r2.status_code, status.HTTP_204_NO_CONTENT)

        resp = self.operator_client.get(list_url)
        self.assertEqual(resp.data[0]["unread_count"], 0)

    def test_operator_post_message(self):
        thread = self._make_thread_operator_scoped()
        url = f"/api/v1/operator/inbox/threads/{thread.id}/messages/"
        resp = self.operator_client.post(
            url,
            data={"body": "Reply from operator"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["sender_type"], "operator")
        self.assertEqual(resp.data["body"], "Reply from operator")

    def test_operator_start_thread(self):
        url = "/api/v1/operator/inbox/threads/start/"
        resp = self.operator_client.post(
            url,
            data={
                "technician_id": str(self.technician.id),
                "body": "Hello tech",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["technician_id"], str(self.technician.id))

    def test_operator_technician_recipients(self):
        self._make_thread_operator_scoped()
        resp = self.operator_client.get("/api/v1/operator/inbox/technicians/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        by_id = {str(r["id"]): r for r in resp.data}
        self.assertIn(str(self.technician.id), by_id)
        self.assertTrue(by_id[str(self.technician.id)]["has_existing_thread"])

    def test_operator_patch_pin(self):
        thread = self._make_thread_operator_scoped(is_pinned=False)
        url = f"/api/v1/operator/inbox/threads/{thread.id}/"
        resp = self.operator_client.patch(
            url, data={"is_pinned": True}, format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["is_pinned"])

    def test_technician_forbidden_operator_inbox(self):
        resp = self.client.get("/api/v1/operator/inbox/threads/")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
