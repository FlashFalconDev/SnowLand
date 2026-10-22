from django.apps import AppConfig


class CoachConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "Coach"

    def ready(self):
        from . import signals  # noqa: F401
