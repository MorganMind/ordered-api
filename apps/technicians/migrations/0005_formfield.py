# Generated manually for FormField model

import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        (
            "technicians",
            "0004_rename_application_tenant_i_7a8b2c_idx_application_tenant__d68dde_idx_and_more",
        ),
    ]

    operations = [
        migrations.CreateModel(
            name="FormField",
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
                    "field_key",
                    models.SlugField(
                        help_text=(
                            "Stable machine key used in answers JSON. "
                            "Must be unique within the form and must not "
                            "change after first submission."
                        ),
                        max_length=120,
                    ),
                ),
                (
                    "label",
                    models.CharField(
                        help_text="Human-readable field label shown to the applicant.",
                        max_length=255,
                    ),
                ),
                (
                    "description",
                    models.TextField(
                        blank=True,
                        help_text="Optional helper text displayed below the label.",
                    ),
                ),
                (
                    "field_type",
                    models.CharField(
                        choices=[
                            ("text", "Text"),
                            ("textarea", "Text Area"),
                            ("email", "Email"),
                            ("phone", "Phone"),
                            ("number", "Number"),
                            ("checkbox", "Checkbox"),
                            ("select", "Single Select (Dropdown)"),
                            ("multi_select", "Multi Select"),
                            ("radio", "Radio Buttons"),
                            ("date", "Date"),
                            ("url", "URL"),
                            ("file_upload", "File Upload"),
                        ],
                        default="text",
                        max_length=30,
                    ),
                ),
                (
                    "required",
                    models.BooleanField(
                        default=False,
                        help_text="Whether this field must be filled in for a valid submission.",
                    ),
                ),
                (
                    "position",
                    models.PositiveIntegerField(
                        db_index=True,
                        default=0,
                        help_text="Sort order within the form (ascending).",
                    ),
                ),
                (
                    "options",
                    models.JSONField(
                        blank=True,
                        default=list,
                        help_text=(
                            'Choices for select / multi_select / radio. '
                            'List of {"label": "...", "value": "..."} dicts.'
                        ),
                    ),
                ),
                (
                    "validations",
                    models.JSONField(
                        blank=True,
                        default=dict,
                        help_text="Field-level validation rules.",
                    ),
                ),
                (
                    "default_value",
                    models.JSONField(
                        blank=True,
                        null=True,
                        help_text="Optional default value pre-filled for the applicant.",
                    ),
                ),
                (
                    "placeholder",
                    models.CharField(
                        blank=True,
                        help_text="Placeholder text for text-like inputs.",
                        max_length=255,
                    ),
                ),
                (
                    "visible",
                    models.BooleanField(
                        default=True,
                        help_text="If False the field is hidden from the public form but kept in schema.",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "form",
                    models.ForeignKey(
                        db_index=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="fields",
                        to="technicians.applicationform",
                    ),
                ),
            ],
            options={
                "db_table": "application_form_fields",
                "ordering": ["position", "created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="formfield",
            index=models.Index(
                fields=["form", "position"],
                name="application_form_fi_form_pos_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="formfield",
            constraint=models.UniqueConstraint(
                fields=("form", "field_key"),
                name="unique_field_key_per_form",
            ),
        ),
    ]
