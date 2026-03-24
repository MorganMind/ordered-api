# Generated manually for operator application-notification email.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0002_alter_tenant_timezone"),
    ]

    operations = [
        migrations.AddField(
            model_name="tenant",
            name="operator_admin_email",
            field=models.EmailField(
                blank=True,
                default="",
                help_text="Receives a notification when someone submits a technician application (public form). Leave blank to skip operator copy.",
                max_length=254,
            ),
        ),
    ]
