from django.db import models
from django.db.models import Q
from django.utils import timezone

from tenants.managers import TenantManager


class PastoralFollowUp(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('returned', 'Returned'),
        ('closed', 'Closed'),
    ]
    OPEN_STATUSES = ('pending', 'in_progress')

    MANUAL = 'manual'
    MISSED_SERVICES = 'missed_services'
    REASON_CHOICES = [
        (MANUAL, 'Added by hand'),
        (MISSED_SERVICES, 'Missed services in a row'),
    ]

    church = models.ForeignKey('tenants.Church', on_delete=models.CASCADE, related_name='followups')
    member = models.ForeignKey('members.Member', on_delete=models.CASCADE, related_name='followups')
    assigned_to = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, blank=True, null=True, related_name='assigned_followups')
    # The pastors responsible: members picked for the member's region, who are
    # reached by SMS and need no sign-in.
    pastors = models.ManyToManyField('members.Member', blank=True, related_name='pastoral_assignments')
    reason = models.CharField(max_length=20, choices=REASON_CHOICES, default=MANUAL)
    missed_count = models.PositiveSmallIntegerField(default=0, help_text='Services missed in a row when this follow-up opened.')
    trigger_service = models.ForeignKey(
        'services.Service', on_delete=models.SET_NULL, blank=True, null=True, related_name='+',
        help_text='The service whose closing opened this follow-up.',
    )
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='pending')
    follow_up_date = models.DateField(blank=True, null=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(blank=True, null=True)

    objects = TenantManager()

    class Meta:
        constraints = [
            # One open "missed services" follow-up per member, so a pastor is
            # never alerted twice about the same absence.
            models.UniqueConstraint(
                fields=['member'],
                condition=Q(reason='missed_services', status__in=['pending', 'in_progress']),
                name='one_open_absence_followup_per_member',
            ),
        ]

    def __str__(self):
        return f"{self.member.full_name} - {self.status}"

    @property
    def is_open(self):
        return self.status in self.OPEN_STATUSES

    @property
    def reason_label(self):
        if self.reason == self.MISSED_SERVICES and self.missed_count:
            return f'Missed {self.missed_count} services in a row'
        return self.get_reason_display()

    @property
    def status_css(self):
        return {
            'pending': 'status-pill-warning',
            'in_progress': 'status-pill-info',
            'completed': 'status-pill-success',
            'returned': 'status-pill-success',
        }.get(self.status, 'status-pill-neutral')

    def add_note(self, text, author=''):
        """Add a dated line to the notes, keeping everything written before."""
        stamp = timezone.localtime().strftime('%d %b %Y, %H:%M')
        entry = f'{stamp} · {author}: {text}' if author else f'{stamp}: {text}'
        self.notes = f'{self.notes.rstrip()}\n{entry}'.strip()
