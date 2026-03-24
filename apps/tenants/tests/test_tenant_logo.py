from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.tenants.models import Tenant, TenantStatus
from apps.users.models import User, UserRole


class TenantMeLogoAPITests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(
            name="Logo Co",
            slug="logo-co",
            status=TenantStatus.ACTIVE,
        )
        self.user = User.objects.create_user(
            email="op@example.com",
            password="x",
            tenant=self.tenant,
            role=UserRole.ADMIN,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.logo_url = "/api/v1/tenants/me/logo/"
        self.me_url = "/api/v1/tenants/me/"

    def test_get_me_includes_logo_url(self):
        self.tenant.logo_url = "https://cdn.example.com/x.png"
        self.tenant.save(update_fields=["logo_url"])
        r = self.client.get(self.me_url)
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data.get("logo_url"), "https://cdn.example.com/x.png")

    def test_patch_external_logo_url(self):
        url = "https://storage.example.com/org.png"
        r = self.client.patch(self.me_url, {"logo_url": url}, format="json")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data.get("logo_url"), url)
        self.tenant.refresh_from_db()
        self.assertEqual(self.tenant.logo_url, url)

    def test_post_multipart_logo(self):
        png = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
            b"\x00\x01\x01\x00\x18\xdd\x8d\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        up = SimpleUploadedFile("x.png", png, content_type="image/png")
        r = self.client.post(self.logo_url, {"file": up}, format="multipart")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(r.data.get("logo_url"))
        self.tenant.refresh_from_db()
        self.assertTrue(self.tenant.logo_url)

    def test_delete_logo(self):
        self.tenant.logo_url = "https://x.test/y.png"
        self.tenant.save(update_fields=["logo_url"])
        r = self.client.delete(self.logo_url)
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIsNone(r.data.get("logo_url"))
        self.tenant.refresh_from_db()
        self.assertIsNone(self.tenant.logo_url)
