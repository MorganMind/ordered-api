# Generated manually for ApplicationForm + TechnicianApplication.application_form

import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0002_alter_tenant_timezone"),
        ("technicians", "0002_application_conversion_audit"),
    ]

    operations = [
        migrations.CreateModel(
            name="ApplicationForm",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "title",
                    models.CharField(
                        help_text="Internal/display title (e.g. 'Summer 2025 Hiring Drive')",
                        max_length=255,
                    ),
                ),
                (
                    "slug",
                    models.SlugField(
                        blank=True,
                        help_text="URL-friendly identifier. Auto-generated if blank.",
                        max_length=150,
                    ),
                ),
                (
                    "description",
                    models.TextField(
                        blank=True,
                        help_text="Optional description shown to applicants or used internally.",
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("draft", "Draft"),
                            ("active", "Active"),
                            ("archived", "Archived"),
                        ],
                        db_index=True,
                        default="draft",
                        max_length=20,
                    ),
                ),
                (
                    "settings",
                    models.JSONField(
                        blank=True,
                        default=dict,
                        help_text=(
                            "Form-level settings. Reserved keys: "
                            "{'duplicate_check_hours': 24, 'confirmation_message': '...', "
                            "'redirect_url': '...'}"
                        ),
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "tenant",
                    models.ForeignKey(
                        db_index=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="application_forms",
                        to="tenants.tenant",
                    ),
                ),
            ],
            options={
                "db_table": "application_forms",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="applicationform",
            index=models.Index(
                fields=["tenant", "status", "-created_at"],
                name="application_tenant_i_7a8b2c_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="applicationform",
            index=models.Index(
                fields=["tenant", "slug"],
                name="application_tenant_i_9d0e1f_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="applicationform",
            constraint=models.UniqueConstraint(
                condition=models.Q(slug__gt=""),
                fields=("tenant", "slug"),
                name="unique_application_form_slug_per_tenant",
            ),
        ),
        migrations.AddField(
            model_name="technicianapplication",
            name="application_form",
            field=models.ForeignKey(
                blank=True,
                help_text="The form definition this application was submitted against.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="applications",
                to="technicians.applicationform",
            ),
        ),
        migrations.AddIndex(
            model_name="technicianapplication",
            index=models.Index(
                fields=["application_form", "status", "-created_at"],
                name="technician_applicatio_af_idx",
            ),
        ),
    ]
