from django.db import models
from django.utils import timezone
from tenants.managers import TenantManager
import uuid


class Service(models.Model):
    STATUS_CHOICES = [
        ('upcoming', 'Upcoming'),
        ('open', 'Open'),
        ('closed', 'Closed'),
        ('finalized', 'Finalized'),
    ]

    church = models.ForeignKey('tenants.Church', on_delete=models.PROTECT, related_name='services')
    region = models.ForeignKey('tenants.Region', on_delete=models.SET_NULL, blank=True, null=True, related_name='services')
    name = models.CharField(max_length=255)
    service_type = models.CharField(max_length=100, blank=True)
    date = models.DateField()
    start_time = models.TimeField(blank=True, null=True)
    end_time = models.TimeField(blank=True, null=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='upcoming')
    created_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, blank=True, null=True, related_name='created_services')
    created_at = models.DateTimeField(auto_now_add=True)

    objects = TenantManager()
    qr_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    def sync_status(self, now=None):
        """Persist the service's time-based status when it is accessed."""
        if self.status == 'finalized':
            return self.status

        now = timezone.localtime(now or timezone.now())
        if self.date > now.date():
            calculated_status = 'upcoming'
        elif self.date < now.date():
            calculated_status = 'closed'
        elif self.start_time and now.time() < self.start_time:
            calculated_status = 'upcoming'
        elif self.end_time and now.time() >= self.end_time:
            calculated_status = 'closed'
        else:
            calculated_status = 'open'

        if self.status != calculated_status:
            self.status = calculated_status
            self.save(update_fields=['status'])
        return self.status

    def __str__(self):
        return f"{self.name} - {self.date}"
