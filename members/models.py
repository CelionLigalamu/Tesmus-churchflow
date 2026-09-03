from django.db import models
from tenants.managers import TenantManager


class Member(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    ]

    church = models.ForeignKey('tenants.Church', on_delete=models.PROTECT, related_name='members')
    region = models.ForeignKey('tenants.Region', on_delete=models.SET_NULL, blank=True, null=True, related_name='members')
    branch = models.ForeignKey('tenants.Branch', on_delete=models.SET_NULL, blank=True, null=True, related_name='members')
    full_name = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=20)
    reference_number = models.CharField(max_length=30)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')
    created_at = models.DateTimeField(auto_now_add=True)

    objects = TenantManager()

    class Meta:
        unique_together = ('church', 'reference_number')
        indexes = [
            models.Index(fields=['church', 'phone_number']),
        ]

    def __str__(self):
        return f"{self.reference_number} - {self.full_name}"