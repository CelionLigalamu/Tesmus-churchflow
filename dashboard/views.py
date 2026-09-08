from analytics.services import dashboard_summary
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from analytics.services import church_summary
from audit.models import AuditLog


@login_required
def home(request):
    user = request.user
    if user.is_tesmus_staff:
        return render(request, 'dashboard/tesmus_home.html')

    try:
        trend_days = int(request.GET.get('attendance_range', 7))
    except (TypeError, ValueError):
        trend_days = 7
    trend_days = trend_days if trend_days in {7, 30, 90} else 7
    summary = dashboard_summary(user.church, trend_days=trend_days)
    return render(request, 'dashboard/church_home.html', {'summary': summary})


@login_required
def activity_list(request):
    activities = AuditLog.objects.filter(
        church=request.user.church,
    ).select_related('user').order_by('-created_at')
    return render(
        request,
        'dashboard/activity.html',
        {'activities': activities},
    )
