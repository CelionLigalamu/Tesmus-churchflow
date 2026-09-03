from django.contrib import admin
from .models import Member
from .services import generate_reference_number
from messaging.services import send_message


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ('reference_number', 'full_name', 'phone_number', 'church', 'status')
    readonly_fields = ('reference_number',)
    actions = ['send_reference_sms']

    def save_model(self, request, obj, form, change):
        if not obj.reference_number:
            obj.reference_number = generate_reference_number(obj.church_id)
        super().save_model(request, obj, form, change)

    def send_reference_sms(self, request, queryset):
        count = 0
        for member in queryset:
            body = (
                f"Mpendwa {member.full_name}, namba yako ya usajili katika "
                f"{member.church.name} ni {member.reference_number}. "
                f"Tafadhali ihifadhi kwa matumizi ya mahudhurio ya ibada na shughuli nyingine za kanisa. "
                f"Mungu akubariki."
            )
            send_message(member.church, member.phone_number, body)
            count += 1
        self.message_user(request, f"Reference SMS queued for {count} member(s).")
    send_reference_sms.short_description = "Send reference number SMS to selected members"
