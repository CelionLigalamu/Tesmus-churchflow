"""Text members their reference numbers without making an administrator wait.

A large import can add hundreds of members, and each text is a separate call to
the SMS provider. Sending them inside the page request would keep the
administrator waiting and could be cut off by the web server's time limit, so
they are sent one by one in a background thread once the members are saved.
Every text is recorded on the Messages page, and failures notify the church's
administrators as usual.
"""
import logging
import threading

from django.db import connections, transaction

from messaging.services import get_system_template, send_reference_number_sms

from .models import Member
from .services import in_reference_number_order

logger = logging.getLogger(__name__)


def reference_texts_enabled(church):
    """False when the church has switched off the member reference number message."""
    return get_system_template(church, 'member_reference') is not None


def send_reference_numbers(member_ids):
    """Text each member their reference number. A problem with one never stops the rest."""
    members = in_reference_number_order(Member.objects.filter(pk__in=member_ids).select_related('church'))
    for member in members:
        try:
            send_reference_number_sms(member)
        except Exception:
            logger.exception('Could not text reference number %s to member %s', member.reference_number, member.pk)


def _send_in_background(member_ids):
    try:
        send_reference_numbers(member_ids)
    finally:
        # This thread opened its own database connections; do not leave them open.
        connections.close_all()


def send_reference_numbers_after_commit(member_ids):
    """Start texting once the members are saved, so nobody is texted for a rolled-back import."""
    member_ids = list(member_ids)
    if not member_ids:
        return

    def start():
        threading.Thread(
            target=_send_in_background, args=(member_ids,),
            name='reference-number-texts', daemon=True,
        ).start()

    transaction.on_commit(start)
