from django.db import models


class AuditLog(models.Model):
    church = models.ForeignKey('tenants.Church', on_delete=models.SET_NULL, blank=True, null=True, related_name='audit_logs')
    user = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, blank=True, null=True, related_name='audit_logs')
    action = models.CharField(max_length=100)
    details = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.action} - {self.created_at}"