from django import forms

from tenants.forms import TypedPlaceFormMixin
from tenants.services import normalize_place_name, region_names

from .models import Member, MinistryRole
from .phones import members_with_phone, phone_key
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

    Every field is required. The member types the area they live in: an area
    the church already has is matched whatever the capitals, and a new one
    becomes a region when the registration is saved - never during validation,
    so a form with a mistake leaves nothing behind.
    """

    full_name = forms.CharField(
        label='Your full name',
        max_length=255,
        error_messages={'required': 'Please enter your full name.'},
        widget=forms.TextInput(attrs={'placeholder': 'e.g. Mary Wanjiku', 'autocomplete': 'name'}),
    )
    phone_number = forms.CharField(
        label='Your phone number',
        max_length=20,
        error_messages={'required': 'Please enter your phone number.'},
        widget=forms.TextInput(attrs={'placeholder': 'e.g. 0712 345 678', 'autocomplete': 'tel'}),
    )
    region = forms.CharField(
        label='Where you live',
        max_length=80,
        error_messages={
            'required': 'Please enter the area where you live.',
            'max_length': 'Please shorten the area name to 80 characters or fewer.',
        },
        widget=forms.TextInput(attrs={
            'list': 'region-options',
            'autocomplete': 'off',
            'placeholder': 'e.g. Sikhendu',
        }),
    )

    def __init__(self, church, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.church = church
        # Areas other members have already typed, suggested as the member types.
        self.region_options = region_names(church)

    def clean_full_name(self):
        name = normalize_place_name(self.cleaned_data['full_name'])
        if len(name) < 2:
            raise forms.ValidationError('Please enter your full name.')
        return name

    def clean_phone_number(self):
        raw = self.cleaned_data['phone_number'].strip()
        if len(phone_key(raw)) < 9:
            raise forms.ValidationError('Please enter a valid phone number.')
        if members_with_phone(Member.objects.filter(church=self.church), raw).exists():
            raise forms.ValidationError(
                'This phone number is already registered at this church.'
            )
        return raw

    def clean_region(self):
        name = normalize_place_name(self.cleaned_data['region'])
        if len(name) < 2 or not any(character.isalpha() for character in name):
            raise forms.ValidationError('Please enter the area where you live.')
        return name

