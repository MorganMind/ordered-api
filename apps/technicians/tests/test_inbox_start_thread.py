import uuid

from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.tenants.models import Tenant, TenantStatus
from apps.users.models import UserRole
from apps.technicians.inbox_models import (
    TechnicianInboxMessage,
    TechnicianInboxThread,
    TechnicianInboxSenderType,
    TechnicianInboxThreadType,
)


class StartThreadTestMixin:
    def _create_tenant(self):
        return Tenant.objects.create(
            name="Test Tenant",
            slug=f"st-{uuid.uuid4().hex[:16]}",
            status=TenantStatus.ACTIVE,
        )

    def _create_user(self, tenant, *, email, role, **kwargs):
        from django.contrib.auth import get_user_model

        User = get_user_model()
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
            role="operator",
            first_name="Sarah",
            last_name="Ops",
        )
        self.admin_user = self._create_user(
            self.tenant,
            email="admin@example.com",
            role=UserRole.ADMIN,
            first_name="Admin",
            last_name="Boss",
        )
        self.other_tenant = self._create_tenant()
        self.other_operator = self._create_user(
            self.other_tenant,
            email="other_op@example.com",
            role=UserRole.ADMIN,
            first_name="Other",
            last_name="Op",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.technician)


class OperatorRecipientsTests(StartThreadTestMixin, TestCase):
    def setUp(self):
        self._set_up_tenant_and_users()
        self.url = "/api/v1/technicians/me/inbox/operators/"

    def test_returns_same_tenant_operators(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        ids = [r["id"] for r in resp.data]
        self.assertIn(str(self.operator.id), ids)

    def test_returns_admins(self):
        resp = self.client.get(self.url)
        ids = [r["id"] for r in resp.data]
        self.assertIn(str(self.admin_user.id), ids)

    def test_excludes_other_tenant_operators(self):
        resp = self.client.get(self.url)
        ids = [r["id"] for r in resp.data]
        self.assertNotIn(str(self.other_operator.id), ids)

    def test_excludes_self(self):
        resp = self.client.get(self.url)
        ids = [r["id"] for r in resp.data]
        self.assertNotIn(str(self.technician.id), ids)

    def test_shows_existing_thread_flag(self):
        TechnicianInboxThread.objects.create(
            tenant=self.tenant,
            technician=self.technician,
            thread_type=TechnicianInboxThreadType.OPERATOR_DIRECT,
            title="Sarah Ops",
            operator_contact=self.operator,
            last_activity_at=timezone.now(),
        )

        resp = self.client.get(self.url)
        op_data = next(
            r for r in resp.data if r["id"] == str(self.operator.id)
        )
        self.assertTrue(op_data["has_existing_thread"])
        self.assertIsNotNone(op_data["existing_thread_id"])

    def test_no_existing_thread(self):
        resp = self.client.get(self.url)
        op_data = next(
            r for r in resp.data if r["id"] == str(self.operator.id)
        )
        self.assertFalse(op_data["has_existing_thread"])
        self.assertIsNone(op_data["existing_thread_id"])

    def test_full_name_fallback(self):
        no_name_op = self._create_user(
            self.tenant,
            email="noname@example.com",
            role="operator",
            first_name="",
            last_name="",
        )
        resp = self.client.get(self.url)
        data = next(r for r in resp.data if r["id"] == str(no_name_op.id))
        self.assertEqual(data["full_name"], "noname@example.com")

    def test_inactive_operators_excluded(self):
        inactive = self._create_user(
            self.tenant,
            email="inactive@example.com",
            role=UserRole.ADMIN,
            first_name="Gone",
            last_name="Operator",
        )
        inactive.is_active = False
        inactive.save()

        resp = self.client.get(self.url)
        ids = [r["id"] for r in resp.data]
        self.assertNotIn(str(inactive.id), ids)

    def test_unauthenticated(self):
        self.client.force_authenticate(user=None)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


class StartThreadTests(StartThreadTestMixin, TestCase):
    def setUp(self):
        self._set_up_tenant_and_users()
        self.url = "/api/v1/technicians/me/inbox/threads/start/"

    def test_start_new_thread(self):
        resp = self.client.post(
            self.url,
            data={
                "operator_id": str(self.operator.id),
                "body": "Hi, I have a question",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["thread_type"], "operator_direct")
        self.assertEqual(resp.data["title"], "Sarah Ops")
        self.assertEqual(resp.data["participant_name"], "Sarah Ops")

        self.assertTrue(
            TechnicianInboxThread.objects.filter(
                technician=self.technician,
                operator_contact=self.operator,
            ).exists()
        )

    def test_start_thread_creates_first_message(self):
        resp = self.client.post(
            self.url,
            data={
                "operator_id": str(self.operator.id),
                "body": "Hello operator!",
            },
            format="json",
        )
        thread_id = resp.data["id"]
        msg = TechnicianInboxMessage.objects.filter(
            thread_id=thread_id
        ).first()
        self.assertIsNotNone(msg)
        self.assertEqual(msg.body, "Hello operator!")
        self.assertEqual(
            msg.sender_type, TechnicianInboxSenderType.TECHNICIAN
        )
        self.assertEqual(msg.sender_user, self.technician)
        self.assertEqual(msg.sender_name, "Alex Tech")

    def test_start_thread_last_message_in_response(self):
        resp = self.client.post(
            self.url,
            data={
                "operator_id": str(self.operator.id),
                "body": "First message",
            },
            format="json",
        )
        self.assertIsNotNone(resp.data["last_message"])
        self.assertEqual(resp.data["last_message"]["body"], "First message")
        self.assertEqual(
            resp.data["last_message"]["sender_type"], "technician"
        )

    def test_duplicate_thread_appends_message(self):
        resp1 = self.client.post(
            self.url,
            data={
                "operator_id": str(self.operator.id),
                "body": "First message",
            },
            format="json",
        )
        self.assertEqual(resp1.status_code, status.HTTP_201_CREATED)
        thread_id = resp1.data["id"]

        resp2 = self.client.post(
            self.url,
            data={
                "operator_id": str(self.operator.id),
                "body": "Second message",
            },
            format="json",
        )
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)
        self.assertEqual(resp2.data["id"], thread_id)

        msg_count = TechnicianInboxMessage.objects.filter(
            thread_id=thread_id
        ).count()
        self.assertEqual(msg_count, 2)

    def test_start_thread_with_admin(self):
        resp = self.client.post(
            self.url,
            data={
                "operator_id": str(self.admin_user.id),
                "body": "Hi admin",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["title"], "Admin Boss")

    def test_operator_from_other_tenant_rejected(self):
        resp = self.client.post(
            self.url,
            data={
                "operator_id": str(self.other_operator.id),
                "body": "Should fail",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_nonexistent_operator_rejected(self):
        resp = self.client.post(
            self.url,
            data={
                "operator_id": str(uuid.uuid4()),
                "body": "Should fail",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_empty_body_rejected(self):
        resp = self.client.post(
            self.url,
            data={
                "operator_id": str(self.operator.id),
                "body": "",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_missing_body_rejected(self):
        resp = self.client.post(
            self.url,
            data={"operator_id": str(self.operator.id)},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_missing_operator_id_rejected(self):
        resp = self.client.post(
            self.url,
            data={"body": "Hello"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_message_technician(self):
        other_tech = self._create_user(
            self.tenant,
            email="tech2@example.com",
            role=UserRole.TECHNICIAN,
        )
        resp = self.client.post(
            self.url,
            data={
                "operator_id": str(other_tech.id),
                "body": "Hey tech",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_unauthenticated(self):
        self.client.force_authenticate(user=None)
        resp = self.client.post(
            self.url,
            data={
                "operator_id": str(self.operator.id),
                "body": "Should fail",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)
