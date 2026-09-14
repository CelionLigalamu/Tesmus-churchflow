from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    """Read-only view for support; notifications are created by the system."""

    list_display = ('recipient', 'church', 'kind', 'count', 'updated_at', 'read_at')
    list_filter = ('kind', 'church')
    search_fields = ('recipient__username', 'detail')
    readonly_fields = ('church', 'recipient', 'kind', 'group_key', 'count', 'detail', 'created_at', 'updated_at', 'read_at')

    def has_add_permission(self, request):
        return False
