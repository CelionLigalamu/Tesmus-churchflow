"""Keeps usher accounts on the usher check-in screen and nothing else."""
from django.conf import settings
from django.shortcuts import redirect

# Pages an usher may open. Anything not listed - including pages added in the
# future and Django admin - sends them back to the usher screen.
USHER_ALLOWED_URL_NAMES = {
    'usher_home', 'usher_service', 'usher_check_in',
    'logout', 'set_theme_preference',
    'public_home', 'login', 'church_login', 'qr_checkin', 'member_self_register',
}


class UsherAccessMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.file_prefixes = tuple(
            '/' + prefix.lstrip('/') for prefix in (settings.STATIC_URL, settings.MEDIA_URL) if prefix
        )

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        user = getattr(request, 'user', None)
        if not (user and user.is_authenticated and getattr(user, 'is_usher', False)):
            return None
        match = request.resolver_match
        if match and not match.namespace and match.url_name in USHER_ALLOWED_URL_NAMES:
            return None
        if request.path.startswith(self.file_prefixes):
            return None
        return redirect('usher_home')
