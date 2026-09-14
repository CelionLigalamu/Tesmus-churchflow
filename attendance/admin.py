from django.contrib import admin
from .models import Attendance
from messaging.admin_helpers import report_delivery
from messaging.services import send_attendance_present_sms


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('service', 'member', 'visitor', 'method', 'result', 'checked_in_at')
    actions = ['send_present_sms']

    def send_present_sms(self, request, queryset):
        results = []
        for attendance in queryset.select_related('member', 'service'):
            if not attendance.member:
                continue
            results.append(send_attendance_present_sms(attendance))
            attendance.result = 'present'
            attendance.save(update_fields=['result'])
        report_delivery(self, request, results, noun='attendee')
    send_present_sms.short_description = "Mark present + send thank-you SMS"
