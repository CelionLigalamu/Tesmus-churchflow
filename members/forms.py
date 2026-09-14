from django import forms

from tenants.forms import TypedPlaceFormMixin
from tenants.services import find_region, normalize_place_name, region_names

from .models import Member, MinistryRole
from .services import ensure_default_ministry_roles


class MemberForm(TypedPlaceFormMixin, forms.ModelForm):
    place_noun = 'members'

    class Meta:
        model = Member
        fields = ('full_name', 'phone_number', 'ministry_roles')
        widgets = {
            'full_name': forms.TextInput(attrs={'placeholder': 'e.g. Mary Wanjiku'}),
            'phone_number': forms.TextInput(attrs={'placeholder': 'e.g. 0712 345 678'}),
        }

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['ministry_roles'].queryset = ensure_default_ministry_roles(user.church)
        self.fields['ministry_roles'].required = False
        self.fields['ministry_roles'].widget.attrs.update({'size': 6})
        self.init_place_fields(user, instance=self.instance)


class MinistryRoleForm(forms.ModelForm):
    def __init__(self, church, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.church = church

    class Meta:
        model = MinistryRole
        fields = ('name',)
        widgets = {'name': forms.TextInput(attrs={'placeholder': 'e.g. Choir'})}

    def clean_name(self):
        name = self.cleaned_data['name'].strip()
        queryset = MinistryRole.objects.filter(church=self.church, name__iexact=name)
        if self.instance.pk:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise forms.ValidationError('A role with this name already exists.')
        return name


class SelfRegistrationForm(forms.Form):
    """The public form a member fills in for themselves.

    Regions must already exist: this endpoint is open to anyone with the link,
    so it may never create new places.
    """

    full_name = forms.CharField(
        label='Your full name',
        max_length=255,
        widget=forms.TextInput(attrs={'placeholder': 'e.g. Mary Wanjiku', 'autocomplete': 'name'}),
    )
    phone_number = forms.CharField(
        label='Your phone number',
        max_length=20,
        widget=forms.TextInput(attrs={'placeholder': 'e.g. 0712 345 678', 'autocomplete': 'tel'}),
    )
    region = forms.CharField(
        label='Where you live',
        required=False,
        widget=forms.TextInput(attrs={
            'list': 'region-options',
            'autocomplete': 'off',
            'placeholder': 'Start typing to see the list',
        }),
    )

    def __init__(self, church, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.church = church
        self.region_options = region_names(church)
        if not self.region_options:
            # Nothing to choose from yet - do not ask a question with no answer.
            del self.fields['region']

    def clean_full_name(self):
        name = normalize_place_name(self.cleaned_data['full_name'])
        if len(name) < 2:
            raise forms.ValidationError('Please enter your full name.')
        return name

    def clean_phone_number(self):
        from .importer import phone_key

        raw = self.cleaned_data['phone_number'].strip()
        if len(phone_key(raw)) < 9:
            raise forms.ValidationError('Please enter a valid phone number.')
        if Member.objects.filter(church=self.church).filter(
            phone_number__in=_phone_variants(raw)
        ).exists():
            raise forms.ValidationError(
                'This phone number is already registered at this church.'
            )
        return raw

    def clean_region(self):
        typed = normalize_place_name(self.cleaned_data.get('region'))
        if not typed:
            return None
        region = find_region(self.church, typed)
        if region is None:
            raise forms.ValidationError(
                'Please choose one of the areas listed. If yours is missing, '
                'leave this blank and the church will complete it.'
            )
        return region


def _phone_variants(raw):
    """Every stored spelling that would mean the same Kenyan number."""
    from .importer import phone_key

    key = phone_key(raw)
    if not key:
        return [raw]
    return [raw, key, f'0{key}', f'254{key}', f'+254{key}']
