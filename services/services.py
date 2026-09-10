from django.db import transaction
from members.models import Member
from attendance.models import Attendance
from messaging.services import (
    get_attendance_template,
    render_attendance_message,
    send_message,
)


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

    service.status = 'finalized'
    service.save(update_fields=['status'])
