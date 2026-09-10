from django.db import models
from tenants.managers import TenantManager


class SMSConfiguration(models.Model):
    church = models.OneToOneField('tenants.Church', on_delete=models.CASCADE, related_name='sms_config')
    provider = models.CharField(max_length=50, default='africastalking')
    sender_id = models.CharField(max_length=11, blank=True)
    username = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)

    objects = TenantManager()

    def __str__(self):
        return f"{self.church.code} SMS Config"


class SMSTemplate(models.Model):
    church = models.ForeignKey('tenants.Church', on_delete=models.CASCADE, related_name='sms_templates')
    name = models.CharField(max_length=100)
    body = models.TextField(help_text="Use {{member_name}}, {{church_name}}, {{service_name}} etc.")
    is_active = models.BooleanField(default=True)

    objects = TenantManager()

    class Meta:
        unique_together = ('church', 'name')

    def __str__(self):
        return f"{self.church.code} - {self.name}"


class SMSMessage(models.Model):
    STATUS_CHOICES = [
        ('queued', 'Queued'),
        ('sent', 'Sent'),
        ('delivered', 'Delivered'),
        ('failed', 'Failed'),
    ]

    church = models.ForeignKey('tenants.Church', on_delete=models.CASCADE, related_name='sms_messages')
    recipient_phone = models.CharField(max_length=20)
    body = models.TextField()
    template = models.ForeignKey('SMSTemplate', on_delete=models.SET_NULL, blank=True, null=True, related_name='messages')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='queued')
    provider_message_id = models.CharField(max_length=100, blank=True)
    dedupe_key = models.CharField(max_length=150, unique=True, blank=True, null=True)
    failure_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(blank=True, null=True)

    objects = TenantManager()

    def __str__(self):
        return f"{self.recipient_phone} - {self.status}"
