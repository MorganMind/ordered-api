from django.apps import AppConfig


class TechniciansConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.technicians"
    verbose_name = "Technicians"

    def ready(self):
        import apps.technicians.inbox_admin  # noqa: F401
        import apps.technicians.signals  # noqa: F401
