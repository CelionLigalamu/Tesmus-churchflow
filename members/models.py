from django.db import models
from tenants.managers import TenantManager


DEFAULT_MINISTRY_ROLES = (
    'Bishop',
    'Pastor',
    'Elder',
    'Deacon',
    'Deaconess',
    'Ushers',
    'Instrumentalists',
)


class MinistryRole(models.Model):
    church = models.ForeignKey('tenants.Church', on_delete=models.CASCADE, related_name='ministry_roles')
    name = models.CharField(max_length=100)
    sort_order = models.PositiveIntegerField(default=1000)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['church', 'name'], name='unique_ministry_role_per_church'),
        ]
        ordering = ['sort_order', 'name']

    def __str__(self):
        return self.name


class Member(models.Model):
    church = models.ForeignKey('tenants.Church', on_delete=models.PROTECT, related_name='members')
    region = models.ForeignKey('tenants.Region', on_delete=models.SET_NULL, blank=True, null=True, related_name='members')
    branch = models.ForeignKey('tenants.Branch', on_delete=models.SET_NULL, blank=True, null=True, related_name='members')
    full_name = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=20)
    reference_number = models.CharField(max_length=30)
    created_at = models.DateTimeField(auto_now_add=True)
    ministry_roles = models.ManyToManyField(MinistryRole, blank=True, related_name='members')

    objects = TenantManager()

    class Meta:
        unique_together = ('church', 'reference_number')
        indexes = [
            models.Index(fields=['church', 'phone_number']),
        ]

    def __str__(self):
        return f"{self.reference_number} - {self.full_name}"
