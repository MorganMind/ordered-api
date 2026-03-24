from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.tenants.models import Tenant, TenantStatus
from apps.users.models import User, UserRole


class TenantMeAPITests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(
            name="Old Name",
            slug="old-slug-me",
            status=TenantStatus.ACTIVE,
        )
        self.user = User.objects.create_user(
            email="operator@example.com",
            password="x",
            tenant=self.tenant,
            role=UserRole.ADMIN,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.url = "/api/v1/tenants/me/"

    def test_get_returns_tenant(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data.get("name"), "Old Name")
        self.assertEqual(resp.data.get("slug"), "old-slug-me")
        self.assertIn("logo_url", resp.data)
        self.assertIsNone(resp.data.get("logo_url"))

    def test_patch_name(self):
        resp = self.client.patch(
            self.url,
            {"name": "Spacekeeping"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["name"], "Spacekeeping")
        self.tenant.refresh_from_db()
        self.assertEqual(self.tenant.name, "Spacekeeping")

    def test_patch_logo_url_external(self):
        url = "https://cdn.example.com/org/logo.png"
        resp = self.client.patch(self.url, {"logo_url": url}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["logo_url"], url)
        self.tenant.refresh_from_db()
        self.assertEqual(self.tenant.logo_url, url)

    def test_patch_logo_url_null_clears(self):
        self.tenant.logo_url = "https://cdn.example.com/x.png"
        self.tenant.save(update_fields=["logo_url"])
        resp = self.client.patch(self.url, {"logo_url": None}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIsNone(resp.data.get("logo_url"))
        self.tenant.refresh_from_db()
        self.assertIsNone(self.tenant.logo_url)
