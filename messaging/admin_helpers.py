"""Helpers for reporting SMS outcomes inside the Django admin."""
from django.contrib import messages

from .services import delivery_report, describe_delivery

ADMIN_MESSAGE_LEVELS = {
    'success': messages.SUCCESS,
    'warning': messages.WARNING,
    'error': messages.ERROR,
}


def report_delivery(model_admin, request, sms_messages, noun='recipient'):
    """Tell the admin user what actually happened, not what was attempted."""
    level, text = describe_delivery(delivery_report(sms_messages), noun=noun)
    model_admin.message_user(request, text, level=ADMIN_MESSAGE_LEVELS[level])
