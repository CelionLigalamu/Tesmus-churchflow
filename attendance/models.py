from django.db import models
from tenants.managers import TenantManager


class Attendance(models.Model):
    METHOD_CHOICES = [
        ('qr', 'QR'),
        ('usher', 'Usher'),
        ('manual', 'Manual'),
    ]
    RESULT_CHOICES = [
        ('present', 'Present'),
        ('absent', 'Absent'),
    ]

    church = models.ForeignKey('tenants.Church', on_delete=models.PROTECT, related_name='attendances')
    service = models.ForeignKey('services.Service', on_delete=models.CASCADE, related_name='attendances')
    member = models.ForeignKey('members.Member', on_delete=models.CASCADE, blank=True, null=True, related_name='attendances')
    visitor = models.ForeignKey('visitors.Visitor', on_delete=models.CASCADE, blank=True, null=True, related_name='attendances')
    method = models.CharField(max_length=10, choices=METHOD_CHOICES)
    result = models.CharField(max_length=10, choices=RESULT_CHOICES, blank=True)
    checked_in_at = models.DateTimeField(auto_now_add=True)

    objects = TenantManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['service', 'member'], name='unique_member_service_attendance'),
        ]

    def __str__(self):
        who = self.member.full_name if self.member else (self.visitor.full_name if self.visitor else "Unknown")
        return f"{who} - {self.service.name}"