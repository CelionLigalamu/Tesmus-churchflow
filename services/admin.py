from django.contrib import admin
from .models import Service
from .services import finalize_service


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ('name', 'church', 'date', 'status', 'qr_token')
    readonly_fields = ('qr_token',)
    actions = ['close_service', 'finalize']

    def close_service(self, request, queryset):
        count = queryset.filter(status='open').update(status='closed')
        self.message_user(request, f"{count} service(s) closed.")
    close_service.short_description = "Close selected services (stop check-ins)"

    def finalize(self, request, queryset):
        count = 0
        for service in queryset:
            if service.status in ('closed', 'open'):
                finalize_service(service)
                count += 1
        self.message_user(request, f"{count} service(s) finalized — present/absent SMS processed.")
    finalize.short_description = "Finalize service (determine absent, send SMS)"