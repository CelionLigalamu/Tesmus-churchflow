from django.contrib import admin
from .models import Visitor
from .services import convert_visitor_to_member
from messaging.services import send_message


@admin.register(Visitor)
class VisitorAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'phone_number', 'church', 'converted_to_member')
    actions = ['convert_to_member', 'send_welcome_sms']

    def convert_to_member(self, request, queryset):
        count = 0
        for visitor in queryset:
            if not visitor.converted_to_member_id:
                convert_visitor_to_member(visitor)
                count += 1
        self.message_user(request, f"{count} visitor(s) converted to member.")
    convert_to_member.short_description = "Convert selected visitors to members"

    def send_welcome_sms(self, request, queryset):
        count = 0
        for visitor in queryset:
            body = (
                f"Mpendwa {visitor.full_name}, tunakushukuru kwa kututembelea na kushiriki nasi "
                f"katika ibada ya leo. Tunafurahi kuwa nawe na tunakukaribisha tena katika familia ya "
                f"{visitor.church.name}. Mungu akubariki."
            )
            send_message(visitor.church, visitor.phone_number, body)
            count += 1
        self.message_user(request, f"Welcome SMS queued for {count} visitor(s).")
    send_welcome_sms.short_description = "Send welcome SMS to selected visitors"