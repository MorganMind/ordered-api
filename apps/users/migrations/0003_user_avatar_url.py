from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0002_user_skills"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="avatar_url",
            field=models.URLField(
                blank=True,
                help_text="Public or app-served URL for profile photo (all roles).",
                max_length=2048,
                null=True,
            ),
        ),
    ]
