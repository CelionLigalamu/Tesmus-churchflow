from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from attendance.models import Attendance
from members.models import Member
from messaging.models import SMSMessage
from services.models import Service
from tenants.models import Church, Region

User = get_user_model()


class ServiceAudienceTests(TestCase):
    """Sending to members present at, or absent from, a service."""

    def setUp(self):
        provider = mock.patch('messaging.services.send_sms', return_value={'ok': 1})
        provider.start()
        self.addCleanup(provider.stop)

        self.church = Church.objects.create(name='Grace Chapel', code='GRC')
        self.region = Region.objects.create(church=self.church, name='Sikhendu')
        self.service = Service.objects.create(
            church=self.church, region=self.region, name='Sunday Service',
            date=timezone.localdate(), status='finalized',
        )
        present = Member.objects.create(church=self.church, region=self.region, full_name='Mary Wanjiku',
                                        phone_number='0711000001', reference_number='GRC-001')
        absent = Member.objects.create(church=self.church, region=self.region, full_name='Peter Kamau',
                                       phone_number='0711000002', reference_number='GRC-002')
        Attendance.objects.create(church=self.church, service=self.service, member=present, method='qr', result='present')
        Attendance.objects.create(church=self.church, service=self.service, member=absent, method='manual', result='absent')
        User.objects.create_user('admin', password='x', church=self.church, scope_type='church')
        User.objects.create_user('pastor', password='x', church=self.church, scope_type='region', scope_region=self.region)

    def send(self, username, audience_type):
        self.client.login(username=username, password='x')
        return self.client.post(reverse('message_create'), {
            'audience_type': audience_type,
            'service': self.service.pk,
            'body': 'Thank you for worshipping with us.',
        })

    def recipients(self):
        return list(SMSMessage.objects.values_list('recipient_phone', flat=True))

    def test_members_present_at_a_service_can_be_messaged(self):
        response = self.send('admin', 'service_present')
        self.assertRedirects(response, reverse('message_list'), fetch_redirect_response=False)
        self.assertEqual(self.recipients(), ['0711000001'])

    def test_members_absent_from_a_service_can_be_messaged(self):
        response = self.send('admin', 'service_absent')
        self.assertRedirects(response, reverse('message_list'), fetch_redirect_response=False)
        self.assertEqual(self.recipients(), ['0711000002'])

    def test_a_region_scoped_user_can_open_the_page_and_send(self):
        self.client.login(username='pastor', password='x')
        self.assertEqual(self.client.get(reverse('message_create')).status_code, 200)
        response = self.send('pastor', 'service_present')
        self.assertRedirects(response, reverse('message_list'), fetch_redirect_response=False)
        self.assertEqual(self.recipients(), ['0711000001'])

    def test_a_service_from_another_church_is_refused(self):
        other = Church.objects.create(name='Hope Centre', code='HOP')
        foreign = Service.objects.create(church=other, name='Other Service', date=timezone.localdate(), status='finalized')
        self.client.login(username='admin', password='x')
        response = self.client.post(reverse('message_create'), {
            'audience_type': 'service_present', 'service': foreign.pk, 'body': 'Hello',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.recipients(), [])
