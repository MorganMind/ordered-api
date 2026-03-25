"""
Integration tests for application forms with custom fields and public apply.
"""

from unittest.mock import patch

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.tenants.models import Tenant, TenantStatus
from apps.users.models import User
from apps.technicians.models import (
    ApplicationForm,
    ApplicationFormStatus,
    FormField,
    FormFieldType,
    TechnicianApplication,
)


class TestApplicationFormFieldsAPI(TestCase):
    """Admin API: forms with nested ``fields_schema``."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name="Test Tenant", slug="test-tenant")
        self.admin = User.objects.create_user(
            email="admin@test.com",
            password="testpass123",
            tenant=self.tenant,
            is_staff=True,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)

    def _url(self, pk=None):
        base = "/api/v1/admin/application-forms/"
        if pk:
            return f"{base}{pk}/"
        return base

    def test_create_form_with_fields(self):
        data = {
            "title": "Summer 2025 Hiring",
            "status": "draft",
            "fields_schema": [
                {
                    "field_key": "full_name",
                    "label": "Full Name",
                    "field_type": "text",
                    "required": True,
                    "position": 0,
                    "validations": {"min_length": 2, "max_length": 100},
                },
                {
                    "field_key": "experience_years",
                    "label": "Years of Experience",
                    "field_type": "number",
                    "required": False,
                    "position": 1,
                    "validations": {"min_value": 0, "max_value": 50},
                },
                {
                    "field_key": "service_types",
                    "label": "Service Types",
                    "field_type": "multi_select",
                    "required": True,
                    "position": 2,
                    "options": [
                        {"label": "Standard Clean", "value": "standard"},
                        {"label": "Deep Clean", "value": "deep"},
                        {"label": "Move-out Clean", "value": "move_out"},
                    ],
                },
                {
                    "field_key": "has_vehicle",
                    "label": "Do you have your own vehicle?",
                    "field_type": "checkbox",
                    "required": False,
                    "position": 3,
                },
                {
                    "field_key": "start_date",
                    "label": "Available Start Date",
                    "field_type": "date",
                    "required": True,
                    "position": 4,
                },
            ],
        }
        resp = self.client.post(self._url(), data, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)

        form = ApplicationForm.objects.get(id=resp.data["id"])
        self.assertEqual(form.fields.count(), 5)
        self.assertEqual(resp.data.get("apply_slug"), form.apply_slug)
        self.assertEqual(len(form.apply_slug), 10)
        self.assertEqual(form.fields.filter(required=True).count(), 3)

    def test_create_form_without_fields(self):
        data = {"title": "Simple Form", "status": "draft"}
        resp = self.client.post(self._url(), data, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        form = ApplicationForm.objects.get(id=resp.data["id"])
        self.assertEqual(form.fields.count(), 0)

    def test_create_form_rejects_duplicate_field_keys(self):
        data = {
            "title": "Dupe Keys Form",
            "fields_schema": [
                {"field_key": "name", "label": "Name", "field_type": "text"},
                {"field_key": "name", "label": "Name Again", "field_type": "text"},
            ],
        }
        resp = self.client.post(self._url(), data, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_select_without_options_rejected(self):
        data = {
            "title": "Bad Select",
            "fields_schema": [
                {
                    "field_key": "choice",
                    "label": "Pick one",
                    "field_type": "select",
                    "options": [],
                },
            ],
        }
        resp = self.client.post(self._url(), data, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_retrieve_form_includes_fields(self):
        data = {
            "title": "Retrieve Test",
            "fields_schema": [
                {
                    "field_key": "name",
                    "label": "Name",
                    "field_type": "text",
                    "required": True,
                },
            ],
        }
        create_resp = self.client.post(self._url(), data, format="json")
        form_id = create_resp.data["id"]

        resp = self.client.get(self._url(form_id))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("fields_schema", resp.data)
        self.assertIn("hidden_fields", resp.data)
        self.assertEqual(len(resp.data["fields_schema"]), 1)
        self.assertEqual(resp.data["fields_schema"][0]["field_key"], "name")
        self.assertEqual(resp.data["hidden_fields"], [])
        self.assertIn("schema_version", resp.data)

    def test_update_form_add_fields(self):
        create_data = {
            "title": "Update Test",
            "fields_schema": [
                {"field_key": "name", "label": "Name", "field_type": "text"},
            ],
        }
        create_resp = self.client.post(self._url(), create_data, format="json")
        form_id = create_resp.data["id"]
        existing_field_id = FormField.objects.get(
            form_id=form_id, field_key="name"
        ).id

        update_data = {
            "fields_schema": [
                {
                    "id": str(existing_field_id),
                    "field_key": "name",
                    "label": "Full Name",
                    "field_type": "text",
                },
                {
                    "field_key": "email",
                    "label": "Email",
                    "field_type": "email",
                    "required": True,
                },
            ],
        }
        resp = self.client.patch(self._url(form_id), update_data, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        form = ApplicationForm.objects.get(id=form_id)
        self.assertEqual(form.fields.count(), 2)
        name_field = form.fields.get(field_key="name")
        self.assertEqual(name_field.label, "Full Name")

    def test_update_form_remove_field(self):
        create_data = {
            "title": "Remove Field Test",
            "fields_schema": [
                {"field_key": "a", "label": "A", "field_type": "text"},
                {"field_key": "b", "label": "B", "field_type": "text"},
            ],
        }
        create_resp = self.client.post(self._url(), create_data, format="json")
        form_id = create_resp.data["id"]

        field_a = FormField.objects.get(form_id=form_id, field_key="a")

        update_data = {
            "fields_schema": [
                {
                    "id": str(field_a.id),
                    "field_key": "a",
                    "label": "A",
                    "field_type": "text",
                },
            ],
        }
        resp = self.client.patch(self._url(form_id), update_data, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(FormField.objects.filter(form_id=form_id).count(), 1)

    def test_update_without_fields_leaves_them_unchanged(self):
        create_data = {
            "title": "No Field Change",
            "fields_schema": [
                {"field_key": "name", "label": "Name", "field_type": "text"},
            ],
        }
        create_resp = self.client.post(self._url(), create_data, format="json")
        form_id = create_resp.data["id"]

        resp = self.client.patch(
            self._url(form_id), {"title": "Renamed"}, format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        form = ApplicationForm.objects.get(id=form_id)
        self.assertEqual(form.title, "Renamed")
        self.assertEqual(form.fields.count(), 1)

    def test_list_includes_field_count(self):
        create_data = {
            "title": "List Test",
            "fields_schema": [
                {"field_key": "a", "label": "A", "field_type": "text"},
                {"field_key": "b", "label": "B", "field_type": "text"},
            ],
        }
        self.client.post(self._url(), create_data, format="json")

        resp = self.client.get(self._url())
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        if isinstance(resp.data, list):
            forms = resp.data
        else:
            forms = resp.data.get("results", resp.data)
        if isinstance(forms, list):
            form_data = forms[0]
        else:
            form_data = forms
        self.assertIn("field_count", form_data)

    def test_option_normalization_plain_strings(self):
        data = {
            "title": "Normalise Test",
            "fields_schema": [
                {
                    "field_key": "color",
                    "label": "Favorite Color",
                    "field_type": "select",
                    "options": ["Red", "Blue", "Green"],
                },
            ],
        }
        resp = self.client.post(self._url(), data, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

        field = FormField.objects.get(form__id=resp.data["id"], field_key="color")
        self.assertEqual(len(field.options), 3)
        self.assertEqual(field.options[0], {"label": "Red", "value": "Red"})

    def test_list_form_templates(self):
        resp = self.client.get("/api/v1/admin/application-forms/templates/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["templates"])
        self.assertEqual(
            resp.data["templates"][0]["key"],
            "cleaning_technician_intake_v1",
        )

    def test_create_form_from_template(self):
        resp = self.client.post(
            "/api/v1/admin/application-forms/from-template/",
            {
                "template_key": "cleaning_technician_intake_v1",
                "title": "Cleaning Intake v1",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        form = ApplicationForm.objects.get(id=resp.data["form"]["id"])
        self.assertEqual(form.title, "Cleaning Intake v1")
        self.assertGreater(form.fields.count(), 0)
        county = form.fields.get(field_key="county")
        self.assertEqual(county.field_type, FormFieldType.TEXT)

    def test_create_form_from_scratch_action(self):
        resp = self.client.post(
            "/api/v1/admin/application-forms/from-scratch/",
            {
                "title": "Scratch Form",
                "fields_schema": [
                    {
                        "field_key": "custom_question",
                        "label": "Custom",
                        "field_type": "text",
                    }
                ],
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertEqual(resp.data["source"], "scratch")


class TestPublicFormSubmissionWithCustomFields(TestCase):
    """Public GET/POST ``/api/v1/forms/{apply_slug}/apply/`` (UUID still accepted)."""

    def setUp(self):
        self.tenant = Tenant.objects.create(
            name="Public Tenant",
            slug="public-tenant",
            status=TenantStatus.ACTIVE,
        )
        self.form = ApplicationForm.objects.create(
            tenant=self.tenant,
            title="Public Hiring Form",
            slug="public-hiring",
            status=ApplicationFormStatus.ACTIVE,
        )
        self.tenant.logo_url = "https://cdn.example.com/tenant-logo.png"
        self.tenant.save(update_fields=["logo_url"])
        FormField.objects.create(
            form=self.form,
            field_key="full_name",
            label="Full Name",
            field_type=FormFieldType.TEXT,
            required=True,
            position=0,
            validations={"min_length": 2},
        )
        FormField.objects.create(
            form=self.form,
            field_key="service_type",
            label="Service Type",
            field_type=FormFieldType.SELECT,
            required=True,
            position=1,
            options=[
                {"label": "Standard", "value": "standard"},
                {"label": "Deep", "value": "deep"},
            ],
        )
        FormField.objects.create(
            form=self.form,
            field_key="available",
            label="Available?",
            field_type=FormFieldType.CHECKBOX,
            required=False,
            position=2,
        )

        self.client = APIClient()
        self.form.refresh_from_db()

    def _url(self):
        return f"/api/v1/forms/{self.form.apply_slug}/apply/"

    def test_get_returns_form_schema(self):
        resp = self.client.get(self._url())
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("fields_schema", resp.data)
        self.assertEqual(len(resp.data["fields_schema"]), 3)
        keys = [f["field_key"] for f in resp.data["fields_schema"]]
        self.assertEqual(keys, ["full_name", "service_type", "available"])
        self.assertIn("public_branding", resp.data)
        self.assertEqual(resp.data.get("apply_slug"), self.form.apply_slug)
        self.assertEqual(resp.data["public_branding"]["name"], self.tenant.name)
        self.assertEqual(
            resp.data["public_branding"]["logo_url"],
            "https://cdn.example.com/tenant-logo.png",
        )

    @patch("apps.technicians.views.notify_application_submitted")
    def test_submit_valid_answers(self, mock_notify):
        data = {
            "first_name": "Alice",
            "last_name": "Smith",
            "email": "alice@example.com",
            "answers": {
                "full_name": "Alice Smith",
                "service_type": "standard",
                "available": True,
            },
        }
        resp = self.client.post(self._url(), data, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        mock_notify.assert_called_once()

    def test_submit_missing_required_answer(self):
        data = {
            "first_name": "Bob",
            "email": "bob@example.com",
            "answers": {
                "service_type": "deep",
            },
        }
        resp = self.client.post(self._url(), data, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_submit_invalid_select_option(self):
        data = {
            "first_name": "Carol",
            "email": "carol@example.com",
            "answers": {
                "full_name": "Carol Jones",
                "service_type": "nonexistent",
            },
        }
        resp = self.client.post(self._url(), data, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_submit_unknown_answer_key(self):
        data = {
            "first_name": "Dave",
            "email": "dave@example.com",
            "answers": {
                "full_name": "Dave Lee",
                "service_type": "standard",
                "hacker_field": "injected",
            },
        }
        resp = self.client.post(self._url(), data, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_submit_with_no_answers_when_required_fields_exist(self):
        data = {
            "first_name": "Eve",
            "email": "eve@example.com",
        }
        resp = self.client.post(self._url(), data, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_submit_form_with_no_custom_fields(self):
        empty_form = ApplicationForm.objects.create(
            tenant=self.tenant,
            title="No Fields Form",
            slug="no-fields",
            status=ApplicationFormStatus.ACTIVE,
        )
        empty_form.refresh_from_db()
        url = f"/api/v1/forms/{empty_form.apply_slug}/apply/"
        data = {
            "first_name": "Frank",
            "email": "frank@example.com",
        }
        resp = self.client.post(url, data, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_schema_version_recorded(self):
        data = {
            "first_name": "Grace",
            "email": "grace@example.com",
            "answers": {
                "full_name": "Grace Hopper",
                "service_type": "deep",
            },
        }
        resp = self.client.post(self._url(), data, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

        app = TechnicianApplication.objects.get(email="grace@example.com")
        self.assertIsNotNone(app.schema_version)
        self.assertGreater(app.schema_version, 0)
        self.assertIn("field_schema_snapshot", app.metadata)
        self.assertEqual(len(app.metadata["field_schema_snapshot"]), 3)

    def test_public_apply_accepts_legacy_uuid_in_path(self):
        url = f"/api/v1/forms/{self.form.id}/apply/"
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data.get("apply_slug"), self.form.apply_slug)

    def test_public_apply_nonexistent_uuid_returns_404(self):
        resp = self.client.get(
            "/api/v1/forms/00000000-0000-4000-8000-000000000099/apply/"
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_public_apply_slug_too_long_returns_404(self):
        resp = self.client.get(
            "/api/v1/forms/abcdefghijklmnopqrstu/apply/"
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_public_apply_invalid_characters_in_ref_returns_404(self):
        resp = self.client.get("/api/v1/forms/bad!slug/apply/")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
