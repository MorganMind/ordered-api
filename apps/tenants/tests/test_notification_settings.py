from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.tenants.models import Tenant, TenantStatus
from apps.users.models import User, UserRole


class TenantNotificationSettingsAPITests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(
            name="T",
            slug="t-notify",
            status=TenantStatus.ACTIVE,
        )
        self.user = User.objects.create_user(
            email="admin@example.com",
            password="x",
            tenant=self.tenant,
            role=UserRole.ADMIN,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.url = "/api/v1/tenants/me/notification-settings/"

    def test_get_defaults_empty(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data.get("operator_admin_email"), "")

    def test_patch_operator_admin_email(self):
        resp = self.client.patch(
            self.url,
            {"operator_admin_email": "ops@example.com"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["operator_admin_email"], "ops@example.com")
        self.tenant.refresh_from_db()
        self.assertEqual(self.tenant.operator_admin_email, "ops@example.com")
