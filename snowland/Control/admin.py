from django.contrib import admin
from .models import UserProfile

class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'is_manager_display', 'is_coach_display')

    def is_manager_display(self, obj):
        return '✅' if obj.is_manager else '❌'
    is_manager_display.short_description = '管理者'

    def is_coach_display(self, obj):
        return '✅' if obj.is_coach else '❌'
    is_coach_display.short_description = '教練'

admin.site.register(UserProfile, UserProfileAdmin)
