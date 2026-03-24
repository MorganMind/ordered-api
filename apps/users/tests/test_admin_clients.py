from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.service_requests.models import ServiceRequest, ServiceType
from apps.tenants.models import Tenant, TenantStatus
from apps.users.models import User, UserRole, UserStatus


class ClientAdminAPITests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(
            name="T",
            slug="t-clients-api",
            status=TenantStatus.ACTIVE,
        )
        self.other_tenant = Tenant.objects.create(
            name="Other",
            slug="other-clients-api",
            status=TenantStatus.ACTIVE,
        )
        self.staff = User.objects.create_user(
            email="staff@example.com",
            password="x",
            tenant=self.tenant,
            is_staff=True,
            role=UserRole.ADMIN,
        )
        self.client_user_a = User.objects.create_user(
            email="alice@example.com",
            password="x",
            tenant=self.tenant,
            role=UserRole.CLIENT,
            first_name="Alice",
            last_name="Nguyen",
        )
        self.client_user_b = User.objects.create_user(
            email="bob@example.com",
            password="x",
            tenant=self.tenant,
            role=UserRole.CLIENT,
            status=UserStatus.INACTIVE,
        )
        User.objects.create_user(
            email="other@example.com",
            password="x",
            tenant=self.other_tenant,
            role=UserRole.CLIENT,
        )
        ServiceRequest.objects.create(
            tenant=self.tenant,
            client=self.client_user_a,
            contact_name="Alice Nguyen",
            address_raw="123 Main St",
            service_type=ServiceType.STANDARD_CLEANING,
        )
        self.api = APIClient()
        self.list_url = "/api/v1/admin/clients/"

    def test_non_staff_forbidden(self):
        op = User.objects.create_user(
            email="op@example.com",
            password="x",
            tenant=self.tenant,
            role=UserRole.ADMIN,
            is_staff=False,
        )
        self.api.force_authenticate(user=op)
        r = self.api.get(self.list_url)
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_list_tenant_scoped_with_counts(self):
        self.api.force_authenticate(user=self.staff)
        r = self.api.get(self.list_url)
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(len(r.data), 2)
        emails = {row["email"] for row in r.data}
        self.assertEqual(emails, {"alice@example.com", "bob@example.com"})
        alice = next(x for x in r.data if x["email"] == "alice@example.com")
        self.assertEqual(alice["service_request_count"], 1)
        self.assertEqual(alice["jobs_created_count"], 0)

    def test_filter_status(self):
        self.api.force_authenticate(user=self.staff)
        r = self.api.get(self.list_url, {"status": UserStatus.INACTIVE})
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(len(r.data), 1)
        self.assertEqual(r.data[0]["email"], "bob@example.com")

    def test_retrieve_detail(self):
        self.api.force_authenticate(user=self.staff)
        r = self.api.get(f"{self.list_url}{self.client_user_a.id}/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["email"], "alice@example.com")
        self.assertEqual(r.data["role"], "client")
        self.assertEqual(r.data["service_request_count"], 1)
