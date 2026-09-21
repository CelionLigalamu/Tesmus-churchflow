from datetime import timedelta

from django.db import models
from django.utils import timezone

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
    AUDIENCE_CHOICES = [
        ('church', 'All members'),
        ('leadership', 'Leadership group'),
        ('region', 'Members in a region'),
        ('service_present', 'Members present at a service'),
        ('service_absent', 'Members absent from a service'),
        ('visitor_present', 'Visitors present at a service'),
        ('individual', 'Individual or automated message'),
    ]
    STATUS_CHOICES = [
        ('queued', 'Queued'),
        ('sent', 'Sent'),
        ('delivered', 'Delivered'),
        ('failed', 'Failed'),
    ]

    church = models.ForeignKey('tenants.Church', on_delete=models.CASCADE, related_name='sms_messages')
    recipient_phone = models.CharField(max_length=20)
    body = models.TextField()
    audience_type = models.CharField(max_length=30, choices=AUDIENCE_CHOICES, default='individual')
    audience_label = models.CharField(max_length=150, blank=True)
    template = models.ForeignKey('SMSTemplate', on_delete=models.SET_NULL, blank=True, null=True, related_name='messages')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='queued')
    provider_message_id = models.CharField(max_length=100, blank=True)
    dedupe_key = models.CharField(max_length=150, unique=True, blank=True, null=True)
    failure_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(blank=True, null=True)
    # How many times this text has been tried, and when the latest try started.
    attempt_count = models.PositiveIntegerField(default=1)
    last_attempt_at = models.DateTimeField(blank=True, null=True)

    objects = TenantManager()

    # A text still "queued" this long after its latest try was interrupted
    # (for example by a server restart) and may be tried again.
    STALE_SENDING_AFTER = timedelta(minutes=10)

    def __str__(self):
        return f"{self.recipient_phone} - {self.status}"

    @property
    def is_sending(self):
        return self.status == 'queued' and not self._send_was_interrupted()

    @property
    def can_resend(self):
        """Only failed or interrupted texts: a sent text is never sent twice."""
        return self.status == 'failed' or (self.status == 'queued' and self._send_was_interrupted())

    def _send_was_interrupted(self):
        started = self.last_attempt_at or self.created_at
        return started is not None and timezone.now() - started > self.STALE_SENDING_AFTER

    @property
    def status_label(self):
        return 'Sending…' if self.is_sending else self.get_status_display()

    @property
    def status_css(self):
        if self.status in ('sent', 'delivered'):
            return 'status-pill-success'
        if self.status == 'failed':
            return 'status-pill-warning'
        return 'status-pill-sending' if self.is_sending else 'status-pill-neutral'

    @property
    def plain_failure_reason(self):
        from .failure_reasons import plain_failure_reason
        return plain_failure_reason(self.failure_reason)
