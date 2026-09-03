from django.contrib import admin
from .models import Attendance


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('service', 'member', 'visitor', 'method', 'result', 'checked_in_at')
