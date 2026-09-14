from django.core.management.base import BaseCommand

from notifications.services import sync_followup_notifications
from tenants.models import Church


class Command(BaseCommand):
    help = 'Refresh "pastoral follow-ups due or overdue" notifications for every active church. Schedule daily.'

    def handle(self, *args, **options):
        churches = Church.objects.filter(is_active=True)
        for church in churches:
            sync_followup_notifications(church)
        self.stdout.write(self.style.SUCCESS(f'Follow-up reminders refreshed for {churches.count()} church(es).'))
