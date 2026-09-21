"""Send failed text messages again.

A resend retries the same message record: its text, recipient and "send once"
key stay the same, so attendance texts and pastor summaries can be retried
without anyone ever receiving the same text twice. Only failed texts (or sends
that were interrupted) can be claimed, and each claim is a single conditional
database update, so a double click or two people resending at once still
sends just one text.
"""
import logging
import threading

from django.db import connections, transaction
from django.db.models import F, Q
from django.utils import timezone

from .models import SMSMessage
from .services import deliver

logger = logging.getLogger(__name__)

# The most texts one "resend" request queues; the rest can be resent next.
MAX_RESEND_BATCH = 500


def can_resend_messages(user):
    """Resending uses SMS credit, so only church-wide administrators may do it."""
    return (
        user.is_authenticated
        and not user.is_tesmus_staff
        and not getattr(user, 'is_usher', False)
        and bool(user.church_id)
        and user.scope_type == 'church'
    )


def resendable(queryset):
    """Failed texts, plus texts whose latest try was interrupted."""
    stale_before = timezone.now() - SMSMessage.STALE_SENDING_AFTER
    return queryset.filter(
        Q(status='failed')
        | Q(status='queued', last_attempt_at__lt=stale_before)
        | Q(status='queued', last_attempt_at__isnull=True, created_at__lt=stale_before)
    )


def claim(queryset):
    """Mark resendable texts as sending again. Returns the ids this call won."""
    candidates = list(resendable(queryset).order_by('pk').values_list('pk', flat=True)[:MAX_RESEND_BATCH])
    claimed = []
    for pk in candidates:
        # Conditional on still being resendable, so only one claim can win.
        won = resendable(SMSMessage.objects.filter(pk=pk)).update(
            status='queued',
            failure_reason='',
            provider_message_id='',
            sent_at=None,
            last_attempt_at=timezone.now(),
            attempt_count=F('attempt_count') + 1,
        )
        if won:
            claimed.append(pk)
    return claimed


def resend_now(message):
    """Resend one text straight away. Returns it, or None if it could not be claimed."""
    if not claim(SMSMessage.objects.filter(pk=message.pk)):
        return None
    message.refresh_from_db()
    return deliver(message)


def resend_in_background(queryset):
    """Claim the resendable texts now and send them one by one in the background.

    Each text shows as "Sending…" straight away and switches to Sent or Failed
    as it is tried, so a large batch never keeps the person waiting.
    """
    ids = claim(queryset)
    if ids:
        transaction.on_commit(lambda: threading.Thread(
            target=_deliver_all, args=(ids,), name='sms-resend', daemon=True,
        ).start())
    return ids


def _deliver_all(ids):
    try:
        for message in SMSMessage.objects.filter(pk__in=ids, status='queued').select_related('church').order_by('pk'):
            try:
                deliver(message)
            except Exception:
                logger.exception('Could not resend text message %s', message.pk)
                SMSMessage.objects.filter(pk=message.pk, status='queued').update(
                    status='failed', failure_reason='The resend was interrupted. Please try again.',
                )
    finally:
        # This thread opened its own database connections; do not leave them open.
        connections.close_all()
