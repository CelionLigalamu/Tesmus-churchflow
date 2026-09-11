from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import AuthenticationForm


class ChurchAuthenticationForm(AuthenticationForm):
    """Username/password authentication restricted to one church URL."""

    def __init__(self, church, *args, **kwargs):
        self.church = church
        super().__init__(*args, **kwargs)

    def clean(self):
        username = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')
        if username and password:
            self.user_cache = authenticate(
                self.request,
                username=username,
                password=password,
            )
            if (
                self.user_cache is None
                or self.user_cache.is_tesmus_staff
                or self.user_cache.church_id != self.church.id
            ):
                raise self.get_invalid_login_error()
            self.confirm_login_allowed(self.user_cache)
        return self.cleaned_data
