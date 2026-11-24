from django.apps import AppConfig


class BookingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "booking"

    def ready(self):
        from django.db.models.signals import pre_delete
        from snowland.soft_delete import SoftDeleteModel, protect_archived_row

        from . import signals  # noqa: F401

        for model in self.apps.get_models():
            if issubclass(model, SoftDeleteModel):
                pre_delete.connect(protect_archived_row, sender=model, dispatch_uid="protect_archived_row")
