"""Admin form for churches: checks that chosen colours stay readable."""
from django import forms

from members.models import MinistryRole

from .colors import UI_CONTRAST, WHITE, contrast_ratio, normalize_hex
from .models import Church

# Colour of the small footer text on the church login page, which sits on the
# church's secondary colour (see .tenant-page-footer in theme.css).
LOGIN_FOOTER_TEXT = '#64748B'

HEX_HELP = 'Enter a colour as a hex code, for example #1D3F91.'


class ChurchAdminForm(forms.ModelForm):
    class Meta:
        model = Church
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.colour_warnings = []
        if 'region_pastor_role' in self.fields:
            # Only this church's own ministry roles can be chosen.
            self.fields['region_pastor_role'].queryset = MinistryRole.objects.filter(
                church_id=self.instance.pk,
            ).order_by('sort_order', 'name')

    def _clean_hex(self, field):
        value = normalize_hex(self.cleaned_data.get(field))
        if value is None:
            raise forms.ValidationError(HEX_HELP)
        return value

    def clean_primary_color(self):
        value = self._clean_hex('primary_color')
        ratio = contrast_ratio(value, WHITE)
        if ratio < UI_CONTRAST:
            raise forms.ValidationError(
                f'This colour is too pale for buttons, links and icons: it has a '
                f'contrast of {ratio:.1f}:1 against white and needs at least '
                f'{UI_CONTRAST:.0f}:1. Choose a darker shade.'
            )
        return value

    def clean_secondary_color(self):
        value = self._clean_hex('secondary_color')
        ratio = contrast_ratio(value, LOGIN_FOOTER_TEXT)
        if ratio < UI_CONTRAST:
            self.colour_warnings.append(
                f'Secondary colour {value} makes the small footer text on the '
                f'login page hard to read ({ratio:.1f}:1). A lighter or darker '
                f'shade will read better.'
            )
        return value

    def clean_accent_color(self):
        return self._clean_hex('accent_color')
