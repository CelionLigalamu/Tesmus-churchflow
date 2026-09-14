"""Regions where members live, and the pastors texted each region's statistics."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Prefetch
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from audit.services import log_action
from members.models import Member
from messaging.services import get_system_template

from .forms import RegionForm, RegionMergeForm, RegionPastorRoleForm
from .models import Region
from .services import merge_regions, region_usage


def can_manage_regions(user):
    return user.is_authenticated and not user.is_tesmus_staff and bool(user.church_id) and user.scope_type == 'church'


def _refuse(request):
    messages.error(request, 'Only church-wide administrators can manage regions and pastors.')
    return redirect('home')


def _pastor_names(region):
    names = region.pastor_members().values_list('full_name', flat=True)
    return ', '.join(names) or 'none'


def _role_pastors(church, region=None):
    """The church's pastor role, and the members holding it who live in `region`."""
    role = church.region_pastor_role
    if not role or region is None or not region.pk:
        return role, []
    return role, list(
        Member.objects.filter(church=church, region=region, ministry_roles=role).order_by('full_name')
    )


@login_required
def region_list(request):
    if not can_manage_regions(request.user):
        return _refuse(request)
    church = request.user.church
    regions = Region.objects.filter(church=church).annotate(
        member_count=Count('members', distinct=True),
    ).prefetch_related(
        Prefetch('pastors', queryset=Member.objects.order_by('full_name')),
    ).order_by('name')

    rows = []
    for region in regions:
        picked = list(region.pastors.all())
        role, holders = _role_pastors(church, region)
        picked_ids = {member.pk for member in picked}
        rows.append({
            'region': region,
            'picked': picked,
            'by_role': [member for member in holders if member.pk not in picked_ids],
        })

    return render(request, 'tenants/region_list.html', {
        'rows': rows,
        'role': church.region_pastor_role,
        'role_form': RegionPastorRoleForm(instance=church),
        'summary_template_active': get_system_template(church, 'region_attendance_summary') is not None,
    })


@login_required
@require_POST
def region_pastor_role(request):
    if not can_manage_regions(request.user):
        return _refuse(request)
    form = RegionPastorRoleForm(request.POST, instance=request.user.church)
    if form.is_valid():
        church = form.save()
        role = church.region_pastor_role
        log_action(request.user, 'region_pastor_role_updated', church=church, details=role.name if role else 'none')
        if role:
            messages.success(request, f"Members with the {role.name} role will be texted their own region's statistics.")
        else:
            messages.success(request, 'Only the pastors picked for each region will be texted.')
    else:
        messages.error(request, 'Choose one of your ministry roles.')
    return redirect('region_list')


@login_required
def region_merge(request, pk):
    """Merge a region typed two ways into one: everything moves, the old one is removed."""
    if not can_manage_regions(request.user):
        return _refuse(request)
    church = request.user.church
    source = get_object_or_404(Region, pk=pk, church=church)
    form = RegionMergeForm(source, request.POST or None)
    if request.method == 'POST' and form.is_valid():
        target = form.cleaned_data['target']
        source_name = source.name
        members_moved = merge_regions(source, target)
        log_action(request.user, 'regions_merged', church=church,
                   details=f'{source_name} merged into {target.name} ({members_moved} members moved)')
        messages.success(
            request,
            f'"{source_name}" was merged into "{target.name}". {members_moved} member(s) moved.',
        )
        return redirect('region_list')
    return render(request, 'tenants/region_merge.html', {
        'form': form,
        'region': source,
        'usage': region_usage(source),
    })


@login_required
def region_create(request):
    if not can_manage_regions(request.user):
        return _refuse(request)
    form = RegionForm(request.user.church, request.POST or None)
    if request.method == 'POST' and form.is_valid():
        region = form.save()
        log_action(request.user, 'region_created', church=request.user.church,
                   details=f'{region.name} - pastors: {_pastor_names(region)}')
        messages.success(request, f'Region "{region.name}" added.')
        return redirect('region_list')
    role, role_pastors = _role_pastors(request.user.church)
    return render(request, 'tenants/region_form.html', {
        'form': form, 'region': None, 'role': role, 'role_pastors': role_pastors,
    })


@login_required
def region_edit(request, pk):
    if not can_manage_regions(request.user):
        return _refuse(request)
    region = get_object_or_404(Region, pk=pk, church=request.user.church)
    form = RegionForm(request.user.church, request.POST or None, instance=region)
    if request.method == 'POST' and form.is_valid():
        region = form.save()
        log_action(request.user, 'region_updated', church=request.user.church,
                   details=f'{region.name} - pastors: {_pastor_names(region)}')
        messages.success(request, f'Region "{region.name}" saved.')
        return redirect('region_list')
    role, role_pastors = _role_pastors(request.user.church, region)
    return render(request, 'tenants/region_form.html', {
        'form': form, 'region': region, 'role': role, 'role_pastors': role_pastors,
    })
