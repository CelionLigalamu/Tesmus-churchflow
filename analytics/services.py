from django.utils import timezone
from pastoral.models import PastoralFollowUp
from services.models import Service
from audit.models import AuditLog
from django.db.models import Count, Q
from members.models import Member
from attendance.models import Attendance
from visitors.models import Visitor


def church_summary(church):
    total_members = Member.objects.filter(church=church, status='active').count()
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
    members = Member.objects.filter(church=region.church, region=region, status='active')
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

def dashboard_summary(church):
    summary = church_summary(church)
    summary['pending_followups'] = PastoralFollowUp.objects.filter(
        church=church, status__in=['pending', 'in_progress']
    ).count()
    summary['upcoming_services'] = Service.objects.filter(
        church=church, date__gte=timezone.now().date()
    ).order_by('date')[:5]
    summary['recent_activity'] = AuditLog.objects.filter(
        church=church
    ).order_by('-created_at')[:6]
    return summary