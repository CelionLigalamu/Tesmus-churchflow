import logging
from functools import partial

from django.db import transaction
from django.db.models import Count, OuterRef, Q, Subquery
from members.models import Member
from attendance.models import Attendance
from messaging.services import (
    get_attendance_template,
    get_system_template,
    render_attendance_message,
    send_message,
    send_region_summary_sms,
)
from tenants.models import Region

logger = logging.getLogger(__name__)


def sync_and_finalize_service(service, now=None):
    service.sync_status(now=now)
    if service.status == 'closed':
        finalize_service(service)
    return service


@transaction.atomic
def finalize_service(service):
    if service.status == 'finalized':
        return

    attended_member_ids = set(Attendance.objects.filter(
        service=service, member__isnull=False
    ).values_list('member_id', flat=True))

    all_members = Member.objects.filter(church_id=service.church_id)

    absent_members = all_members.exclude(id__in=attended_member_ids)
    absent_template = get_attendance_template(service.church, 'absent')

    for member in absent_members:
        Attendance.objects.get_or_create(
            church=service.church,
            service=service,
            member=member,
            defaults={
                'method': 'manual',
                'result': 'absent',
            },
        )
        if absent_template:
            send_message(
                service.church,
                member.phone_number,
                render_attendance_message(absent_template, member, service),
                template=absent_template,
                dedupe_key=f'attendance:{service.pk}:{member.pk}:absent',
            )

    Attendance.objects.filter(
        service=service, member_id__in=attended_member_ids, result=''
    ).update(result='present')

    present_template = get_attendance_template(service.church, 'present')
    if present_template:
        present_members = Member.objects.filter(id__in=attended_member_ids)
        for member in present_members:
            send_message(
                service.church,
                member.phone_number,
                render_attendance_message(present_template, member, service),
                template=present_template,
                dedupe_key=f'attendance:{service.pk}:{member.pk}:present',
            )

    # Members who checked in before being given a region are counted in the
    # region they belong to now that the service has closed.
    Attendance.objects.filter(
        service=service, region__isnull=True, member__region__isnull=False,
    ).update(region=Subquery(
        Member.objects.filter(pk=OuterRef('member_id')).values('region')[:1]
    ))

    service.status = 'finalized'
    service.save(update_fields=['status'])

    # Pastors are texted only once the attendance above is safely saved.
    transaction.on_commit(partial(send_region_summaries, service), robust=True)


def region_attendance_breakdown(service):
    """Present, absent and rate for each region with members in a service."""
    rows = Attendance.objects.filter(
        service=service, member__isnull=False, region__isnull=False,
    ).values('region').annotate(
        present=Count('id', filter=Q(result='present')),
        absent=Count('id', filter=Q(result='absent')),
    ).order_by()
    regions = Region.objects.in_bulk([row['region'] for row in rows])

    breakdown = []
    for row in rows:
        total = row['present'] + row['absent']
        if not total:
            continue
        breakdown.append({
            'region': regions[row['region']],
            'total_members': total,
            'present': row['present'],
            'absent': row['absent'],
            'attendance_rate': round(row['present'] * 100 / total),
        })
    return sorted(breakdown, key=lambda stats: stats['region'].name.lower())


def send_region_summaries(service):
    """Text each region's pastors that region's statistics for a service.

    A problem with one pastor's message is logged and never stops the others.
    Returns the SMS records created or found.
    """
    template = get_system_template(service.church, 'region_attendance_summary')
    if template is None:
        return []

    results = []
    for stats in region_attendance_breakdown(service):
        region = stats['region']
        for pastor in region.pastor_members():
            try:
                results.append(send_region_summary_sms(pastor, stats, service, template))
            except Exception:
                logger.exception(
                    'Could not send the %s attendance summary for service %s to pastor %s',
                    region.name, service.pk, pastor.pk,
                )
    return results
