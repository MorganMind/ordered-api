import uuid

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from apps.tenants.models import Tenant
from apps.users.models import User, UserRole


@override_settings(MEDIA_ROOT="/tmp/ordered-test-media")
class UsersMeApiTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="T", slug=f"t-{uuid.uuid4().hex[:8]}")
        self.user = User.objects.create_user(
            email="u@example.com",
            password="x",
            tenant=self.tenant,
            role=UserRole.CLIENT,
            first_name="A",
            last_name="B",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_get_me_includes_avatar_url(self):
        r = self.client.get("/api/v1/users/me/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIn("avatar_url", r.data)
        self.assertEqual(r.data["email"], "u@example.com")

    def test_patch_avatar_url_external(self):
        url = "https://cdn.example.com/a.png"
        r = self.client.patch("/api/v1/users/me/", {"avatar_url": url}, format="json")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["avatar_url"], url)
        self.user.refresh_from_db()
        self.assertEqual(self.user.avatar_url, url)

    def test_post_multipart_avatar(self):
        png = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
            b"\x01\x01\x01\x00\x18\xdd\x8d\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        up = SimpleUploadedFile("a.png", png, content_type="image/png")
        r = self.client.post("/api/v1/users/me/avatar/", {"file": up}, format="multipart")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(r.data.get("avatar_url"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.avatar_url)

    def test_post_multipart_octet_stream_png_magic(self):
        """Mobile often sends application/octet-stream; backend infers image/png from bytes."""
        png = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
            b"\x01\x01\x01\x00\x18\xdd\x8d\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        up = SimpleUploadedFile(
            "pick", png, content_type="application/octet-stream"
        )
        r = self.client.post("/api/v1/users/me/avatar/", {"file": up}, format="multipart")
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        self.assertIsNotNone(r.data.get("avatar_url"))

    def test_post_multipart_avatar_field_name_avatar(self):
        png = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
            b"\x01\x01\x01\x00\x18\xdd\x8d\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        up = SimpleUploadedFile("b.png", png, content_type="image/png")
        r = self.client.post("/api/v1/users/me/avatar/", {"avatar": up}, format="multipart")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(r.data.get("avatar_url"))

    def test_delete_avatar(self):
        self.user.avatar_url = "https://x.test/y.png"
        self.user.save(update_fields=["avatar_url"])
        r = self.client.delete("/api/v1/users/me/avatar/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertIsNone(self.user.avatar_url)
