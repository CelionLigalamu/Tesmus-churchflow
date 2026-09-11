from django.contrib.auth.views import LoginView
from django.shortcuts import get_object_or_404

from tenants.models import Church

from .forms import ChurchAuthenticationForm


class ChurchLoginView(LoginView):
    template_name = 'dashboard/church_login.html'
    form_class = ChurchAuthenticationForm

    def dispatch(self, request, *args, **kwargs):
        self.church = get_object_or_404(
            Church,
            slug=kwargs['church_slug'],
            is_active=True,
        )
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['church'] = self.church
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['church'] = self.church
        return context
