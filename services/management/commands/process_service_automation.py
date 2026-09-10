import time

from django.core.management.base import BaseCommand
from django.utils import timezone

from services.models import Service
from services.services import sync_and_finalize_service


class Command(BaseCommand):
    help = 'Synchronize service statuses and finalize completed services.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--once',
            action='store_true',
            help='Process services once and exit.',
        )
        parser.add_argument(
            '--interval',
            type=int,
            default=60,
            help='Seconds to wait between checks when running continuously.',
        )

    def handle(self, *args, **options):
        interval = max(options['interval'], 10)

        while True:
            self.process_services()
            if options['once']:
                return
            time.sleep(interval)

    def process_services(self):
        services = Service.objects.filter(
            status__in=['upcoming', 'open', 'closed'],
        ).select_related('church')
        processed = 0

        for service in services.iterator():
            try:
                sync_and_finalize_service(service)
                processed += 1
            except Exception as error:
                self.stderr.write(
                    self.style.ERROR(
                        f'Could not process service {service.pk}: {error}'
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(
                f'{timezone.localtime():%Y-%m-%d %H:%M:%S} — '
                f'processed {processed} service(s).'
            )
        )
