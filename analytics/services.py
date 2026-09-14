from datetime import datetime, timedelta
from math import floor, log10

from django.utils import timezone
from pastoral.models import PastoralFollowUp
from services.models import Service
from services.services import sync_and_finalize_service
from audit.models import AuditLog
from django.db.models import Count, Q
from members.models import Member
from attendance.models import Attendance
from visitors.models import Visitor


def dashboard_service_status(service, now=None):
    """Return the time-aware status shown on the dashboard."""
    sync_and_finalize_service(service, now=now)
    return 'closed' if service.status == 'finalized' else service.status


def decorate_dashboard_service(service, now=None):
    status = dashboard_service_status(service, now=now)
    service.dashboard_status = status
    service.dashboard_status_label = status.title()
    return service


def church_summary(church):
    total_members = Member.objects.filter(church=church).count()
    total_visitors = Visitor.objects.filter(church=church).count()

    attendance_qs = Attendance.objects.filter(church=church, member__isnull=False)
    present_count = attendance_qs.filter(result='present').count()
    absent_count = attendance_qs.filter(result='absent').count()

    total_marked = present_count + absent_count
    attendance_rate = round((present_count / total_marked) * 100, 1) if total_marked else 0

    return {
        'total_members': total_members,
        'total_visitors': total_visitors,
        'present': present_count,
        'absent': absent_count,
        'attendance_rate': attendance_rate,
    }


def service_summary(service):
    attendances = service.attendances.filter(member__isnull=False)
    present = attendances.filter(result='present').count()
    absent = attendances.filter(result='absent').count()
    total = present + absent
    rate = round((present / total) * 100, 1) if total else 0

    return {
        'service': service.name,
        'date': service.date,
        'registered': total,
        'present': present,
        'absent': absent,
        'attendance_rate': rate,
    }


def region_summary(region):
    members = Member.objects.filter(church=region.church, region=region)
    attendances = Attendance.objects.filter(church=region.church, member__in=members)
    present = attendances.filter(result='present').count()
    absent = attendances.filter(result='absent').count()
    total = present + absent
    rate = round((present / total) * 100, 1) if total else 0

    return {
        'region': region.name,
        'members': members.count(),
        'present': present,
        'absent': absent,
        'attendance_rate': rate,
    }

def dashboard_summary(
    church,
    trend_days=7,
    start_date=None,
    end_date=None,
    region=None,
):
    today = timezone.localdate()
    if start_date is None or end_date is None:
        end_date = today
        start_date = today - timedelta(days=trend_days - 1)

    member_filter = {'church': church}
    person_filter = Q(church=church)
    service_filter = Q(church=church)
    # Attendance is counted by where the member lives (the region recorded on
    # each attendance), not by the service, which serves the whole church.
    attendance_filter = Q()
    if region:
        member_filter['region'] = region
        person_filter &= Q(region=region)
        service_filter &= Q(region=region) | Q(region__isnull=True)
        attendance_filter &= Q(region=region)

    summary = {
        'total_members': Member.objects.filter(**member_filter).count(),
        'present': 0,
        'absent': 0,
        'attendance_rate': 0,
        'total_visitors': Visitor.objects.filter(person_filter).filter(
            first_visit_date__date__range=(start_date, end_date)
        ).count(),
        'pending_followups': PastoralFollowUp.objects.filter(
            church=church,
            status__in=['pending', 'in_progress'],
            member__in=Member.objects.filter(**member_filter),
            created_at__date__range=(start_date, end_date),
        ).count(),
    }
    attendance_qs = Attendance.objects.filter(
        church=church,
        service__date__range=(start_date, end_date),
    ).filter(attendance_filter).filter(member__isnull=False)
    summary['present'] = attendance_qs.filter(result='present').count()
    summary['absent'] = attendance_qs.filter(result='absent').count()
    marked_total = summary['present'] + summary['absent']
    summary['attendance_rate'] = round(
        (summary['present'] / marked_total) * 100, 1
    ) if marked_total else 0

    summary['upcoming_services'] = Service.objects.filter(
        service_filter, date__gte=today,
    ).order_by('date', 'start_time', 'created_at')[:5]
    now = timezone.localtime()
    today_services = [
        decorate_dashboard_service(service, now=now)
        for service in Service.objects.filter(
            service_filter,
            date=now.date(),
        ).order_by('start_time', 'created_at')
    ]
    open_services = [
        service for service in today_services
        if service.dashboard_status == 'open'
    ]
    upcoming_services_today = [
        service for service in today_services
        if service.dashboard_status == 'upcoming'
    ]
    closed_services_today = [
        service for service in today_services
        if service.dashboard_status == 'closed'
    ]
    summary['today_service'] = (
        open_services[0]
        if open_services
        else upcoming_services_today[0]
        if upcoming_services_today
        else closed_services_today[-1]
        if closed_services_today
        else None
    )
    summary['upcoming_services'] = [
        decorate_dashboard_service(service, now=now)
        for service in summary['upcoming_services']
    ]

    # Build a complete calendar series from real attendance rows.  Empty days
    # remain visible as zeroes instead of disappearing from the chart.
    today = timezone.localdate()
    trend_start = start_date
    trend_days = (end_date - start_date).days + 1
    attendance_by_day = {
        row['service__date']: row['present']
        for row in Attendance.objects.filter(
            church=church,
            service__date__range=(trend_start, today),
            member__isnull=False,
        ).filter(attendance_filter).filter(service__date__range=(start_date, end_date)).values('service__date').annotate(
            present=Count('id', filter=Q(result='present')),
        )
    }
    trend_counts = [
        (trend_start + timedelta(days=index), attendance_by_day.get(
            trend_start + timedelta(days=index), 0
        ))
        for index in range(trend_days)
    ]

    max_present = max([present for _, present in trend_counts] or [0])
    # Keep the scale readable as attendance grows: 3 stays 0–3, while 346
    # becomes a clean 0–200–400 scale instead of an awkward 0–173–346.
    if max_present <= 10:
        chart_max = max(max_present, 1)
    else:
        magnitude = 10 ** floor(log10(max_present))
        chart_max = next(
            step * magnitude
            for step in (1, 2, 5, 10)
            if step * magnitude >= max_present
        )
    chart_width = 640
    chart_left = 24
    chart_right = 616
    chart_baseline = 156
    chart_height = 112
    step = (chart_right - chart_left) / max(trend_days - 1, 1)
    trend = []
    label_step = 1 if trend_days == 7 else 5 if trend_days == 30 else 15
    for index, (day, present) in enumerate(trend_counts):
        x = round(chart_left + (index * step), 1)
        y = round(chart_baseline - ((present / chart_max) * chart_height), 1)
        trend.append({
            'label': day.strftime('%a'),
            'date_label': f"{day.strftime('%b')} {day.day}",
            'present': present,
            'x': x,
            'y': y,
            'show_label': index == 0 or index == trend_days - 1 or index % label_step == 0,
        })
    summary['attendance_trend'] = trend
    summary['attendance_range'] = trend_days
    summary['attendance_y_ticks'] = [
        {'value': chart_max, 'y': 44},
        {'value': round(chart_max / 2), 'y': 100},
        {'value': 0, 'y': 156},
    ]
    summary['attendance_chart_points'] = ' '.join(
        f"{point['x']},{point['y']}" for point in trend
    )
    summary['recent_activity'] = AuditLog.objects.filter(church=church).order_by('-created_at')[:6]
    return summary
