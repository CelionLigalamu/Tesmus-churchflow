from django.contrib import admin
from .models import SMSConfiguration, SMSTemplate, SMSMessage

admin.site.register(SMSConfiguration)
admin.site.register(SMSTemplate)


@admin.register(SMSMessage)
class SMSMessageAdmin(admin.ModelAdmin):
    list_display = ('recipient_phone', 'church', 'status', 'created_at')
    list_filter = ('status', 'church')
