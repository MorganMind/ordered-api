from django.test import TestCase

from api_auth.me_response import enrich_tenant_for_auth_me
from apps.tenants.models import Tenant, TenantStatus


class EnrichTenantForAuthMeTests(TestCase):
    def test_db_name_and_slug_override_stale_jwt_metadata(self):
        tenant = Tenant.objects.create(
            name="Spacekeeping",
            slug="spacekeeping",
            status=TenantStatus.ACTIVE,
        )
        seed = {
            "id": str(tenant.id),
            "name": "ATCH",
            "slug": "stale-slug",
            "settings": {},
        }
        out = enrich_tenant_for_auth_me(seed)
        self.assertIsNotNone(out)
        self.assertEqual(out["name"], "Spacekeeping")
        self.assertEqual(out["slug"], "spacekeeping")

    def test_logo_url_from_db_row(self):
        tenant = Tenant.objects.create(
            name="A",
            slug="a-logo",
            status=TenantStatus.ACTIVE,
            logo_url="https://cdn.example.com/org.png",
        )
        seed = {"id": str(tenant.id), "settings": {}}
        out = enrich_tenant_for_auth_me(seed)
        self.assertIsNotNone(out)
        self.assertEqual(out.get("logo_url"), "https://cdn.example.com/org.png")
