from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.http import JsonResponse
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404, resolve_url

from tenants.models import Church

from .forms import ChurchAuthenticationForm
from .models import User


class ChurchLogoutView(LogoutView):
    """Log out, then return church users to their own church's sign-in page.

    Tesmus staff, people without a church, and users of a church that is no
    longer active go to the general sign-in page instead. A safe `next`
    address, when one is sent, still takes priority.
    """

    def post(self, request, *args, **kwargs):
        # Read the church first: logging out replaces the signed-in user.
        self.church_login_url = self._church_login_url(request.user)
        return super().post(request, *args, **kwargs)

    @staticmethod
    def _church_login_url(user):
        if not user.is_authenticated or user.is_tesmus_staff or not user.church_id:
            return None
        church = user.church
        if not church.is_active or not church.slug:
            return None
        return reverse('church_login', args=[church.slug])

    def get_default_redirect_url(self):
        return getattr(self, 'church_login_url', None) or resolve_url('login')


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
