from django import forms

from tenants.forms import TypedPlaceFormMixin

from .models import Visitor


class VisitorForm(TypedPlaceFormMixin, forms.ModelForm):
    place_noun = 'visitors'

    class Meta:
        model = Visitor
        fields = ('full_name', 'phone_number')
        widgets = {
            'full_name': forms.TextInput(attrs={'placeholder': 'e.g. Jane Wanjiku'}),
            'phone_number': forms.TextInput(attrs={'placeholder': 'e.g. 0712 345 678'}),
        }

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.init_place_fields(user, instance=self.instance)
