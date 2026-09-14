"""Region forms: typed region entry for members and visitors, region pastors and merging."""
import difflib

from django import forms

from accounts.permissions import user_can_access_region
from members.models import Member, MinistryRole

from .services import (
    PlaceError,
    find_region,
    normalize_place_name,
    region_names,
    resolve_region,
)
from .models import Church, Region


class TypedPlaceFormMixin:
    """Replaces the region dropdown with an autocompleted text input.

    The model's region field is left out of Meta.fields; this text field
    stands in for it and the resolved region is attached to the instance in
    save(). Nothing is created during validation, so a form that fails on
    another field does not leave a stray region behind.
    """

    place_noun = 'records'

    def init_place_fields(self, user, instance=None):
        self.user = user
        # Only church-wide administrators may invent new regions by typing.
        # A region-scoped user must match one that exists, otherwise they
        # could create a region outside their own scope.
        self.can_create_places = (
            not user.is_tesmus_staff and user.scope_type == 'church'
        )

        self.fields['region'] = forms.CharField(
            required=False,
            label='Region',
            widget=forms.TextInput(attrs={
                'list': 'region-options',
                'autocomplete': 'off',
                'placeholder': 'e.g. Kasarani',
            }),
        )

        if instance is not None and instance.pk:
            self.fields['region'].initial = instance.region.name if instance.region_id else ''

        # Rendered as <datalist> options by the form template.
        self.region_options = region_names(user.church)

    def clean(self):
        cleaned = super().clean()
        region_name = normalize_place_name(cleaned.get('region'))
        cleaned['region'] = region_name

        existing_region = find_region(self.user.church, region_name) if region_name else None
        if region_name and not existing_region and not self.can_create_places:
            self.add_error('region', f'"{region_name}" is not one of your regions.')
        if existing_region and not user_can_access_region(self.user, existing_region):
            self.add_error('region', f'You cannot assign {self.place_noun} to this region.')
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        try:
            instance.region = resolve_region(
                self.user.church, self.cleaned_data.get('region'), create=self.can_create_places,
            )
        except PlaceError as error:  # pragma: no cover - guarded in clean()
            raise forms.ValidationError(str(error))

        if commit:
            instance.save()
            self.save_m2m()
        return instance


class RegionForm(forms.ModelForm):
    """Add or rename a region and choose its pastors from the church's members."""

    pastors = forms.ModelMultipleChoiceField(
        queryset=Member.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = Region
        fields = ('name', 'pastors')
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'e.g. Sikhendu', 'autocomplete': 'off'}),
        }

    def __init__(self, church, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.church = church
        if not self.instance.pk:
            self.instance.church = church
        # Only this church's members can be chosen, so an altered form cannot
        # make another church's member a pastor here.
        self.fields['pastors'].queryset = Member.objects.filter(
            church=church,
        ).select_related('region').order_by('full_name', 'reference_number')

    def clean_name(self):
        name = normalize_place_name(self.cleaned_data.get('name'))
        if not name:
            raise forms.ValidationError('Enter the region name.')
        duplicates = Region.objects.filter(church=self.church, name__iexact=name)
        if self.instance.pk:
            duplicates = duplicates.exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise forms.ValidationError('A region with this name already exists.')
        return name

    def save(self, commit=True):
        region = super().save(commit=False)
        region.church = self.church
        if commit:
            region.save()
            self.save_m2m()
        return region

    def pastor_options(self):
        """Members to show in the picker, with the chosen pastors listed first."""
        if self.is_bound:
            selected = set(self.data.getlist('pastors'))
        elif self.instance.pk:
            selected = {str(pk) for pk in self.instance.pastors.values_list('pk', flat=True)}
        else:
            selected = set()
        options = [
            {'member': member, 'selected': str(member.pk) in selected}
            for member in self.fields['pastors'].queryset
        ]
        options.sort(key=lambda option: not option['selected'])
        return options


class RegionMergeForm(forms.Form):
    """Choose the region that one region's members and records move into."""

    target = forms.ModelChoiceField(
        queryset=Region.objects.none(),
        label='Move everything into',
        empty_label='Choose a region',
        error_messages={'required': 'Choose the region to merge into.', 'invalid_choice': 'Choose one of your regions.'},
    )
    confirm = forms.BooleanField(error_messages={'required': 'Tick the box to confirm the merge.'})

    def __init__(self, source, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.source = source
        others = Region.objects.filter(church_id=source.church_id).exclude(pk=source.pk).order_by('name')
        self.fields['target'].queryset = others
        # Just the area name: every choice belongs to this church, so the church code adds nothing.
        self.fields['target'].label_from_instance = lambda region: region.name
        self.fields['confirm'].label = f'I understand "{source.name}" will be removed once everything has moved.'
        # Suggest the region spelled most like this one, e.g. Sikendu -> Sikhendu.
        self.suggested = None
        by_name = {region.name.lower(): region for region in others}
        match = difflib.get_close_matches(source.name.lower(), list(by_name), n=1, cutoff=0.75)
        if match:
            self.suggested = by_name[match[0]]
            if not self.is_bound:
                self.fields['target'].initial = self.suggested.pk


class RegionPastorRoleForm(forms.ModelForm):
    """Which ministry role makes a member their own region's pastor."""

    class Meta:
        model = Church
        fields = ('region_pastor_role',)
        labels = {'region_pastor_role': 'Pastors by ministry role'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        field = self.fields['region_pastor_role']
        # Only this church's own roles, so an altered form cannot pick another church's.
        field.queryset = MinistryRole.objects.filter(church=self.instance).order_by('sort_order', 'name')
        field.required = False
        field.empty_label = 'No role - only pastors picked for each region'
