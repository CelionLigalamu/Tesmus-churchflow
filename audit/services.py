from .models import AuditLog


def log_action(user, action, church=None, details=''):
    AuditLog.objects.create(
        user=user,
        church=church or getattr(user, 'church', None),
        action=action,
        details=details,
    )