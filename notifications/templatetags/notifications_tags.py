from django import template

from notifications.models import Notification
from notifications.services import refresh_followups_if_due

register = template.Library()

RECENT_LIMIT = 8


@register.inclusion_tag('notifications/bell.html', takes_context=True)
def notification_bell(context, menu_id):
    """The bell and its dropdown for the signed-in church user."""
    request = context.get('request')
    user = getattr(request, 'user', None)
    data = {'enabled': False, 'menu_id': menu_id, 'request': request, 'csrf_token': context.get('csrf_token')}
    if not user or not user.is_authenticated or not user.church_id or user.is_tesmus_staff:
        return data

    refresh_followups_if_due(user.church)
    notifications = Notification.objects.filter(recipient=user)
    unread = notifications.filter(read_at__isnull=True)
    data.update(
        enabled=True,
        recent=list(notifications[:RECENT_LIMIT]),
        unread_count=unread.count(),
        has_attention=unread.filter(kind__in=Notification.ATTENTION_KINDS).exists(),
    )
    return data
