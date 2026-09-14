from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.timesince import timesince


class Notification(models.Model):
    """Something one person should know about or act on.

    Titles, icons and destinations are derived from `kind`, never stored as
    free text, so a notification can only ever point somewhere inside the app.
    Similar unread events share a `group_key` and are counted on one row.
    """

    SMS_FAILED = 'sms_failed'
    FOLLOWUP_DUE = 'followup_due'
    MEMBER_SELF_REGISTERED = 'member_self_registered'

    KIND_CHOICES = [
        (SMS_FAILED, 'Text messages failed'),
        (FOLLOWUP_DUE, 'Pastoral follow-ups due'),
        (MEMBER_SELF_REGISTERED, 'New self-registrations'),
    ]
    ATTENTION_KINDS = (SMS_FAILED, FOLLOWUP_DUE)

    TITLES = {
        SMS_FAILED: ('{n} text message failed to send', '{n} text messages failed to send'),
        FOLLOWUP_DUE: ('{n} pastoral follow-up is due or overdue', '{n} pastoral follow-ups are due or overdue'),
        MEMBER_SELF_REGISTERED: ('{n} new member registered through your link', '{n} new members registered through your link'),
    }
    ICONS = {
        SMS_FAILED: 'alert',
        FOLLOWUP_DUE: 'pastoral',
        MEMBER_SELF_REGISTERED: 'visitors',
    }

    church = models.ForeignKey('tenants.Church', on_delete=models.CASCADE, related_name='notifications')
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    kind = models.CharField(max_length=40, choices=KIND_CHOICES)
    group_key = models.CharField(
        max_length=120,
        help_text='Unread events with the same key are combined into one notification.',
    )
    count = models.PositiveIntegerField(default=1)
    detail = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(default=timezone.now)
    read_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['recipient', 'read_at', 'group_key'], name='notif_recipient_unread_idx'),
        ]

    def __str__(self):
        return f'{self.recipient} - {self.title}'

    @property
    def title(self):
        singular, plural = self.TITLES[self.kind]
        return (singular if self.count == 1 else plural).format(n=self.count)

    @property
    def display_detail(self):
        """The detail as shown to people; failed texts keep the technical error for support only."""
        if self.kind == self.SMS_FAILED and self.detail:
            from messaging.failure_reasons import plain_failure_reason
            return plain_failure_reason(self.detail)
        return self.detail

    @property
    def icon(self):
        return self.ICONS[self.kind]

    @property
    def needs_attention(self):
        return self.kind in self.ATTENTION_KINDS

    @property
    def is_unread(self):
        return self.read_at is None

    @property
    def target_url(self):
        if self.kind == self.SMS_FAILED:
            return reverse('message_list') + '?status=failed'
        if self.kind == self.FOLLOWUP_DUE:
            return reverse('pastoral_followup_list')
        return reverse('member_list')

    @property
    def time_label(self):
        if (timezone.now() - self.updated_at).total_seconds() < 60:
            return 'Just now'
        return f'{timesince(self.updated_at, depth=1)} ago'
