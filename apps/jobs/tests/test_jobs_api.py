import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.bookings.models import Booking
from apps.jobs.models import Job, JobStatus
from apps.service_requests.models import ServiceRequest, ServiceRequestStatus, ServiceType
from apps.technicians.models import OnboardingStatus, TechnicianProfile
from apps.tenants.models import Tenant
from apps.users.models import UserRole

User = get_user_model()


class JobApiTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Acme", slug=f"acme-{uuid.uuid4().hex[:8]}")
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
        self.tech = User.objects.create_user(
            email="tech@example.com",
            password="x",
            tenant=self.tenant,
            role=UserRole.TECHNICIAN,
            first_name="T",
            last_name="Ech",
        )
        TechnicianProfile.objects.update_or_create(
            user=self.tech,
            defaults={
                "tenant": self.tenant,
                "onboarding_status": OnboardingStatus.ACTIVE,
            },
        )
        self.api = APIClient()

    def test_convert_priced_service_request_creates_job(self):
        sr = ServiceRequest.objects.create(
            tenant_id=self.tenant.id,
            client=self.client_user,
            contact_name="Pat",
            contact_phone="555",
            address_raw="1 Main",
            service_type=ServiceType.STANDARD_CLEANING,
            status=ServiceRequestStatus.PRICED,
        )
        self.api.force_authenticate(user=self.operator)
        r = self.api.post(
            f"/api/v1/service-requests/{sr.id}/convert-to-job/",
            {"title": "Custom title"},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r.data["title"], "Custom title")
        sr.refresh_from_db()
        self.assertEqual(sr.status, ServiceRequestStatus.CONVERTED)
        self.assertIsNotNone(sr.converted_job_id)
        self.assertIsNotNone(r.data.get("booking_id"))
        job = Job.objects.get(pk=sr.converted_job_id)
        self.assertIsNotNone(job.booking_id)
        self.assertTrue(Booking.objects.filter(pk=job.booking_id, tenant_id=self.tenant.id).exists())

    def test_claim_fails_without_service_request_or_booking(self):
        job = Job.objects.create(
            tenant_id=self.tenant.id,
            title="Orphan",
            status=JobStatus.OPEN,
        )
        self.api.force_authenticate(user=self.tech)
        r = self.api.post(f"/api/v1/jobs/{job.id}/claim/", {}, format="json")
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_operator_post_job_requires_booking_or_service_request(self):
        self.api.force_authenticate(user=self.operator)
        r = self.api.post("/api/v1/jobs/", {"title": "No links"}, format="json")
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_convert_fails_when_not_priced(self):
        sr = ServiceRequest.objects.create(
            tenant_id=self.tenant.id,
            client=self.client_user,
            contact_name="Pat",
            contact_phone="555",
            address_raw="1 Main",
            service_type=ServiceType.STANDARD_CLEANING,
            status=ServiceRequestStatus.NEW,
        )
        self.api.force_authenticate(user=self.operator)
        r = self.api.post(f"/api/v1/service-requests/{sr.id}/convert-to-job/", {}, format="json")
        self.assertEqual(r.status_code, status.HTTP_409_CONFLICT)

    def _minimal_sr(self, **kwargs):
        defaults = dict(
            tenant_id=self.tenant.id,
            client=self.client_user,
            contact_name="Pat",
            contact_phone="555",
            address_raw="1 Main",
            service_type=ServiceType.STANDARD_CLEANING,
            status=ServiceRequestStatus.PRICED,
        )
        defaults.update(kwargs)
        return ServiceRequest.objects.create(**defaults)

    def test_technician_sees_open_unassigned_and_assigned_jobs(self):
        sr_open = self._minimal_sr()
        open_job = Job.objects.create(
            tenant_id=self.tenant.id,
            title="Open",
            status=JobStatus.OPEN,
            service_request=sr_open,
        )
        sr_mine = self._minimal_sr()
        mine = Job.objects.create(
            tenant_id=self.tenant.id,
            title="Mine",
            status=JobStatus.ASSIGNED,
            assigned_to=self.tech,
            service_request=sr_mine,
        )
        sr_other = self._minimal_sr()
        Job.objects.create(
            tenant_id=self.tenant.id,
            title="Other",
            status=JobStatus.ASSIGNED,
            assigned_to=self.operator,
            service_request=sr_other,
        )
        self.api.force_authenticate(user=self.tech)
        r = self.api.get("/api/v1/jobs/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        ids = {row["id"] for row in r.data}
        self.assertIn(str(open_job.id), ids)
        self.assertIn(str(mine.id), ids)
        self.assertEqual(len(ids), 2)

    def test_claim_start_complete_flow(self):
        sr = self._minimal_sr()
        job = Job.objects.create(
            tenant_id=self.tenant.id,
            title="Do work",
            status=JobStatus.OPEN,
            service_request=sr,
        )
        self.api.force_authenticate(user=self.tech)
        r = self.api.post(f"/api/v1/jobs/{job.id}/claim/", {}, format="json")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["status"], JobStatus.ASSIGNED)
        self.assertIsNotNone(r.data.get("booking_id"))
        job.refresh_from_db()
        self.assertEqual(job.assigned_to_id, self.tech.id)
        self.assertIsNotNone(job.booking_id)

        r2 = self.api.post(f"/api/v1/jobs/{job.id}/start/", {}, format="json")
        self.assertEqual(r2.status_code, status.HTTP_200_OK)
        self.assertEqual(r2.data["status"], JobStatus.IN_PROGRESS)

        r3 = self.api.post(f"/api/v1/jobs/{job.id}/complete/", {}, format="json")
        self.assertEqual(r3.status_code, status.HTTP_200_OK)
        self.assertEqual(r3.data["status"], JobStatus.COMPLETED)

    def test_operator_post_creates_job(self):
        sr = self._minimal_sr()
        self.api.force_authenticate(user=self.operator)
        r = self.api.post(
            "/api/v1/jobs/",
            {"title": "Manual job", "service_request": str(sr.id)},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r.data["title"], "Manual job")
        self.assertEqual(r.data["status"], JobStatus.OPEN)
        self.assertIsNone(r.data.get("assigned_to"))
        self.assertIsNotNone(r.data.get("booking_id"))

    def test_operator_patch_assigns_technician(self):
        sr = self._minimal_sr()
        job = Job.objects.create(
            tenant_id=self.tenant.id,
            title="Assigned by op",
            status=JobStatus.OPEN,
            service_request=sr,
        )
        self.api.force_authenticate(user=self.operator)
        r = self.api.patch(
            f"/api/v1/jobs/{job.id}/",
            {"assigned_to": str(self.tech.id)},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["assigned_to"], str(self.tech.id))
        self.assertEqual(r.data["status"], JobStatus.ASSIGNED)
        self.assertIsNotNone(r.data.get("booking_id"))

    def test_transitions_open_job(self):
        sr = self._minimal_sr()
        job = Job.objects.create(
            tenant_id=self.tenant.id,
            title="T",
            status=JobStatus.OPEN,
            service_request=sr,
        )
        self.api.force_authenticate(user=self.operator)
        r = self.api.get(f"/api/v1/jobs/{job.id}/transitions/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIn("assigned", r.data["allowed_transitions"])
        self.assertIn("cancelled", r.data["allowed_transitions"])
        names = {t["name"] for t in r.data["transitions"]}
        self.assertEqual(names, {"assign", "cancel", "claim"})
