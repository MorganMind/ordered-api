import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("jobs", "0005_fix_job_created_by_uuid_fk"),
    ]

    operations = [
        migrations.AddField(
            model_name="job",
            name="assigned_to",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="assigned_jobs",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
