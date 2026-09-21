"""Create and refresh notifications.

The notify_* functions are called from the code path where the event happens
(sending a text, a member registering). They log problems instead of raising,
so a notification failure can never stop that original action.
"""
import logging

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db.models import F, Q
from django.utils import timezone

from .models import Notification

logger = logging.getLogger(__name__)

OPEN_FOLLOWUP_STATUSES = ('pending', 'in_progress')
FOLLOWUP_SYNC_SECONDS = 600


def _people(church):
    return get_user_model().objects.filter(church=church, is_active=True, is_tesmus_staff=False)


def church_admins(church):
    """Church-wide administrators - the people responsible for the whole church."""
    return _people(church).filter(scope_type='church')


def people_responsible_for_member(church, member):
    """Church-wide admins, plus anyone scoped to the member's region."""
    scope = Q(scope_type='church')
    if member.region_id:
        scope |= Q(scope_type='region', scope_region_id=member.region_id)
    return _people(church).filter(scope).distinct()


def _add_to_group(recipients, church, kind, group_key, detail=''):
    """Count the event on each person's unread notification, or start one."""
    now = timezone.now()
    detail = (detail or '')[:255]
    for person in recipients:
        updated = Notification.objects.filter(
            recipient=person, group_key=group_key, read_at__isnull=True,
        ).update(count=F('count') + 1, detail=detail, updated_at=now)
        if not updated:
            Notification.objects.create(
                church=church, recipient=person, kind=kind,
                group_key=group_key, detail=detail, updated_at=now,
            )


def notify_sms_failed(sms_message):
    try:
        church = sms_message.church
        _add_to_group(
            church_admins(church), church, Notification.SMS_FAILED,
            group_key=f'{Notification.SMS_FAILED}:{church.id}:{timezone.localdate()}',
            detail=sms_message.failure_reason or 'The SMS provider rejected the message.',
        )
    except Exception:
        logger.exception('Could not record a failed text message notification')


def notify_member_self_registered(member):
    try:
        church = member.church
        _add_to_group(
            people_responsible_for_member(church, member), church, Notification.MEMBER_SELF_REGISTERED,
            group_key=f'{Notification.MEMBER_SELF_REGISTERED}:{church.id}:{timezone.localdate()}',
            detail=f'Latest: {member.full_name} ({member.reference_number})',
        )
    except Exception:
        logger.exception('Could not record a self-registration notification')


def notify_followup_unassigned(followup):
    """A member stopped coming but their region has no pastor to text: tell the admins."""
    try:
        church = followup.church
        member = followup.member
        where = f'no pastor is set for {member.region.name}' if member.region_id else 'they have no region'
        _add_to_group(
            church_admins(church), church, Notification.FOLLOWUP_UNASSIGNED,
            group_key=f'{Notification.FOLLOWUP_UNASSIGNED}:{church.id}:{timezone.localdate()}',
            detail=f'Latest: {member.full_name} ({member.reference_number}) - {where}',
        )
    except Exception:
        logger.exception('Could not record a follow-up without a pastor notification')


def sync_followup_notifications(church, today=None):
    """Keep one 'due or overdue' notification per person, per day, up to date.

    Church-wide admins see every open follow-up; anyone else sees the ones
    assigned to them. Safe to run repeatedly.
    """
    from pastoral.models import PastoralFollowUp

    today = today or timezone.localdate()
    group_key = f'{Notification.FOLLOWUP_DUE}:{church.id}:{today}'
    due = PastoralFollowUp.objects.filter(
        church=church, status__in=OPEN_FOLLOWUP_STATUSES, follow_up_date__lte=today,
    )

    targets = {person.id: (person, due) for person in church_admins(church)}
    assignees = _people(church).filter(assigned_followups__in=due).exclude(id__in=targets.keys()).distinct()
    for person in assignees:
        targets[person.id] = (person, due.filter(assigned_to=person))

    now = timezone.now()
    for person, queryset in targets.values():
        total = queryset.count()
        existing = Notification.objects.filter(recipient=person, group_key=group_key).first()
        if total == 0:
            if existing and existing.read_at is None:
                existing.delete()
            continue

        overdue = queryset.filter(follow_up_date__lt=today).count()
        detail = f'{overdue} overdue, {total - overdue} due today'
        if existing is None:
            Notification.objects.create(
                church=church, recipient=person, kind=Notification.FOLLOWUP_DUE,
                group_key=group_key, count=total, detail=detail, updated_at=now,
            )
        elif existing.count != total or existing.detail != detail:
            if total > existing.count:
                existing.read_at = None  # more are due than when it was read
            existing.count = total
            existing.detail = detail
            existing.updated_at = now
            existing.save(update_fields=['count', 'detail', 'updated_at', 'read_at'])

    # People with nothing due any more (e.g. reassigned) lose today's unread reminder.
    Notification.objects.filter(group_key=group_key, read_at__isnull=True).exclude(
        recipient_id__in=targets.keys(),
    ).delete()


def refresh_followups_if_due(church):
    """Run the follow-up check at most every few minutes per church."""
    if cache.add(f'notifications:followups-synced:{church.id}', True, FOLLOWUP_SYNC_SECONDS):
        try:
            sync_followup_notifications(church)
        except Exception:
            logger.exception('Could not refresh follow-up notifications')
