from django.contrib import admin
from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('action', 'user', 'church', 'created_at')
    list_filter = ('church',)
    readonly_fields = ('church', 'user', 'action', 'details', 'created_at')
