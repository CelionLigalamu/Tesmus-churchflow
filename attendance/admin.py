from django.contrib import admin
from .models import Attendance
from messaging.services import send_message


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('service', 'member', 'visitor', 'method', 'result', 'checked_in_at')
    actions = ['send_present_sms']

    def send_present_sms(self, request, queryset):
        count = 0
        for attendance in queryset:
            if not attendance.member:
                continue
            body = (
                f"Mpendwa {attendance.member.full_name}, tunakushukuru kwa kushiriki nasi "
                f"katika {attendance.service.name} ya leo. Mungu akubariki."
            )
            send_message(attendance.church, attendance.member.phone_number, body)
            attendance.result = 'present'
            attendance.save(update_fields=['result'])
            count += 1
        self.message_user(request, f"Present SMS queued for {count} attendee(s).")
    send_present_sms.short_description = "Mark present + send thank-you SMS"
