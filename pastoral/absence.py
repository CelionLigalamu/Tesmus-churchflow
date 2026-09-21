"""Find members who have stopped coming and alert their pastors.

Each time a service closes:

1. Members who attended close their open "missed services" follow-up as
   Returned.
2. Every member marked absent is checked. One who has now missed the church's
   chosen number of services in a row (Church setup; 3 by default) gets one open
   follow-up in Pastoral Care, assigned to their region's pastors, and those
   pastors are texted once. Further absences do not text them again.
3. A member whose region has no pastor still gets a follow-up, and the
   church's administrators are told in their notifications instead.

Only the church's own records are used, so every church works the same way
without any per-church code.
"""
import logging
from functools import partial

from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from attendance.models import Attendance
from members.models import Member
from messaging.services import get_system_template, render_sms, send_message
from notifications.services import notify_followup_unassigned

from .models import PastoralFollowUp

logger = logging.getLogger(__name__)

# How far back a run of missed services is counted.
STREAK_LOOKBACK = 52
AUTHOR = 'ChurchFlow'


def missed_in_a_row(member):
    """How many of this member's most recent closed services they missed in a row."""
    results = (
        Attendance.objects.filter(member=member, result__in=('present', 'absent'))
        .order_by(F('service__date').desc(), F('service__start_time').desc(nulls_last=True), '-service_id')
        .values_list('result', flat=True)[:STREAK_LOOKBACK]
    )
    streak = 0
    for result in results:
        if result != 'absent':
            break
        streak += 1
    return streak


def check_absences_after_commit(service):
    """Run the absence check once the closed service's attendance is saved."""
    transaction.on_commit(partial(process_closed_service, service), robust=True)


def process_closed_service(service):
    """Close follow-ups for members who came back, then flag members who stopped coming."""
    try:
        close_returned_members(service)
    except Exception:
        logger.exception('Could not close returned follow-ups for service %s', service.pk)
    try:
        return flag_absent_members(service)
    except Exception:
        logger.exception('Could not check absences for service %s', service.pk)
        return []


def close_returned_members(service):
    present_ids = Attendance.objects.filter(
        service=service, result='present', member__isnull=False,
    ).values_list('member_id', flat=True)
    returned = PastoralFollowUp.objects.filter(
        church_id=service.church_id,
        reason=PastoralFollowUp.MISSED_SERVICES,
        status__in=PastoralFollowUp.OPEN_STATUSES,
        member_id__in=present_ids,
    )
    closed = 0
    for followup in returned:
        followup.status = 'returned'
        followup.closed_at = timezone.now()
        followup.add_note(f'Came back to {service.name} on {service.date:%d %b %Y}. Closed automatically.', AUTHOR)
        followup.save(update_fields=['status', 'closed_at', 'notes'])
        closed += 1
    return closed


def flag_absent_members(service):
    church = service.church
    threshold = church.absence_alert_after
    if not threshold:
        return []

    absent_members = Member.objects.filter(
        church_id=church.pk, attendances__service=service, attendances__result='absent',
    ).select_related('region').distinct()
    opened = []
    for member in absent_members:
        streak = missed_in_a_row(member)
        if streak < threshold:
            continue
        if PastoralFollowUp.objects.filter(
            member=member, reason=PastoralFollowUp.MISSED_SERVICES, status__in=PastoralFollowUp.OPEN_STATUSES,
        ).exists():
            continue  # Already being followed up: the pastor is not texted again.

        pastors = [p for p in member.region.pastor_members() if p.pk != member.pk] if member.region_id else []
        followup = PastoralFollowUp(
            church=church, member=member, reason=PastoralFollowUp.MISSED_SERVICES,
            missed_count=streak, trigger_service=service, status='pending',
            follow_up_date=timezone.localdate(),
        )
        followup.add_note(
            f'Missed the last {streak} services in a row (latest: {service.name}, {service.date:%d %b %Y}).', AUTHOR,
        )
        if pastors:
            followup.add_note('Pastors alerted by SMS: ' + ', '.join(p.full_name for p in pastors) + '.', AUTHOR)
        elif member.region_id:
            followup.add_note(f'No pastor is set for {member.region.name}, so no pastor could be texted.', AUTHOR)
        else:
            followup.add_note('This member has no region, so no pastor could be texted.', AUTHOR)
        try:
            with transaction.atomic():
                followup.save()
        except IntegrityError:
            continue  # Another check opened one for this member at the same moment.
        followup.pastors.set(pastors)

        if pastors:
            alert_pastors(followup, pastors)
        else:
            notify_followup_unassigned(followup)
        opened.append(followup)
    return opened


def alert_pastors(followup, pastors):
    """Text each pastor once about this follow-up. None when the church switched the text off."""
    template = get_system_template(followup.church, 'pastor_followup_alert')
    if template is None:
        return []
    member = followup.member
    results = []
    for pastor in pastors:
        if not pastor.phone_number:
            continue
        body = render_sms(
            template,
            pastor_name=pastor.full_name,
            member_name=member.full_name,
            reference_number=member.reference_number,
            member_phone=member.phone_number,
            region_name=member.region.name if member.region_id else '',
            missed_count=followup.missed_count,
            church_name=followup.church.name,
        )
        try:
            results.append(send_message(
                followup.church, pastor.phone_number, body, template=template,
                # One alert per pastor per follow-up, even if the check runs again.
                dedupe_key=f'pastoral-alert:{followup.pk}:{pastor.pk}',
                audience_label=f'Follow-up alert - {member.reference_number}',
            ))
        except Exception:
            logger.exception('Could not text pastor %s about follow-up %s', pastor.pk, followup.pk)
    return results
