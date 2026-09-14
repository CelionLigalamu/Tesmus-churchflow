"""Forms for giving church members an usher sign-in."""
from django import forms
from django.contrib.auth import get_user_model, password_validation
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.db import transaction

from members.models import Member, MinistryRole
from tenants.models import Church

User = get_user_model()


def members_without_sign_in(church):
    """The church's members who do not have a sign-in yet."""
    return Member.objects.filter(church=church, user_account__isnull=True).select_related('region').order_by(
        'full_name', 'reference_number',
    )


def give_usher_role(church, member):
    """Give a member the ministry role the church uses for ushers, if it has one."""
    if church.usher_role_id:
        member.ministry_roles.add(church.usher_role_id)


def member_choice_field():
    return forms.ModelChoiceField(
        queryset=Member.objects.none(),
        label='Member',
        widget=forms.RadioSelect,
        error_messages={
            'required': 'Choose the member who will use this sign-in.',
            'invalid_choice': 'Choose one of your members who does not have a sign-in yet.',
        },
    )


class MemberChoiceMixin:
    """A searchable list of the church's members who do not have a sign-in yet."""

    def init_member_field(self, church):
        self.church = church
        # Only this church's members without a sign-in, so an altered form
        # cannot link another church's member or give one member two sign-ins.
        self.fields['member'].queryset = members_without_sign_in(church)

    def member_options(self):
        if self.is_bound:
            selected = str(self.data.get('member', ''))
        else:
            selected = str(self.initial.get('member', '') or '')
        role_holders = set()
        if self.church.usher_role_id:
            role_holders = set(
                Member.objects.filter(church=self.church, ministry_roles=self.church.usher_role_id)
                .values_list('pk', flat=True)
            )
        options = [
            {'member': member, 'selected': str(member.pk) == selected, 'has_usher_role': member.pk in role_holders}
            for member in self.fields['member'].queryset
        ]
        # The chosen member first, then members who already hold the usher role.
        options.sort(key=lambda option: (not option['selected'], not option['has_usher_role']))
        return options


class UsherCreateForm(MemberChoiceMixin, forms.Form):
    """A church administrator gives one of their members an usher sign-in."""

    member = member_choice_field()
    username = forms.CharField(
        label='Username', max_length=150, validators=[UnicodeUsernameValidator()],
        help_text='What the usher types to sign in, for example simon.mbuthia',
        widget=forms.TextInput(attrs={'autocomplete': 'off'}),
    )
    password1 = forms.CharField(
        label='Password', strip=False,
        help_text='At least 8 characters, not too common and not only numbers.',
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
    )
    password2 = forms.CharField(
        label='Repeat password', strip=False,
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
    )

    def __init__(self, church, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.init_member_field(church)

    def clean_username(self):
        username = self.cleaned_data['username'].strip()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError('That username is already taken.')
        return username

    def clean(self):
        cleaned = super().clean()
        password, repeated = cleaned.get('password1'), cleaned.get('password2')
        if password and repeated and password != repeated:
            self.add_error('password2', 'The two passwords do not match.')
        elif password:
            member = cleaned.get('member')
            candidate = User(username=cleaned.get('username', ''), first_name=member.full_name if member else '')
            try:
                password_validation.validate_password(password, user=candidate)
            except forms.ValidationError as error:
                self.add_error('password1', error)
        return cleaned

    def save(self):
        member = self.cleaned_data['member']
        with transaction.atomic():
            usher = User.objects.create_user(
                username=self.cleaned_data['username'],
                password=self.cleaned_data['password1'],
                first_name=member.full_name[:150],
                church=self.church,
                is_usher=True,
                scope_type='none',
                member=member,
            )
            give_usher_role(self.church, member)
        return usher


class UsherLinkForm(MemberChoiceMixin, forms.Form):
    """Link an existing usher sign-in to the member record of the person using it."""

    member = member_choice_field()

    def __init__(self, church, usher, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.usher = usher
        self.init_member_field(church)

    def save(self):
        member = self.cleaned_data['member']
        with transaction.atomic():
            self.usher.member = member
            self.usher.first_name = member.full_name[:150]
            self.usher.save(update_fields=['member', 'first_name'])
            give_usher_role(self.church, member)
        return self.usher


class UsherRoleForm(forms.ModelForm):
    """Which ministry role marks the church's ushers."""

    class Meta:
        model = Church
        fields = ('usher_role',)
        labels = {'usher_role': 'Ministry role for ushers'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        field = self.fields['usher_role']
        # Only this church's own roles, so an altered form cannot pick another church's.
        field.queryset = MinistryRole.objects.filter(church=self.instance).order_by('sort_order', 'name')
        field.required = False
        field.empty_label = 'No role'
