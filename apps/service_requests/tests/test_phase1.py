from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.pricing.models import PriceSnapshot
from apps.service_requests.models import ServiceRequest, ServiceRequestStatus, ServiceType
from apps.tenants.models import Tenant


User = get_user_model()


class ServiceRequestPhase1Tests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Acme", slug="acme")
        self.client_user = User.objects.create_user(
            username="client1", email="client1@example.com", password="x"
        )
        self.client_user.tenant_id = self.tenant.id

        self.operator = User.objects.create_user(
            username="op1", email="op1@example.com", password="x"
        )
        self.operator.tenant_id = self.tenant.id
        self.operator.is_tenant_operator = True

        self.api = APIClient()

    def _create_sr_via_api(self, user, **extra):
        self.api.force_authenticate(user=user)
        body = {
            "contact_name": "Pat",
            "contact_phone": "555-0100",
            "address_raw": "123 Main",
            "service_type": ServiceType.STANDARD_CLEANING,
            **extra,
        }
        r = self.api.post("/api/v1/service-requests/", body, format="json")
        return r

    def test_create_requires_phone_or_email(self):
        r = self._create_sr_via_api(
            self.client_user,
            contact_phone="",
            contact_email="",
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_sets_source_api_server_side(self):
        r = self._create_sr_via_api(
            self.client_user,
            **{"source": "import"},
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        sr = ServiceRequest.objects.get(pk=r.data["id"])
        self.assertEqual(sr.source, "api")

    def test_timing_preference_date_range_validated(self):
        self.api.force_authenticate(user=self.client_user)
        r = self.api.post(
            "/api/v1/service-requests/",
            {
                "contact_name": "Pat",
                "contact_phone": "555",
                "address_raw": "1 Main",
                "service_type": ServiceType.DEEP_CLEAN,
                "timing_preference": {
                    "date_range_start": "2025-08-31",
                    "date_range_end": "2025-08-01",
                },
            },
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_media_refs_shape(self):
        self.api.force_authenticate(user=self.client_user)
        r = self.api.post(
            "/api/v1/service-requests/",
            {
                "contact_name": "Pat",
                "contact_email": "p@example.com",
                "address_raw": "1 Main",
                "service_type": ServiceType.OTHER,
                "media_refs": [{"type": "image", "storage_key": "k"}],
            },
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)

    def test_client_cannot_see_operator_notes(self):
        sr = ServiceRequest.objects.create(
            tenant_id=self.tenant.id,
            client=self.client_user,
            contact_name="Pat",
            contact_phone="1",
            address_raw="x",
            service_type=ServiceType.OTHER,
            internal_operator_notes="secret",
        )
        self.api.force_authenticate(user=self.client_user)
        r = self.api.get(f"/api/v1/service-requests/{sr.id}/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertNotIn("internal_operator_notes", r.data)

    def test_operator_sees_operator_notes(self):
        sr = ServiceRequest.objects.create(
            tenant_id=self.tenant.id,
            client=self.client_user,
            contact_name="Pat",
            contact_phone="1",
            address_raw="x",
            service_type=ServiceType.OTHER,
            internal_operator_notes="visible",
        )
        self.api.force_authenticate(user=self.operator)
        r = self.api.get(f"/api/v1/service-requests/{sr.id}/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data.get("internal_operator_notes"), "visible")

    def test_client_cannot_patch(self):
        sr = ServiceRequest.objects.create(
            tenant_id=self.tenant.id,
            client=self.client_user,
            contact_name="Pat",
            contact_phone="1",
            address_raw="x",
            service_type=ServiceType.OTHER,
        )
        self.api.force_authenticate(user=self.client_user)
        r = self.api.patch(
            f"/api/v1/service-requests/{sr.id}/",
            {"notes": "nope"},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_status_transition_guard(self):
        sr = ServiceRequest.objects.create(
            tenant_id=self.tenant.id,
            client=self.client_user,
            contact_name="Pat",
            contact_phone="1",
            address_raw="x",
            service_type=ServiceType.OTHER,
            status=ServiceRequestStatus.CONVERTED,
        )
        self.api.force_authenticate(user=self.operator)
        r = self.api.post(
            f"/api/v1/service-requests/{sr.id}/status/",
            {"status": ServiceRequestStatus.NEW},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_price_moves_reviewing_to_priced(self):
        sr = ServiceRequest.objects.create(
            tenant_id=self.tenant.id,
            client=self.client_user,
            contact_name="Pat",
            contact_phone="1",
            address_raw="x",
            service_type=ServiceType.OTHER,
            status=ServiceRequestStatus.REVIEWING,
        )
        self.api.force_authenticate(user=self.operator)
        r = self.api.post(f"/api/v1/service-requests/{sr.id}/price/", {}, format="json")
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        sr.refresh_from_db()
        self.assertEqual(sr.status, ServiceRequestStatus.PRICED)
        self.assertIsNotNone(sr.latest_price_snapshot_id)

    def test_price_returns_409_when_not_priceable(self):
        sr = ServiceRequest.objects.create(
            tenant_id=self.tenant.id,
            client=self.client_user,
            contact_name="Pat",
            contact_phone="1",
            address_raw="x",
            service_type=ServiceType.OTHER,
            status=ServiceRequestStatus.PRICED,
        )
        self.api.force_authenticate(user=self.operator)
        r = self.api.post(f"/api/v1/service-requests/{sr.id}/price/", {}, format="json")
        self.assertEqual(r.status_code, status.HTTP_409_CONFLICT)

    def test_client_cannot_retrieve_other_clients_request(self):
        other = User.objects.create_user(
            username="client2", email="client2@example.com", password="x"
        )
        other.tenant_id = self.tenant.id
        sr = ServiceRequest.objects.create(
            tenant_id=self.tenant.id,
            client=other,
            contact_name="Pat",
            contact_phone="1",
            address_raw="x",
            service_type=ServiceType.OTHER,
        )
        self.api.force_authenticate(user=self.client_user)
        r = self.api.get(f"/api/v1/service-requests/{sr.id}/")
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)

    def test_clear_latest_on_snapshot_delete(self):
        sr = ServiceRequest.objects.create(
            tenant_id=self.tenant.id,
            client=self.client_user,
            contact_name="Pat",
            contact_phone="1",
            address_raw="x",
            service_type=ServiceType.OTHER,
        )
        snap = PriceSnapshot.objects.create(
            tenant_id=self.tenant.id,
            service_request=sr,
            total_cents=100,
            subtotal_cents=100,
        )
        sr.latest_price_snapshot = snap
        sr.save(update_fields=["latest_price_snapshot", "updated_at"])
        snap.delete()
        sr.refresh_from_db()
        self.assertIsNone(sr.latest_price_snapshot_id)

    def test_model_clean_requires_phone_or_email(self):
        sr = ServiceRequest(
            tenant_id=self.tenant.id,
            client=self.client_user,
            contact_name="Pat",
            contact_phone="",
            contact_email="",
            address_raw="x",
            service_type=ServiceType.OTHER,
        )
        with self.assertRaises(ValidationError):
            sr.full_clean()

    def test_pricing_service_sets_latest_pointer(self):
        sr = ServiceRequest.objects.create(
            tenant_id=self.tenant.id,
            client=self.client_user,
            contact_name="Pat",
            contact_phone="1",
            address_raw="x",
            service_type=ServiceType.OTHER,
        )
        from apps.pricing.services import create_price_snapshot_from_service_request

        snap = create_price_snapshot_from_service_request(sr)
        sr.refresh_from_db()
        self.assertEqual(sr.latest_price_snapshot_id, snap.id)
        self.assertEqual(snap.service_request_id, sr.id)
