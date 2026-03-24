from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0003_tenant_operator_admin_email"),
    ]

    operations = [
        migrations.AddField(
            model_name="tenant",
            name="logo_url",
            field=models.URLField(
                blank=True,
                help_text="Public URL for workspace/organization logo (upload via API or external CDN).",
                max_length=2048,
                null=True,
            ),
        ),
    ]
