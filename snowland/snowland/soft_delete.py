from django.conf import settings
from django.db import models
from django.db.models import Q
from django.db.models.deletion import ProtectedError


class SoftDeleteQuerySet(models.QuerySet):
    def live(self):
        return self.filter(self.model.live_filter())


class SoftDeleteManager(models.Manager.from_queryset(SoftDeleteQuerySet)):
    """Unfiltered manager for historical relationships and batch operations."""


class LiveManager(SoftDeleteManager):
    def get_queryset(self):
        return super().get_queryset().live()


class SoftDeleteModel(models.Model):
    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="+",
    )

    # Explicit to support multiple parent chains and nullable relationships.
    soft_delete_parents = ()

    objects = LiveManager()
    all_objects = SoftDeleteManager()

    @classmethod
    def live_filter(cls, relation=""):
        prefix = f"{relation}__" if relation else ""
        visible = Q(**{f"{prefix}is_deleted": False})
        for path in cls.soft_delete_parents:
            # An absent optional parent does not archive the row.
            visible &= ~Q(**{f"{prefix}{path}__is_deleted": True})
        return visible

    class Meta:
        abstract = True
        base_manager_name = "all_objects"
        default_manager_name = "objects"


def protect_archived_row(sender, instance, **kwargs):
    if instance.is_deleted:
        raise ProtectedError("已封存的紀錄須保留，包含透過其他物件的級聯刪除", [instance])
