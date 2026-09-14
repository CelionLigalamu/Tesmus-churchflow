from django import forms

from accounts.permissions import user_can_access_region
from tenants.models import Region

from .models import Service


class ServiceForm(forms.ModelForm):
    class Meta:
        model = Service
        fields = ('name', 'service_type', 'date', 'start_time', 'end_time', 'region')
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'e.g. Sunday Service'}),
            'service_type': forms.TextInput(attrs={'placeholder': 'e.g. Worship service'}),
            'date': forms.DateInput(attrs={'type': 'date'}),
            'start_time': forms.TimeInput(attrs={'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'type': 'time'}),
        }

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields['region'].queryset = Region.objects.filter(church=user.church).order_by('name')
        if user.scope_type == 'region' and user.scope_region_id:
            self.fields['region'].queryset = self.fields['region'].queryset.filter(pk=user.scope_region_id)

    def clean(self):
        cleaned = super().clean()
        region = cleaned.get('region')
        start_time, end_time = cleaned.get('start_time'), cleaned.get('end_time')
        if region and not user_can_access_region(self.user, region):
            self.add_error('region', 'You cannot schedule services for this region.')
        if start_time and end_time and end_time <= start_time:
            self.add_error('end_time', 'Closing time must be after the start time.')
        return cleaned
