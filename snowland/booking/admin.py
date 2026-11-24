from django.contrib import admin

from .models import Reservation, ReservationGroup
from .order_archive import SCOPES


class ArchiveVisibilityFilter(admin.SimpleListFilter):
    title = '封存狀態'
    parameter_name = 'archive'

    def lookups(self, request, model_admin):
        return [('all', '含已刪除'), ('deleted', '僅已刪除')]

    def queryset(self, request, queryset):
        if self.value() == 'all':
            return queryset
        if self.value() == 'deleted':
            return queryset.exclude(pk__in=queryset.live().order_by().values('pk'))
        return queryset.live()


class ArchivedOrderAdmin(admin.ModelAdmin):
    list_display = ['pk', 'is_deleted', 'deleted_at']
    actions = None
    readonly_fields = ['is_deleted', 'deleted_at', 'deleted_by']

    def get_queryset(self, request):
        if request.user.is_superuser:
            return self.model.all_objects.all()
        return super().get_queryset(request).live()

    def get_list_filter(self, request):
        return [ArchiveVisibilityFilter] if request.user.is_superuser else []

    def has_delete_permission(self, request, obj=None):
        return False

    def is_archived(self, obj):
        return obj is not None and (
            obj.is_deleted or not self.model.all_objects.live().filter(pk=obj.pk).exists()
        )

    def has_change_permission(self, request, obj=None):
        return not self.is_archived(obj) and super().has_change_permission(request, obj)

    def get_readonly_fields(self, request, obj=None):
        if self.is_archived(obj):
            return [field.name for field in (*self.model._meta.fields, *self.model._meta.many_to_many)]
        return super().get_readonly_fields(request, obj)


class ReservationInline(admin.TabularInline):
    model = Reservation
    extra = 0
    fields = ['group', 'course_type', 'status', 'preferred_coach']
    can_delete = False

    def get_queryset(self, request):
        return super().get_queryset(request).live()


class PlatformArchiveAdmin(ArchivedOrderAdmin):
    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(ReservationGroup)
class ReservationGroupAdmin(ArchivedOrderAdmin):
    list_display = ['id', 'name', 'user', 'created_at', 'is_deleted', 'deleted_at']
    inlines = [ReservationInline]

    def get_list_filter(self, request):
        filters = super().get_list_filter(request)
        return [*filters, 'client'] if request.user.is_superuser else filters

    def get_inlines(self, request, obj=None):
        return [] if self.is_archived(obj) else super().get_inlines(request, obj)


for scope in SCOPES:
    if scope.model is not ReservationGroup:
        admin_class = ArchivedOrderAdmin if scope.model._meta.model_name in {
            'reservation', 'booking', 'memberdetail', 'payment',
        } else PlatformArchiveAdmin
        admin.site.register(scope.model, admin_class)
