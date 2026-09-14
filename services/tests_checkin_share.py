from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from attendance.models import Attendance
from members.models import Member
from services.models import Service
from tenants.models import Church, Region

User = get_user_model()


class ServiceCheckInShareTests(TestCase):
    """The check-in link, QR code, poster, new link and close-now on the service page."""

    def setUp(self):
        provider = mock.patch('messaging.services.send_sms', return_value={'ok': 1})
        provider.start()
        self.addCleanup(provider.stop)
        self.church = Church.objects.create(name='Grace Chapel', code='GRC')
        self.region = Region.objects.create(church=self.church, name='Sikhendu')
        User.objects.create_user('admin', password='x', church=self.church, scope_type='church')
        User.objects.create_user('pastor', password='x', church=self.church, scope_type='region', scope_region=self.region)
        self.member = Member.objects.create(church=self.church, full_name='Mary Wanjiku', phone_number='0712345678', reference_number='GRC-01')
        self.service = Service.objects.create(church=self.church, name='Sunday Service', date=timezone.localdate())
        self.client.login(username='admin', password='x')

    def detail(self):
        return self.client.get(reverse('service_detail', args=[self.service.pk]))

    def test_the_service_page_shows_the_link_qr_code_and_poster(self):
        response = self.detail()
        self.assertContains(response, 'http://testserver' + reverse('qr_checkin', args=[self.service.qr_token]))
        self.assertContains(response, '<svg')
        self.assertContains(response, reverse('service_checkin_poster', args=[self.service.pk]))
        self.assertContains(response, 'Close service now')

    def test_the_poster_has_a_large_qr_code_and_instructions(self):
        response = self.client.get(reverse('service_checkin_poster', args=[self.service.pk]))
        self.assertContains(response, '<svg')
        self.assertContains(response, 'Enter your phone number or reference number')

    def test_a_new_link_stops_the_old_one_working(self):
        old_token = self.service.qr_token
        self.client.post(reverse('service_new_checkin_link', args=[self.service.pk]))
        self.service.refresh_from_db()
        self.assertNotEqual(self.service.qr_token, old_token)
        self.assertEqual(self.client.get(reverse('qr_checkin', args=[old_token])).status_code, 404)

    def test_closing_early_finalizes_the_service(self):
        self.client.post(reverse('service_close_now', args=[self.service.pk]))
        self.service.refresh_from_db()
        self.assertEqual(self.service.status, 'finalized')
        self.assertTrue(Attendance.objects.filter(service=self.service, member=self.member, result='absent').exists())

    def test_only_church_wide_administrators_change_the_link_or_close_early(self):
        old_token = self.service.qr_token
        self.client.login(username='pastor', password='x')
        self.client.post(reverse('service_new_checkin_link', args=[self.service.pk]))
        self.client.post(reverse('service_close_now', args=[self.service.pk]))
        self.service.refresh_from_db()
        self.assertEqual(self.service.qr_token, old_token)
        self.assertNotEqual(self.service.status, 'finalized')
        self.assertFalse(Attendance.objects.filter(service=self.service).exists())

    def test_a_closed_service_does_not_show_the_check_in_card(self):
        self.service.status = 'finalized'
        self.service.save()
        self.assertNotContains(self.detail(), 'Member check-in')
