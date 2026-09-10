from datetime import date, timedelta

from analytics.services import dashboard_summary
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import render
from analytics.services import church_summary
from audit.models import AuditLog
from django.utils import timezone
from accounts.permissions import user_can_access_branch, user_can_access_region
from tenants.models import Branch, Region
from messaging.models import SMSTemplate, SMSConfiguration


@login_required
def home(request):
    user = request.user
    if user.is_tesmus_staff:
        return render(request, 'dashboard/tesmus_home.html')

    today = timezone.localdate()
    range_key = request.GET.get('range', 'today')
    custom_start = request.GET.get('start', '')
    custom_end = request.GET.get('end', '')
    filter_error = ''

    if range_key == '7d':
        start_date, end_date = today - timedelta(days=6), today
        range_label = '7 days'
    elif range_key == '30d':
        start_date, end_date = today - timedelta(days=29), today
        range_label = '30 days'
    elif range_key == '3m':
        start_date, end_date = today - timedelta(days=89), today
        range_label = '3 months'
    elif range_key == 'custom':
        try:
            start_date = date.fromisoformat(custom_start)
            end_date = date.fromisoformat(custom_end)
            if end_date < start_date:
                raise ValueError
            range_label = f'{start_date:%d %b %Y} – {end_date:%d %b %Y}'
        except (TypeError, ValueError):
            range_key = 'today'
            start_date = end_date = today
            range_label = 'Today'
            filter_error = 'Choose a valid start and end date.'
    else:
        range_key = 'today'
        start_date = end_date = today
        range_label = 'Today'

    regions = Region.objects.filter(church=user.church).order_by('name')
    branches = Branch.objects.filter(church=user.church).select_related('region').order_by('name')
    if user.scope_type == 'region' and user.scope_region_id:
        regions = regions.filter(pk=user.scope_region_id)
        branches = branches.filter(region_id=user.scope_region_id)
    elif user.scope_type == 'branch' and user.scope_branch_id:
        branches = branches.filter(pk=user.scope_branch_id)
        regions = regions.filter(pk=user.scope_branch.region_id)

    selected_region = None
    selected_branch = None
    region_id = request.GET.get('region', '')
    branch_id = request.GET.get('branch', '')
    if region_id:
        candidate = regions.filter(pk=region_id).first()
        if candidate and user_can_access_region(user, candidate):
            selected_region = candidate
    if branch_id:
        candidate = branches.filter(pk=branch_id).first()
        if candidate and user_can_access_branch(user, candidate):
            if not selected_region or candidate.region_id == selected_region.id:
                selected_branch = candidate
            else:
                filter_error = 'The selected branch does not belong to the selected region.'

    # Scope is enforced here, independent of what the browser sends.
    if user.scope_type == 'region' and user.scope_region_id:
        selected_region = regions.filter(pk=user.scope_region_id).first()
        selected_branch = selected_branch if selected_branch and selected_branch.region_id == selected_region.id else None
    elif user.scope_type == 'branch' and user.scope_branch_id:
        selected_branch = branches.filter(pk=user.scope_branch_id).first()
        selected_region = regions.filter(pk=selected_branch.region_id).first() if selected_branch else None

    if selected_region:
        branches = branches.filter(region=selected_region)
    summary = dashboard_summary(
        user.church,
        start_date=start_date,
        end_date=end_date,
        region=selected_region,
        branch=selected_branch,
    )
    return render(request, 'dashboard/church_home.html', {
        'summary': summary,
        'regions': regions,
        'branches': branches,
        'selected_region': selected_region,
        'selected_branch': selected_branch,
        'selected_range': range_key,
        'custom_start': custom_start,
        'custom_end': custom_end,
        'range_label': range_label,
        'filter_error': filter_error,
    })


@login_required
def activity_list(request):
    activities = AuditLog.objects.filter(
        church=request.user.church,
    ).select_related('user').order_by('-created_at')
    page_obj = Paginator(activities, 25).get_page(request.GET.get('page'))
    query_params = request.GET.copy()
    query_params.pop('page', None)
    return render(
        request,
        'dashboard/activity.html',
        {
            'activities': page_obj,
            'page_obj': page_obj,
            'query_params': query_params.urlencode(),
        },
    )


@login_required
def settings_page(request):
    if request.user.is_tesmus_staff or not request.user.church_id:
        return render(request, 'dashboard/tesmus_home.html')

    return render(request, 'dashboard/settings.html', {
        'church': request.user.church,
        'template_count': SMSTemplate.objects.filter(church=request.user.church).count(),
        'sms_configured': hasattr(request.user.church, 'sms_config'),
        'can_manage_templates': request.user.scope_type == 'church',
    })
