from django.contrib import admin
from django import forms
from Client.admin import PlatformOnlyAdmin
from .models import UserProfile, TenantStaffMembership

class UserProfileAdmin(PlatformOnlyAdmin):
    list_display = ('user', 'is_manager_display', 'is_coach_display')

    def is_manager_display(self, obj):
        return '✅' if obj.is_manager else '❌'
    is_manager_display.short_description = '管理者'

    def is_coach_display(self, obj):
        return '✅' if obj.is_coach else '❌'
    is_coach_display.short_description = '教練'

admin.site.register(UserProfile, UserProfileAdmin)


class TenantStaffForm(forms.ModelForm):
    class Meta:
        model = TenantStaffMembership
        fields = '__all__'

    def clean(self):
        values = super().clean()
        client = values.get('client')
        campuses = values.get('campuses')
        if client and campuses is not None and campuses.exclude(client=client).exists():
            self.add_error('campuses','只能指派這所學校的校區。')
        return values


@admin.register(TenantStaffMembership)
class TenantStaffAdmin(PlatformOnlyAdmin):
    form = TenantStaffForm
    list_display = ['user','client','role','is_manager','is_coach']
    list_filter = ['client','role','is_manager','is_coach']
    search_fields = ['user__email','user__username','client__internal_code']
    autocomplete_fields = ['user','client']
    filter_horizontal = ['campuses']
