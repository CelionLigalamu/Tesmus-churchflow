from django import forms

from tenants.models import Church

from .models import PastoralFollowUp


class FollowUpUpdateForm(forms.Form):
    status = forms.ChoiceField(
        choices=PastoralFollowUp.STATUS_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select form-select-custom'}),
    )
    note = forms.CharField(
        required=False,
        max_length=2000,
        label='Add a note',
        widget=forms.Textarea(attrs={
            'rows': 4,
            'placeholder': 'What happened? For example: Called her, she has been unwell and hopes to be back next Sunday.',
        }),
    )


class AbsenceAlertSettingForm(forms.ModelForm):
    class Meta:
        model = Church
        fields = ('absence_alert_after',)
        widgets = {'absence_alert_after': forms.NumberInput(attrs={'min': 0, 'max': 20})}
