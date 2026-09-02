from django.contrib import admin
from .models import Reservation, Booking, MemberDetail, Payment, ReservationGroup

class ReservationInline(admin.TabularInline):
    model = Reservation
    extra = 0
    fields = ['group', 'course_type', 'status', 'preferred_coach']
    readonly_fields = []

@admin.register(ReservationGroup)
class ReservationGroupAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'user', 'created_at']
    inlines = [ReservationInline]

# 註冊模型到管理界面
admin.site.register(Reservation)
admin.site.register(Booking)
admin.site.register(MemberDetail)
admin.site.register(Payment)