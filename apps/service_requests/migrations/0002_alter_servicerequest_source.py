# Generated manually — default intake source for API-created rows is API.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("service_requests", "0001_service_request_domain"),
    ]

    operations = [
        migrations.AlterField(
            model_name="servicerequest",
            name="source",
            field=models.CharField(
                choices=[("form", "Form"), ("api", "API"), ("import", "Import")],
                db_index=True,
                default="api",
                max_length=20,
            ),
        ),
    ]
