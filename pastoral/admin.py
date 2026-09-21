from django.contrib import admin
from .models import PastoralFollowUp


@admin.register(PastoralFollowUp)
class PastoralFollowUpAdmin(admin.ModelAdmin):
    list_display = ('member', 'church', 'reason', 'missed_count', 'status', 'follow_up_date', 'created_at')
    list_filter = ('status', 'reason', 'church')
    search_fields = ('member__full_name', 'member__reference_number')
    filter_horizontal = ('pastors',)
    raw_id_fields = ('member', 'assigned_to', 'trigger_service')
    readonly_fields = ('created_at', 'closed_at')
