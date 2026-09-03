from django.contrib import admin
from .models import Service


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ('name', 'church', 'date', 'status', 'qr_token')
    readonly_fields = ('qr_token',)
