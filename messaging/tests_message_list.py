from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from messaging.models import SMSMessage
from tenants.models import Church

User = get_user_model()


class MessageTotalsTests(TestCase):
    def test_totals_count_every_message_even_when_sent_at_different_times(self):
        church = Church.objects.create(name='Grace Chapel', code='GRC')
        User.objects.create_user('admin', password='x', church=church, scope_type='church')
        for index, status in enumerate(['failed', 'failed', 'failed', 'sent']):
            message = SMSMessage.objects.create(
                church=church, recipient_phone=f'07110000{index:02d}', body='Hello', status=status,
            )
            SMSMessage.objects.filter(pk=message.pk).update(created_at=timezone.now() - timedelta(seconds=index))

        self.client.login(username='admin', password='x')
        response = self.client.get(reverse('message_list'))
        self.assertEqual(response.context['failed_count'], 3)
        self.assertEqual(response.context['sent_count'], 1)
        self.assertEqual(response.context['total_recipients'], 4)
