from django.db import models
from tenants.managers import TenantManager


class Visitor(models.Model):
    church = models.ForeignKey('tenants.Church', on_delete=models.PROTECT, related_name='visitors')
    region = models.ForeignKey('tenants.Region', on_delete=models.SET_NULL, blank=True, null=True, related_name='visitors')
    full_name = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=20)
    first_visit_date = models.DateTimeField(auto_now_add=True)
    converted_to_member = models.ForeignKey(
        'members.Member', on_delete=models.SET_NULL, blank=True, null=True, related_name='converted_from_visitor'
    )

    objects = TenantManager()

    class Meta:
        indexes = [
            models.Index(fields=['church', 'phone_number']),
        ]

    def __str__(self):
        return f"{self.full_name} ({self.phone_number})"