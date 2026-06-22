from django.apps import AppConfig


class ComplaintsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.complaints"
    label = "complaints"
    verbose_name = "Complaints"

    def ready(self):
        import apps.complaints.signals  # noqa: F401
