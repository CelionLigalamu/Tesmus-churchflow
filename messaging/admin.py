from django.contrib import admin
from .models import SMSConfiguration, SMSTemplate, SMSMessage

admin.site.register(SMSConfiguration)
admin.site.register(SMSTemplate)
admin.site.register(SMSMessage)
