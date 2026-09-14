from django.contrib import admin
from .models import Member, MinistryRole
from .services import generate_reference_number
from messaging.admin_helpers import report_delivery
from messaging.services import send_reference_number_sms
from audit.services import log_action


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ('reference_number', 'full_name', 'phone_number', 'church')
    filter_horizontal = ('ministry_roles',)
    readonly_fields = ('reference_number',)
    actions = ['send_reference_sms']

    def save_model(self, request, obj, form, change):
        if not obj.reference_number:
            obj.reference_number = generate_reference_number(obj.church_id)
        super().save_model(request, obj, form, change)
        action = 'member_updated' if change else 'member_created'
        log_action(request.user, action, church=obj.church, details=f"{obj.reference_number} - {obj.full_name}")

    def send_reference_sms(self, request, queryset):
        results = [send_reference_number_sms(member) for member in queryset]
        report_delivery(self, request, results, noun='member')
    send_reference_sms.short_description = "Send reference number SMS to selected members"


@admin.register(MinistryRole)
class MinistryRoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'church')
    list_filter = ('church',)
