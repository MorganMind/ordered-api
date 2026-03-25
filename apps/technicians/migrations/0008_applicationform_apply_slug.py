# Generated manually for short public apply URLs

import secrets

from django.db import migrations, models

_ALPHABET = "abcdefghijklmnopqrstuvwxyz0123456789"
_LENGTH = 10


def _allocate_slug(apps):
    ApplicationForm = apps.get_model("technicians", "ApplicationForm")
    for _ in range(256):
        candidate = "".join(secrets.choice(_ALPHABET) for _ in range(_LENGTH))
        if not ApplicationForm.objects.filter(apply_slug=candidate).exists():
            return candidate
    raise RuntimeError("Could not allocate unique apply_slug during migration")


def backfill_apply_slugs(apps, schema_editor):
    ApplicationForm = apps.get_model("technicians", "ApplicationForm")
    for form in ApplicationForm.objects.filter(apply_slug__isnull=True).iterator():
        form.apply_slug = _allocate_slug(apps)
        form.save(update_fields=["apply_slug"])


class Migration(migrations.Migration):

    dependencies = [
        ("technicians", "0007_rename_application_form_fi_form_pos_idx_application_form_id_7d86ce_idx_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="applicationform",
            name="apply_slug",
            field=models.CharField(
                editable=False,
                help_text="Short random public URL segment for /forms/.../apply/ (set automatically).",
                max_length=16,
                null=True,
                unique=True,
            ),
        ),
        migrations.RunPython(backfill_apply_slugs, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="applicationform",
            name="apply_slug",
            field=models.CharField(
                editable=False,
                help_text="Short random public URL segment for /forms/.../apply/ (set automatically).",
                max_length=16,
                unique=True,
            ),
        ),
    ]
