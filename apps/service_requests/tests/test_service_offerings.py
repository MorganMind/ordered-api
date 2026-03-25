import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.jobs.models import Skill
from apps.service_requests.models import (
    ServiceOffering,
    ServiceOfferingSkill,
    ServiceRequest,
    ServiceType,
)
from apps.tenants.models import Tenant
from apps.users.models import UserRole

User = get_user_model()


class ServiceOfferingApiTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(
            name="Acme",
            slug=f"acme-{uuid.uuid4().hex[:8]}",
        )
        self.other_tenant = Tenant.objects.create(
            name="Other",
            slug=f"other-{uuid.uuid4().hex[:8]}",
        )
        self.operator = User.objects.create_user(
            email="op@example.com",
            password="x",
            tenant=self.tenant,
            role=UserRole.ADMIN,
        )
        self.client_user = User.objects.create_user(
            email="client@example.com",
            password="x",
            tenant=self.tenant,
            role=UserRole.CLIENT,
        )
        self.skill_a = Skill.objects.create(
            key=f"sk-a-{uuid.uuid4().hex[:6]}",
            label="Skill A",
            category="cat",
        )
        self.skill_b = Skill.objects.create(
            key=f"sk-b-{uuid.uuid4().hex[:6]}",
            label="Skill B",
            category="cat",
        )
        self.api = APIClient()

    def test_operator_creates_offering_with_ordered_skills(self):
        self.api.force_authenticate(user=self.operator)
        r = self.api.post(
            "/api/v1/service-offerings/",
            {
                "name": "Premium Clean",
                "slug": "premium-clean",
                "description": "Full home",
                "is_active": True,
                "sort_order": 1,
                "reporting_category": ServiceType.DEEP_CLEAN,
                "skill_ids": [str(self.skill_b.id), str(self.skill_a.id)],
            },
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        off = ServiceOffering.objects.get(pk=r.data["id"])
        self.assertEqual(off.tenant_id, self.tenant.id)
        links = list(
            ServiceOfferingSkill.objects.filter(service_offering=off).order_by(
                "sort_order"
            )
        )
        self.assertEqual(len(links), 2)
        self.assertEqual(links[0].skill_id, self.skill_b.id)
        self.assertEqual(links[1].skill_id, self.skill_a.id)
        self.assertEqual(r.data["skills"][0]["key"], self.skill_b.key)
        self.assertEqual(r.data["skills"][1]["key"], self.skill_a.key)

    def test_client_cannot_create_offering(self):
        self.api.force_authenticate(user=self.client_user)
        r = self.api.post(
            "/api/v1/service-offerings/",
            {
                "name": "X",
                "slug": "x",
                "reporting_category": ServiceType.OTHER,
            },
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_client_lists_offerings(self):
        ServiceOffering.objects.create(
            tenant_id=self.tenant.id,
            name="Listed",
            slug="listed",
            reporting_category=ServiceType.STANDARD_CLEANING,
        )
        self.api.force_authenticate(user=self.client_user)
        r = self.api.get("/api/v1/service-offerings/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(r.data), 1)

    def test_create_service_request_with_offering_syncs_service_type(self):
        off = ServiceOffering.objects.create(
            tenant_id=self.tenant.id,
            name="Move package",
            slug="move-pkg",
            reporting_category=ServiceType.MOVE_IN_OUT,
        )
        ServiceOfferingSkill.objects.create(
            service_offering=off,
            skill=self.skill_a,
            sort_order=0,
        )
        self.api.force_authenticate(user=self.client_user)
        r = self.api.post(
            "/api/v1/service-requests/",
            {
                "contact_name": "Pat",
                "contact_phone": "555",
                "address_raw": "1 Main",
                "service_offering": str(off.id),
            },
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r.data["service_type"], ServiceType.MOVE_IN_OUT)
        self.assertEqual(r.data["service_label"], "Move package")
        self.assertEqual(r.data["service_offering"]["name"], "Move package")
        self.assertEqual(len(r.data["service_offering"]["skills"]), 1)
        sr = ServiceRequest.objects.get(pk=r.data["id"])
        self.assertEqual(sr.service_offering_id, off.id)
        self.assertEqual(sr.service_type, ServiceType.MOVE_IN_OUT)

    def test_create_rejects_foreign_tenant_offering(self):
        off = ServiceOffering.objects.create(
            tenant_id=self.other_tenant.id,
            name="Alien",
            slug="alien",
            reporting_category=ServiceType.OTHER,
        )
        self.api.force_authenticate(user=self.client_user)
        r = self.api.post(
            "/api/v1/service-requests/",
            {
                "contact_name": "Pat",
                "contact_phone": "555",
                "address_raw": "1 Main",
                "service_offering": str(off.id),
            },
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_lists_service_offering_templates(self):
        self.api.force_authenticate(user=self.client_user)
        r = self.api.get("/api/v1/service-offerings/templates/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertTrue(r.data["templates"])
        self.assertIn("key", r.data["templates"][0])

    def test_create_offering_from_template(self):
        Skill.objects.create(
            key="deep_cleaning",
            label="Deep Cleaning",
            category="cleaning",
            is_active=True,
        )
        self.api.force_authenticate(user=self.operator)
        r = self.api.post(
            "/api/v1/service-offerings/from-template/",
            {
                "template_key": "cleaning_deep",
                "name": "Deep Clean Plus",
                "slug": "deep-clean-plus",
            },
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        self.assertEqual(r.data["template_key"], "cleaning_deep")
        self.assertEqual(
            r.data["service_offering"]["name"],
            "Deep Clean Plus",
        )
        self.assertEqual(
            ServiceOffering.objects.filter(
                tenant_id=self.tenant.id,
                slug="deep-clean-plus",
            ).count(),
            1,
        )
