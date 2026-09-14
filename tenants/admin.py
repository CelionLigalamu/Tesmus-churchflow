from django import forms
from django.contrib import admin, messages
from django.contrib.admin import helpers
from django.db import transaction
from django.template.response import TemplateResponse

from audit.services import log_action
from members.models import Member

from .admin_forms import ChurchAdminForm
from .models import Church, Region
from .services import merge_regions

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


class RegionAdminForm(forms.ModelForm):
    class Meta:
        model = Region
        fields = ('church', 'name', 'pastors')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Once the church is known, only its members are offered as pastors.
        if self.instance.pk:
            self.fields['pastors'].queryset = Member.objects.filter(
                church_id=self.instance.church_id,
            ).order_by('full_name')

    def clean(self):
        cleaned = super().clean()
        church = cleaned.get('church')
        outsiders = [
            pastor.full_name for pastor in cleaned.get('pastors') or []
            if church and pastor.church_id != church.id
        ]
        if outsiders:
            self.add_error('pastors', f'Pastors must be members of {church.name}: {", ".join(outsiders)}.')
        return cleaned


@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    form = RegionAdminForm
    list_display = ('name', 'church', 'pastor_list')
    list_filter = ('church',)
    search_fields = ('name', 'church__name')
    filter_horizontal = ('pastors',)
    actions = ['merge_selected_regions']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('church').prefetch_related('pastors')

    @admin.action(description='Merge selected regions (same church) into one')
    def merge_selected_regions(self, request, queryset):
        """For the same area typed two ways: keep one region, move everything into it."""
        regions = list(queryset.select_related('church').order_by('name'))
        if len(regions) < 2:
            self.message_user(request, 'Select at least two regions to merge.', messages.WARNING)
            return None
        if len({region.church_id for region in regions}) > 1:
            self.message_user(request, 'Only regions of the same church can be merged.', messages.ERROR)
            return None

        target_id = request.POST.get('target')
        if target_id:
            target = next((region for region in regions if str(region.pk) == target_id), None)
            if target is None:
                self.message_user(request, 'Choose one of the selected regions to keep.', messages.ERROR)
                return None
            merged_names = [region.name for region in regions if region.pk != target.pk]
            with transaction.atomic():
                members_moved = sum(
                    merge_regions(region, target) for region in regions if region.pk != target.pk
                )
            log_action(request.user, 'regions_merged', church=target.church,
                       details=f'{", ".join(merged_names)} merged into {target.name} ({members_moved} members moved)')
            self.message_user(
                request,
                f'Merged {", ".join(merged_names)} into {target.name}. {members_moved} member(s) moved.',
                messages.SUCCESS,
            )
            return None

        choices = [(region, region.members.count()) for region in regions]
        suggested = max(choices, key=lambda choice: choice[1])[0]
        return TemplateResponse(request, 'admin/tenants/region/merge_regions.html', {
            **self.admin_site.each_context(request),
            'title': 'Merge regions',
            'opts': self.model._meta,
            'church': regions[0].church,
            'choices': choices,
            'suggested': suggested,
            'action_checkbox_name': helpers.ACTION_CHECKBOX_NAME,
        })

    @admin.display(description='Pastors')
    def pastor_list(self, obj):
        return ', '.join(pastor.full_name for pastor in obj.pastors.all()) or '-'
