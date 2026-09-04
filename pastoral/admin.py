from django.contrib import admin
from .models import PastoralFollowUp


@admin.register(PastoralFollowUp)
class PastoralFollowUpAdmin(admin.ModelAdmin):
    list_display = ('member', 'status', 'assigned_to', 'follow_up_date')
    list_filter = ('status',)
