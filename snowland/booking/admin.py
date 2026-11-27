from django import forms
from django.contrib import admin
from django.db.models import FileField

from .media_files import PrivateCourseMediaStorage
from .models import (
    InsuranceLedgerEntry, InsurancePrepaidAccount, InsuranceReconciliation, Reservation, ReservationGroup,
)
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


def private_file_name(field):
    @admin.display(description=field.verbose_name)
    def display(obj):
        name = getattr(obj, field.name).name
        return name.rsplit('/', 1)[-1] if name else None

    return display


class ArchivedOrderAdmin(admin.ModelAdmin):
    list_display = ['pk', 'is_deleted', 'deleted_at']
    actions = None
    readonly_fields = ['is_deleted', 'deleted_at', 'deleted_by']

    def __init__(self, model, admin_site):
        super().__init__(model, admin_site)
        self.private_file_displays = {
            field.name: private_file_name(field) for field in model._meta.fields
            if isinstance(field, FileField) and isinstance(field.storage, PrivateCourseMediaStorage)
        }

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

    def get_fields(self, request, obj=None):
        if obj is not None and not self.has_change_permission(request, obj):
            # Django normally calls FileField.url to render read-only fields.
            # Private storage serves files only through their authorized endpoints.
            return [
                self.private_file_displays.get(field.name, field.name)
                for field in (*self.model._meta.fields, *self.model._meta.many_to_many)
            ]
        return super().get_fields(request, obj)


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


class PaymentAdminForm(forms.ModelForm):
    def clean_reservation_group(self):
        group = self.cleaned_data['reservation_group']
        group_ids = {group.pk, self.instance.reservation_group_id} - {None}
        locked_groups = ReservationGroup.objects.select_for_update().filter(pk__in=group_ids).order_by('pk')
        if any(row.is_test for row in locked_groups):
            raise forms.ValidationError('測試訂單不能變更正式付款紀錄')
        return group


class PaymentArchiveAdmin(ArchivedOrderAdmin):
    form = PaymentAdminForm


class MemberDetailAdmin(ArchivedOrderAdmin):
    readonly_fields = [
        *ArchivedOrderAdmin.readonly_fields,
        'insurance_premium_amount', 'insurance_premium_currency',
        'insurance_processing_status', 'insurance_premium_ledger_key',
    ]


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
            'reservation', 'booking',
        } else PlatformArchiveAdmin
        if scope.model._meta.model_name == 'payment':
            admin_class = PaymentArchiveAdmin
        elif scope.model._meta.model_name == 'memberdetail':
            admin_class = MemberDetailAdmin
        admin.site.register(scope.model, admin_class)


@admin.register(InsurancePrepaidAccount, InsuranceLedgerEntry, InsuranceReconciliation)
class InsuranceLedgerAdmin(admin.ModelAdmin):
    actions = None

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
