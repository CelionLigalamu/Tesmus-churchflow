"""Typed region entry for Django admin, matching the church dashboard.

In admin a region is typed rather than picked from one long list of every
church's regions. The name is matched within the chosen church, without caring
about capitals or extra spaces, and an area the church does not have yet is
added as a new region. A region can never come from another church.
"""
from django import forms
from django.utils.html import format_html, json_script

from .models import Region
from .services import normalize_place_name, resolve_region


class RegionNameInput(forms.TextInput):
    """A text box that suggests the chosen church's regions as you type."""

    class Media:
        js = ('js/admin_region_input.js',)

    def __init__(self, church_field='church', attrs=None):
        super().__init__(attrs={'autocomplete': 'off', 'placeholder': 'e.g. Kasarani', **(attrs or {})})
        self.church_field = church_field

    def render(self, name, value, attrs=None, renderer=None):
        attrs = dict(attrs or {})
        input_id = attrs.get('id') or f'id_{name}'
        attrs.update({
            'list': f'{input_id}-options',
            'data-region-names': f'{input_id}-names',
            'data-church-field': f'id_{self.church_field}',
        })
        # Every church's region names, keyed by church; the script shows only
        # the chosen church's names and switches them when the church changes.
        names = {}
        for church_id, region_name in Region.objects.order_by('name').values_list('church_id', 'name'):
            names.setdefault(str(church_id), []).append(region_name)
        return format_html(
            '{}<datalist id="{}"></datalist>{}',
            super().render(name, value, attrs, renderer),
            f'{input_id}-options',
            json_script(names, f'{input_id}-names'),
        )


class TypedRegionAdminForm(forms.ModelForm):
    """Base admin form for records with a church and a region.

    Subclasses set Meta.model and exclude the model's own region field, which
    this typed field stands in for.
    """

    region = forms.CharField(
        required=False,
        max_length=80,
        widget=RegionNameInput(),
        help_text='The area where the person lives. A new area is added as a region automatically. '
                  'Leave blank if not known.',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and self.instance.region_id:
            self.fields['region'].initial = self.instance.region.name

    def clean_region(self):
        return normalize_place_name(self.cleaned_data.get('region'))

    def save(self, commit=True):
        instance = super().save(commit=False)
        # Only runs after validation, so a form with errors never creates a region.
        instance.region = resolve_region(instance.church, self.cleaned_data.get('region'), create=True)
        if commit:
            instance.save()
            self.save_m2m()
        return instance
