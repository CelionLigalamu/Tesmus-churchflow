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
    # The member's region when this record was made. Kept on the record so a
    # member moving house later does not rewrite past regional statistics.
    region = models.ForeignKey('tenants.Region', on_delete=models.SET_NULL, blank=True, null=True, related_name='attendances')
    # Which browser checked this member in through the check-in link, so one
    # phone cannot check in several members for the same service.
    device_id = models.CharField(max_length=64, blank=True, db_index=True)
    # The usher or administrator who checked the member in, when not self check-in.
    checked_in_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, blank=True, null=True, related_name='checkins_recorded')
    checked_in_at = models.DateTimeField(auto_now_add=True)

    objects = TenantManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['service', 'member'], name='unique_member_service_attendance'),
        ]

    def save(self, *args, **kwargs):
        if self._state.adding and self.member_id and not self.region_id:
            self.region_id = self.member.region_id
        super().save(*args, **kwargs)

    def __str__(self):
        who = self.member.full_name if self.member else (self.visitor.full_name if self.visitor else "Unknown")
        return f"{who} - {self.service.name}"