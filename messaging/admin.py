from django.contrib import admin

from .models import SMSConfiguration, SMSTemplate, SMSMessage

admin.site.register(SMSConfiguration)


@admin.register(SMSTemplate)
class SMSTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'church', 'is_active')
    list_filter = ('church', 'is_active')
    search_fields = ('name', 'body', 'church__name')


@admin.register(SMSMessage)
class SMSMessageAdmin(admin.ModelAdmin):
    list_display = ('recipient_phone', 'church', 'status', 'created_at')
    list_filter = ('status', 'church')
