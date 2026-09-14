from datetime import time, timedelta
from unittest import mock

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from attendance.checkin import DEVICE_COOKIE, MAX_FAILED_ATTEMPTS
from attendance.models import Attendance
from members.models import Member
from services.models import Service
from tenants.models import Church


class CheckInPageTests(TestCase):
    """Members checking themselves in with their phone number or reference number."""

    def setUp(self):
        self.church = Church.objects.create(name='Preaching Life Change Ministry', code='PLCM', primary_color='#123F92')
        self.service = Service.objects.create(church=self.church, name='Sunday Service', date=timezone.localdate())
        self.url = reverse('qr_checkin', args=[self.service.qr_token])
        self.mary = Member.objects.create(church=self.church, full_name='Mary Wanjiku Muthoni',
                                          phone_number='0712 345 678', reference_number='PLCM-01')
        self.peter = Member.objects.create(church=self.church, full_name='Peter Kamau',
                                           phone_number='0722000111', reference_number='PLCM-02')

    def check_in(self, identifier, client=None):
        return (client or self.client).post(self.url, {'identifier': identifier})

    def test_a_member_checks_in_with_their_phone_number_written_any_way(self):
        response = self.check_in('+254712345678')
        self.assertContains(response, 'You&rsquo;re checked in')
        self.assertContains(response, 'Welcome, Mary M.')
        self.assertNotContains(response, 'Wanjiku')
        attendance = Attendance.objects.get(service=self.service, member=self.mary)
        self.assertEqual(attendance.method, 'qr')
        self.assertTrue(attendance.device_id)

    def test_a_member_checks_in_with_their_reference_number_in_any_capitals(self):
        response = self.check_in(' plcm-02 ')
        self.assertContains(response, 'You&rsquo;re checked in')
        self.assertContains(response, 'Welcome, Peter K.')
        self.assertTrue(Attendance.objects.filter(service=self.service, member=self.peter).exists())

    def test_the_page_asks_for_a_phone_or_reference_number_using_the_churchs_code(self):
        response = self.client.get(self.url)
        self.assertContains(response, 'Your phone number or reference number')
        self.assertContains(response, 'e.g. 0712 345 678 or PLCM-08')
        self.assertContains(response, 'Preaching Life Change Ministry')
        self.assertContains(response, 'name="viewport"')

    def test_an_unknown_number_gets_a_general_message(self):
        response = self.check_in('0799999999')
        self.assertContains(response, 'We couldn&#x27;t check you in')
        self.assertFalse(Attendance.objects.exists())

    def test_an_empty_box_asks_again(self):
        self.assertContains(self.check_in('   '), 'Please enter your phone number or reference number.')

    def test_checking_in_twice_says_already_checked_in(self):
        self.check_in('PLCM-01')
        response = self.check_in('0712345678')
        self.assertContains(response, 'You&rsquo;re already checked in')
        self.assertEqual(Attendance.objects.count(), 1)

    def test_one_phone_can_check_in_only_one_member_per_service(self):
        self.check_in('0712345678')
        response = self.check_in('PLCM-02')
        self.assertContains(response, 'This phone has already been used to check someone in')
        self.assertFalse(Attendance.objects.filter(member=self.peter).exists())
        self.assertContains(self.check_in('PLCM-02', client=Client()), 'You&rsquo;re checked in')

    def test_the_phone_cookie_is_signed_and_hidden_from_scripts(self):
        cookie = self.client.get(self.url).cookies[DEVICE_COOKIE]
        self.assertTrue(cookie['httponly'])
        self.assertIn(':', cookie.value)

    def test_guessing_reference_numbers_is_blocked_after_five_tries(self):
        for number in range(90, 90 + MAX_FAILED_ATTEMPTS):
            self.check_in(f'PLCM-{number}')
        response = self.check_in('PLCM-01')
        self.assertContains(response, 'Too many attempts')
        self.assertFalse(Attendance.objects.exists())

    def test_two_members_sharing_a_number_are_asked_for_their_reference_number(self):
        Member.objects.create(church=self.church, full_name='John Kamau', phone_number='+254722000111', reference_number='PLCM-03')
        self.assertContains(self.check_in('0722000111'), 'Please use your reference number')
        self.assertContains(self.check_in('PLCM-03'), 'Welcome, John K.')

    def test_another_churchs_reference_number_is_not_accepted(self):
        other = Church.objects.create(name='Hope Centre', code='HOP')
        Member.objects.create(church=other, full_name='Ruth Chebet', phone_number='0733000222', reference_number='HOP-01')
        self.assertContains(self.check_in('HOP-01'), 'We couldn&#x27;t check you in')

    def test_a_service_that_has_not_started_says_when_check_in_opens(self):
        self.service.date = timezone.localdate() + timedelta(days=1)
        self.service.start_time = time(9, 0)
        self.service.save()
        response = self.client.get(self.url)
        self.assertContains(response, 'Check-in opens')
        self.assertContains(response, '09:00')
        self.assertNotContains(response, 'id_identifier')

    def test_a_finished_service_says_check_in_has_closed(self):
        self.service.date = timezone.localdate() - timedelta(days=1)
        self.service.save()
        with mock.patch('messaging.services.send_sms', return_value={'ok': 1}):
            response = self.client.get(self.url)
        self.assertContains(response, 'Check-in has closed')
