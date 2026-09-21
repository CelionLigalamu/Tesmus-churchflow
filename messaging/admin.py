from django.contrib import admin, messages

from .models import SMSConfiguration, SMSTemplate, SMSMessage
from .resend import resend_in_background

admin.site.register(SMSConfiguration)


@admin.register(SMSTemplate)
class SMSTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'church', 'is_active')
    list_filter = ('church', 'is_active')
    search_fields = ('name', 'body', 'church__name')


@admin.register(SMSMessage)
class SMSMessageAdmin(admin.ModelAdmin):
    list_display = ('recipient_phone', 'church', 'status', 'attempt_count', 'created_at', 'last_attempt_at')
    list_filter = ('status', 'church')
    actions = ['resend_failed']

    @admin.action(description='Resend selected failed messages')
    def resend_failed(self, request, queryset):
        claimed = resend_in_background(queryset)
        if claimed:
            self.message_user(
                request,
                f'{len(claimed)} failed message(s) are being resent. Refresh this page to see their new status.',
                messages.SUCCESS,
            )
        else:
            self.message_user(
                request,
                'None of the selected messages had failed, so nothing was resent. Sent messages are never sent twice.',
                messages.WARNING,
            )
