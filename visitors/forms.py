from django import forms

from accounts.permissions import user_can_access_branch, user_can_access_region
from tenants.models import Branch, Region

from .models import Visitor


class VisitorForm(forms.ModelForm):
    class Meta:
        model = Visitor
        fields = ('full_name', 'phone_number', 'region', 'branch')
        widgets = {
            'full_name': forms.TextInput(attrs={'placeholder': 'e.g. Jane Wanjiku'}),
            'phone_number': forms.TextInput(attrs={'placeholder': 'e.g. 0712 345 678'}),
        }

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields['region'].queryset = Region.objects.filter(church=user.church).order_by('name')
        self.fields['branch'].queryset = Branch.objects.filter(church=user.church).select_related('region').order_by('name')
        if user.scope_type == 'region' and user.scope_region_id:
            self.fields['region'].queryset = self.fields['region'].queryset.filter(pk=user.scope_region_id)
            self.fields['branch'].queryset = self.fields['branch'].queryset.filter(region_id=user.scope_region_id)
        elif user.scope_type == 'branch' and user.scope_branch_id:
            self.fields['region'].queryset = self.fields['region'].queryset.filter(pk=user.scope_branch.region_id)
            self.fields['branch'].queryset = self.fields['branch'].queryset.filter(pk=user.scope_branch_id)

    def clean(self):
        cleaned = super().clean()
        region, branch = cleaned.get('region'), cleaned.get('branch')
        if region and not user_can_access_region(self.user, region):
            self.add_error('region', 'You cannot assign visitors to this region.')
        if branch and not user_can_access_branch(self.user, branch):
            self.add_error('branch', 'You cannot assign visitors to this branch.')
        if branch and region and branch.region_id != region.id:
            self.add_error('branch', 'Choose a branch within the selected region.')
        return cleaned
