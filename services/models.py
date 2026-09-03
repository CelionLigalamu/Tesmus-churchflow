from django.db import models
from tenants.managers import TenantManager
import uuid


class Service(models.Model):
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('closed', 'Closed'),
        ('finalized', 'Finalized'),
    ]

    church = models.ForeignKey('tenants.Church', on_delete=models.PROTECT, related_name='services')
    region = models.ForeignKey('tenants.Region', on_delete=models.SET_NULL, blank=True, null=True, related_name='services')
    branch = models.ForeignKey('tenants.Branch', on_delete=models.SET_NULL, blank=True, null=True, related_name='services')
    name = models.CharField(max_length=255)
    service_type = models.CharField(max_length=100, blank=True)
    date = models.DateField()
    start_time = models.TimeField(blank=True, null=True)
    end_time = models.TimeField(blank=True, null=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='open')
    created_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, blank=True, null=True, related_name='created_services')
    created_at = models.DateTimeField(auto_now_add=True)

    objects = TenantManager()
    qr_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    def __str__(self):
        return f"{self.name} - {self.date}"
