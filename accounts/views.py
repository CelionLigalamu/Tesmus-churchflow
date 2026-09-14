from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.http import JsonResponse
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render, resolve_url

from django.db import IntegrityError

from audit.services import log_action
from members.models import Member
from tenants.models import Church

from .forms import ChurchAuthenticationForm
from .models import User
from .usher_forms import UsherCreateForm, UsherLinkForm, UsherRoleForm, members_without_sign_in


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


def can_manage_ushers(user):
    return (
        user.is_authenticated and not user.is_tesmus_staff and not user.is_usher
        and bool(user.church_id) and user.scope_type == 'church'
    )


def _refuse_ushers(request):
    messages.error(request, 'Only church-wide administrators can manage ushers.')
    return redirect('home')


@login_required
def usher_list(request):
    """Church-wide administrators give members an usher sign-in and manage those sign-ins."""
    if not can_manage_ushers(request.user):
        return _refuse_ushers(request)
    church = request.user.church
    initial = {}
    requested_member = request.GET.get('member', '')
    if requested_member.isdigit():
        initial['member'] = requested_member
    form = UsherCreateForm(church, request.POST or None, initial=initial)
    if request.method == 'POST' and form.is_valid():
        try:
            usher = form.save()
        except IntegrityError:
            messages.error(request, 'That member was given a sign-in a moment ago. Check the list of ushers below.')
            return redirect('usher_list')
        log_action(request.user, 'usher_created', church=church,
                   details=f'{usher.username} for {usher.member.reference_number} - {usher.member.full_name}')
        role_note = f' They now have the {church.usher_role.name} ministry role.' if church.usher_role_id else ''
        messages.success(
            request,
            f'{usher.first_name} can now sign in at your church sign-in page and use the usher check-in screen.{role_note}',
        )
        return redirect('usher_list')

    members_needing_sign_in = Member.objects.none()
    if church.usher_role_id:
        members_needing_sign_in = Member.objects.filter(
            church=church, ministry_roles=church.usher_role_id, user_account__isnull=True,
        ).order_by('full_name')
    return render(request, 'accounts/usher_list.html', {
        'form': form,
        'ushers': User.objects.filter(church=church, is_usher=True).select_related('member').order_by(
            '-is_active', 'first_name', 'username',
        ),
        'usher_role': church.usher_role,
        'role_form': UsherRoleForm(instance=church),
        'members_needing_sign_in': members_needing_sign_in,
        'church_login_url': request.build_absolute_uri(reverse('church_login', args=[church.slug])),
    })


@login_required
def usher_link(request, pk):
    """Link an usher sign-in made before sign-ins were tied to members."""
    if not can_manage_ushers(request.user):
        return _refuse_ushers(request)
    church = request.user.church
    usher = get_object_or_404(User, pk=pk, church_id=church.pk, is_usher=True)
    if usher.member_id:
        messages.info(request, f'{usher.first_name or usher.username} is already linked to {usher.member.full_name}.')
        return redirect('usher_list')

    initial = {}
    same_name = members_without_sign_in(church).filter(full_name__iexact=usher.first_name.strip()).first() if usher.first_name else None
    if same_name:
        initial['member'] = same_name.pk
    form = UsherLinkForm(church, usher, request.POST or None, initial=initial)
    if request.method == 'POST' and form.is_valid():
        try:
            usher = form.save()
        except IntegrityError:
            messages.error(request, 'That member was given a sign-in a moment ago. Choose another member.')
            return redirect('usher_link', pk=pk)
        log_action(request.user, 'usher_linked', church=church,
                   details=f'{usher.username} linked to {usher.member.reference_number} - {usher.member.full_name}')
        messages.success(request, f'The sign-in "{usher.username}" is now linked to {usher.member.full_name}.')
        return redirect('usher_list')
    return render(request, 'accounts/usher_link.html', {'form': form, 'usher': usher})


@login_required
@require_POST
def usher_role_update(request):
    if not can_manage_ushers(request.user):
        return _refuse_ushers(request)
    form = UsherRoleForm(request.POST, instance=request.user.church)
    if form.is_valid():
        church = form.save()
        role = church.usher_role
        log_action(request.user, 'usher_role_updated', church=church, details=role.name if role else 'none')
        if role:
            messages.success(request, f'Members given an usher sign-in will now get the {role.name} ministry role.')
        else:
            messages.success(request, 'Usher sign-ins will no longer add a ministry role.')
    else:
        messages.error(request, 'Choose one of your ministry roles.')
    return redirect('usher_list')


@login_required
@require_POST
def usher_toggle_active(request, pk):
    if not can_manage_ushers(request.user):
        messages.error(request, 'Only church-wide administrators can manage ushers.')
        return redirect('home')
    usher = get_object_or_404(User, pk=pk, church_id=request.user.church_id, is_usher=True)
    usher.is_active = not usher.is_active
    usher.save(update_fields=['is_active'])
    name = usher.get_short_name() or usher.username
    log_action(request.user, 'usher_turned_on' if usher.is_active else 'usher_turned_off',
               church=request.user.church, details=usher.username)
    if usher.is_active:
        messages.success(request, f'{name} can sign in again.')
    else:
        messages.success(request, f'{name} can no longer sign in.')
    return redirect('usher_list')
