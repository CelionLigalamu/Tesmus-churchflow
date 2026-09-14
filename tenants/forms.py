"""Free-text region and branch entry, shared by the member and visitor forms."""
from django import forms

from accounts.permissions import user_can_access_branch, user_can_access_region

from .services import (
    PlaceError,
    branch_names,
    find_branch,
    find_region,
    normalize_place_name,
    region_names,
    resolve_branch,
    resolve_region,
)


class TypedPlaceFormMixin:
    """Replaces the region/branch dropdowns with autocompleted text inputs.

    The model's region/branch fields are left out of Meta.fields; these text
    fields stand in for them and the resolved objects are attached to the
    instance in save(). Nothing is created during validation, so a form that
    fails on another field does not leave a stray region behind.
    """

    place_noun = 'records'

    def init_place_fields(self, user, instance=None):
        self.user = user
        # Only church-wide administrators may invent new places by typing.
        # A region- or branch-scoped user must match something that exists,
        # otherwise they could create a region outside their own scope.
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
        self.fields['branch'] = forms.CharField(
            required=False,
            label='Branch',
            widget=forms.TextInput(attrs={
                'list': 'branch-options',
                'autocomplete': 'off',
                'placeholder': 'e.g. Westlands',
            }),
        )

        if instance is not None and instance.pk:
            self.fields['region'].initial = instance.region.name if instance.region_id else ''
            self.fields['branch'].initial = instance.branch.name if instance.branch_id else ''

        # Rendered as <datalist> options by the form template.
        self.region_options = region_names(user.church)
        self.branch_options = branch_names(user.church)

    def clean(self):
        cleaned = super().clean()
        church = self.user.church

        region_name = normalize_place_name(cleaned.get('region'))
        branch_name = normalize_place_name(cleaned.get('branch'))
        cleaned['region'] = region_name
        cleaned['branch'] = branch_name

        existing_region = find_region(church, region_name) if region_name else None
        existing_branch = find_branch(church, branch_name) if branch_name else None

        if region_name and not existing_region and not self.can_create_places:
            self.add_error('region', f'"{region_name}" is not one of your regions.')
        if branch_name and not existing_branch and not self.can_create_places:
            self.add_error('branch', f'"{branch_name}" is not one of your branches.')

        if existing_region and not user_can_access_region(self.user, existing_region):
            self.add_error('region', f'You cannot assign {self.place_noun} to this region.')
        if existing_branch and not user_can_access_branch(self.user, existing_branch):
            self.add_error('branch', f'You cannot assign {self.place_noun} to this branch.')

        # A branch belongs to one region; typing a different one is a conflict.
        if existing_branch and existing_region and existing_branch.region_id:
            if existing_branch.region_id != existing_region.id:
                self.add_error(
                    'branch',
                    f'"{existing_branch.name}" already belongs to the '
                    f'{existing_branch.region.name} region.',
                )
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        church = self.user.church
        create = self.can_create_places

        try:
            region = resolve_region(church, self.cleaned_data.get('region'), create=create)
            branch = resolve_branch(
                church, self.cleaned_data.get('branch'), region=region, create=create
            )
        except PlaceError as error:  # pragma: no cover - guarded in clean()
            raise forms.ValidationError(str(error))

        instance.region = region
        instance.branch = branch

        if commit:
            instance.save()
            self.save_m2m()
        return instance
