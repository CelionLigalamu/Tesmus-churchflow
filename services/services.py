from django.db import transaction
from members.models import Member
from attendance.models import Attendance
from messaging.services import send_message


@transaction.atomic
def finalize_service(service):
    if service.status == 'finalized':
        return

    attended_member_ids = Attendance.objects.filter(
        service=service, member__isnull=False
    ).values_list('member_id', flat=True)

    all_active_members = Member.objects.filter(
        church_id=service.church_id, status='active'
    )

    absent_members = all_active_members.exclude(id__in=attended_member_ids)

    for member in absent_members:
        Attendance.objects.create(
            church=service.church,
            service=service,
            member=member,
            method='manual',
            result='absent',
        )
        body = (
            f"Mpendwa {member.full_name}, tulikukosa katika {service.name} ya leo. "
            f"Tunatumaini uko salama. Ikiwa kuna changamoto yoyote unayopitia, "
            f"tafadhali wasiliana na kanisa ili tuweze kukusaidia na kukuunga mkono."
        )
        send_message(service.church, member.phone_number, body)

    Attendance.objects.filter(
        service=service, member_id__in=attended_member_ids, result=''
    ).update(result='present')

    service.status = 'finalized'
    service.save(update_fields=['status'])