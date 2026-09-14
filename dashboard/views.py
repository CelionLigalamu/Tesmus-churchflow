from datetime import date, timedelta

from analytics.services import dashboard_summary
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import redirect, render
from analytics.services import church_summary
from audit.models import AuditLog
from django.utils import timezone
from accounts.permissions import user_can_access_region
from tenants.models import Region
from messaging.models import SMSTemplate, SMSConfiguration


def public_home(request):
    return render(request, 'dashboard/public_home.html')


def tesmus_staff_landing(request):
    """Tesmus staff manage the platform in Django admin, so send them there.

    Staff without Django admin access would only be refused by admin, so they
    keep the platform page instead.
    """
    if request.user.is_staff:
        return redirect('admin:index')
    return render(request, 'dashboard/tesmus_home.html')


@login_required
def home(request):
    user = request.user
    if user.is_tesmus_staff:
        return tesmus_staff_landing(request)

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
    if user.scope_type == 'region' and user.scope_region_id:
        regions = regions.filter(pk=user.scope_region_id)

    selected_region = None
    region_id = request.GET.get('region', '')
    if region_id:
        candidate = regions.filter(pk=region_id).first()
        if candidate and user_can_access_region(user, candidate):
            selected_region = candidate

    # Scope is enforced here, independent of what the browser sends.
    if user.scope_type == 'region' and user.scope_region_id:
        selected_region = regions.filter(pk=user.scope_region_id).first()

    summary = dashboard_summary(
        user.church,
        start_date=start_date,
        end_date=end_date,
        region=selected_region,
    )
    return render(request, 'dashboard/church_home.html', {
        'summary': summary,
        'regions': regions,
        'selected_region': selected_region,
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
    if request.user.is_tesmus_staff:
        return tesmus_staff_landing(request)
    if not request.user.church_id:
        return render(request, 'dashboard/tesmus_home.html')

    return render(request, 'dashboard/settings.html', {
        'church': request.user.church,
        'template_count': SMSTemplate.objects.filter(church=request.user.church).count(),
        'sms_configured': hasattr(request.user.church, 'sms_config'),
        'can_manage_templates': request.user.scope_type == 'church',
    })
