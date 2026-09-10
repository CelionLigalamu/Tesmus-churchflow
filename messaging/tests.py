from django.test import TestCase

from members.models import Member, MinistryRole
from .audience import get_recipients
from .models import SMSMessage
from tenants.models import Church


class LeadershipAudienceTests(TestCase):
    def test_leadership_audience_returns_only_active_members_with_selected_role(self):
        church = Church.objects.create(name='Messaging Church', code='MSG')
        role = MinistryRole.objects.create(church=church, name='Usher')
        matching = Member.objects.create(church=church, full_name='Matching', phone_number='0700000020', reference_number='MSG-01')
        matching.ministry_roles.add(role)
        inactive = Member.objects.create(church=church, full_name='Other', phone_number='0700000021', reference_number='MSG-02')
        self.assertEqual(list(get_recipients(church, 'leadership', result=role.pk)), [matching])

    def test_message_history_keeps_audience_metadata(self):
        church = Church.objects.create(name='History Church', code='HIST')
        message = SMSMessage.objects.create(church=church, recipient_phone='0700000030', body='Meeting reminder', audience_type='leadership', audience_label='Ushers')
        self.assertEqual(message.audience_label, 'Ushers')
        self.assertEqual(message.get_audience_type_display(), 'Leadership group')
