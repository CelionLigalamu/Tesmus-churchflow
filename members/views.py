from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from attendance.models import Attendance
from .models import Member
from .forms import MemberForm, MinistryRoleForm
from .models import DEFAULT_MINISTRY_ROLES, MinistryRole
from .services import ensure_default_ministry_roles, generate_reference_number
from audit.services import log_action


def can_manage_roles(user):
    return user.is_authenticated and not user.is_tesmus_staff and bool(user.church_id) and user.scope_type == 'church'


@login_required
def member_list(request):
    search_query = request.GET.get('q', '').strip()

    members = Member.objects.for_user(request.user).select_related(
        'region',
        'branch',
    ).prefetch_related('ministry_roles').order_by('full_name', 'reference_number')

    if search_query:
        members = members.filter(
            Q(full_name__icontains=search_query)
            | Q(reference_number__icontains=search_query)
        )
    total_members = members.count()
    page_obj = Paginator(members, 25).get_page(request.GET.get('page'))
    query_params = request.GET.copy()
    query_params.pop('page', None)

    context = {
        'members': page_obj,
        'page_obj': page_obj,
        'query_params': query_params.urlencode(),
        'search_query': search_query,
        'total_members': total_members,
    }
    return render(request, 'members/member_list.html', context)


@login_required
def member_create(request):
    if request.user.is_tesmus_staff or not request.user.church_id:
        return redirect('home')
    form = MemberForm(request.user, request.POST or None)
    if request.method == 'POST' and form.is_valid():
        member = form.save(commit=False)
        member.church = request.user.church
        member.reference_number = generate_reference_number(member.church_id)
        member.save()
        form.save_m2m()
        log_action(request.user, 'member_created', church=member.church, details=f'{member.reference_number} - {member.full_name}')
        messages.success(request, f'{member.full_name} was registered successfully.')
        return redirect('member_detail', pk=member.pk)
    return render(request, 'members/member_form.html', {'form': form})


@login_required
def member_edit(request, pk):
    if request.user.is_tesmus_staff or not request.user.church_id:
        return redirect('home')
    member = get_object_or_404(Member.objects.for_user(request.user), pk=pk)
    form = MemberForm(request.user, request.POST or None, instance=member)
    if request.method == 'POST' and form.is_valid():
        member = form.save()
        log_action(request.user, 'member_updated', church=member.church, details=f'{member.reference_number} - {member.full_name}')
        messages.success(request, f'{member.full_name} was updated successfully.')
        return redirect('member_detail', pk=member.pk)
    return render(request, 'members/member_form.html', {'form': form, 'member': member})


@login_required
def ministry_role_list(request):
    if not can_manage_roles(request.user):
        messages.error(request, 'Only church-wide administrators can manage ministry roles.')
        return redirect('member_list')
    roles = ensure_default_ministry_roles(request.user.church).prefetch_related('members')
    return render(request, 'members/ministry_role_list.html', {'roles': roles})


@login_required
def ministry_role_create(request):
    if not can_manage_roles(request.user):
        messages.error(request, 'Only church-wide administrators can manage ministry roles.')
        return redirect('member_list')
    form = MinistryRoleForm(request.user.church, request.POST or None)
    if request.method == 'POST' and form.is_valid():
        role = form.save(commit=False)
        role.church = request.user.church
        last_order = request.user.church.ministry_roles.order_by('-sort_order').values_list('sort_order', flat=True).first()
        role.sort_order = max(last_order or 0, len(DEFAULT_MINISTRY_ROLES) * 10) + 10
        role.save()
        messages.success(request, f'{role.name} was created.')
        return redirect('ministry_role_list')
    return render(request, 'members/ministry_role_form.html', {'form': form, 'role': None})


@login_required
def ministry_role_edit(request, pk):
    if not can_manage_roles(request.user):
        messages.error(request, 'Only church-wide administrators can manage ministry roles.')
        return redirect('member_list')
    role = get_object_or_404(MinistryRole, pk=pk, church=request.user.church)
    form = MinistryRoleForm(request.user.church, request.POST or None, instance=role)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f'{role.name} was updated.')
        return redirect('ministry_role_list')
    return render(request, 'members/ministry_role_form.html', {'form': form, 'role': role})


@login_required
def ministry_role_delete(request, pk):
    if not can_manage_roles(request.user):
        messages.error(request, 'Only church-wide administrators can manage ministry roles.')
        return redirect('member_list')
    role = get_object_or_404(MinistryRole, pk=pk, church=request.user.church)
    if request.method == 'POST':
        name = role.name
        role.delete()
        messages.success(request, f'{name} was removed.')
    return redirect('ministry_role_list')


@login_required
def member_detail(request, pk):
    member = get_object_or_404(
        Member.objects.for_user(request.user).select_related('region', 'branch').prefetch_related('ministry_roles'),
        pk=pk,
    )
    attendance_history = Attendance.objects.for_user(request.user).filter(
        member=member,
    ).select_related('service').order_by('-service__date', '-checked_in_at')

    return render(
        request,
        'members/member_detail.html',
        {
            'member': member,
            'attendance_history': attendance_history,
        },
    )
