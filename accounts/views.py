from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404

from tenants.models import Church

from .forms import ChurchAuthenticationForm
from .models import User


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


@login_required
@require_POST
def set_theme_preference(request):
    """Save the signed-in person's dashboard appearance: light, dark or system."""
    value = request.POST.get('theme', '')
    if value not in dict(User.THEME_CHOICES):
        return JsonResponse({'error': 'Choose light, dark or system.'}, status=400)
    if request.user.theme_preference != value:
        request.user.theme_preference = value
        request.user.save(update_fields=['theme_preference'])
    return JsonResponse({'theme': value})
