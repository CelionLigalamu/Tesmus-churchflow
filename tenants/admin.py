from django.contrib import admin, messages

from .admin_forms import ChurchAdminForm
from .models import Church, Region, Branch

@admin.register(Church)
class ChurchAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'slug', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'code', 'slug')
    prepopulated_fields = {'slug': ('name',)}
    form = ChurchAdminForm

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        # Colours that save but may be hard to read are flagged, not blocked.
        for warning in getattr(form, 'colour_warnings', []):
            messages.warning(request, warning)


admin.site.register(Region)
admin.site.register(Branch)
