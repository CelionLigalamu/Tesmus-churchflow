from django import forms

from .models import SMSTemplate


class SMSTemplateForm(forms.ModelForm):
    class Meta:
        model = SMSTemplate
        fields = ('body', 'is_active')
        widgets = {
            'body': forms.Textarea(attrs={
                'rows': 7,
                'maxlength': 480,
                'placeholder': 'Write the SMS message here...',
            }),
        }

    def clean_body(self):
        body = self.cleaned_data['body'].strip()
        if not body:
            raise forms.ValidationError('Enter a message before saving.')
        return body
