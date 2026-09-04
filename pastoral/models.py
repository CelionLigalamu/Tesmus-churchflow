from django.db import models
from tenants.managers import TenantManager


class PastoralFollowUp(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('closed', 'Closed'),
    ]

    church = models.ForeignKey('tenants.Church', on_delete=models.CASCADE, related_name='followups')
    member = models.ForeignKey('members.Member', on_delete=models.CASCADE, related_name='followups')
    assigned_to = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, blank=True, null=True, related_name='assigned_followups')
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='pending')
    follow_up_date = models.DateField(blank=True, null=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = TenantManager()

    def __str__(self):
        return f"{self.member.full_name} - {self.status}"
