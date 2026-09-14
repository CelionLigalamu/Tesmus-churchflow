from datetime import timedelta
from io import StringIO
from itertools import count
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from members.models import Member
from messaging.services import send_message
from notifications.models import Notification
from notifications.services import notify_member_self_registered, sync_followup_notifications
from pastoral.models import PastoralFollowUp
from tenants.models import Church, Region

User = get_user_model()
_phones = count(1)


class NotificationTestBase(TestCase):
    def setUp(self):
        cache.clear()
        self.church = Church.objects.create(name='Grace Chapel', code='GRC')
        self.other_church = Church.objects.create(name='Hope Centre', code='HOP')
        self.region = Region.objects.create(church=self.church, name='Kasarani')
        self.other_region = Region.objects.create(church=self.church, name='Embakasi')
        self.admin = User.objects.create_user('admin', password='x', church=self.church, scope_type='church')
        self.pastor = User.objects.create_user('pastor', password='x', church=self.church, scope_type='region', scope_region=self.region)
        self.other_pastor = User.objects.create_user('other_pastor', password='x', church=self.church, scope_type='region', scope_region=self.other_region)
        self.outsider = User.objects.create_user('outsider', password='x', church=self.other_church, scope_type='church')

    def make_member(self, region=None, name='Asha Njeri'):
        number = next(_phones)
        return Member.objects.create(
            church=self.church, region=region, full_name=name,
            phone_number=f'07{number:08d}', reference_number=f'GRC-{number:03d}',
        )


class FailedTextNotificationTests(NotificationTestBase):
    def test_failures_notify_church_admins_grouped_into_one(self):
        with mock.patch('messaging.services.send_sms', side_effect=Exception('Insufficient balance')):
            send_message(self.church, '0700000001', 'Hello')
            send_message(self.church, '0700000002', 'Hello')
        notification = Notification.objects.get(kind=Notification.SMS_FAILED)
        self.assertEqual(notification.recipient, self.admin)
        self.assertEqual(notification.count, 2)
        self.assertEqual(notification.title, '2 text messages failed to send')
        self.assertIn('Insufficient balance', notification.detail)
        self.assertEqual(notification.target_url, reverse('message_list') + '?status=failed')

    def test_successful_texts_create_nothing(self):
        with mock.patch('messaging.services.send_sms', return_value={'ok': 1}):
            send_message(self.church, '0700000001', 'Hello')
        self.assertFalse(Notification.objects.exists())

    def test_new_failures_after_reading_start_a_fresh_notification(self):
        with mock.patch('messaging.services.send_sms', side_effect=Exception('down')):
            send_message(self.church, '0700000001', 'Hello')
            Notification.objects.update(read_at=timezone.now())
            send_message(self.church, '0700000002', 'Hello')
        self.assertEqual(Notification.objects.count(), 2)
        self.assertEqual(Notification.objects.filter(read_at__isnull=True).get().count, 1)

    def test_a_notification_problem_never_breaks_sending(self):
        with mock.patch('messaging.services.send_sms', side_effect=Exception('down')), \
                mock.patch('notifications.services._add_to_group', side_effect=RuntimeError('database down')), \
                self.assertLogs('notifications.services', level='ERROR') as logs:
            message = send_message(self.church, '0700000001', 'Hello')
        self.assertEqual(message.status, 'failed')
        self.assertIn('Could not record a failed text message notification', logs.output[0])


class SelfRegistrationNotificationTests(NotificationTestBase):
    def test_admins_and_the_members_region_pastor_are_told(self):
        notify_member_self_registered(self.make_member(region=self.region))
        recipients = set(Notification.objects.values_list('recipient__username', flat=True))
        self.assertEqual(recipients, {'admin', 'pastor'})

    def test_member_without_a_region_goes_to_admins_only(self):
        notify_member_self_registered(self.make_member())
        self.assertEqual(set(Notification.objects.values_list('recipient__username', flat=True)), {'admin'})

    def test_registering_through_the_public_link_notifies(self):
        with mock.patch('messaging.services.send_sms', return_value={'ok': 1}):
            self.client.post(
                reverse('member_self_register', args=[self.church.registration_token]),
                {'full_name': 'Mary Wanjiku', 'phone_number': '0712345678', 'region': 'Kasarani'},
            )
        notification = Notification.objects.get(recipient=self.admin, kind=Notification.MEMBER_SELF_REGISTERED)
        self.assertIn('Mary Wanjiku', notification.detail)
        self.assertTrue(Notification.objects.filter(recipient=self.pastor).exists())
        self.assertFalse(Notification.objects.filter(recipient__in=[self.other_pastor, self.outsider]).exists())


class FollowUpNotificationTests(NotificationTestBase):
    def followup(self, days_from_today, assigned=None, status='pending'):
        return PastoralFollowUp.objects.create(
            church=self.church, member=self.make_member(), assigned_to=assigned, status=status,
            follow_up_date=timezone.localdate() + timedelta(days=days_from_today),
        )

    def test_admins_see_all_due_and_assignees_see_their_own(self):
        self.followup(-2, assigned=self.pastor)
        self.followup(0, assigned=self.pastor)
        self.followup(0)
        self.followup(3, assigned=self.pastor)
        self.followup(-1, status='completed')
        sync_followup_notifications(self.church)

        admin_note = Notification.objects.get(recipient=self.admin, kind=Notification.FOLLOWUP_DUE)
        self.assertEqual(admin_note.count, 3)
        self.assertEqual(admin_note.detail, '1 overdue, 2 due today')
        self.assertEqual(Notification.objects.get(recipient=self.pastor).count, 2)
        self.assertFalse(Notification.objects.filter(recipient=self.other_pastor).exists())

    def test_running_twice_changes_nothing_and_resolving_clears_it(self):
        followup = self.followup(0, assigned=self.pastor)
        sync_followup_notifications(self.church)
        sync_followup_notifications(self.church)
        self.assertEqual(Notification.objects.count(), 2)
        followup.status = 'completed'
        followup.save()
        sync_followup_notifications(self.church)
        self.assertFalse(Notification.objects.exists())

    def test_a_read_reminder_returns_when_more_become_due(self):
        self.followup(0)
        sync_followup_notifications(self.church)
        Notification.objects.update(read_at=timezone.now())
        self.followup(-1)
        sync_followup_notifications(self.church)
        notification = Notification.objects.get(recipient=self.admin)
        self.assertIsNone(notification.read_at)
        self.assertEqual(notification.count, 2)

    def test_daily_command(self):
        self.followup(-1)
        output = StringIO()
        call_command('send_followup_reminders', stdout=output)
        self.assertTrue(Notification.objects.filter(recipient=self.admin).exists())
        self.assertIn('refreshed', output.getvalue())


class NotificationViewTests(NotificationTestBase):
    def setUp(self):
        super().setUp()
        self.notification = Notification.objects.create(
            church=self.church, recipient=self.admin, kind=Notification.SMS_FAILED,
            group_key='sms', count=3, detail='Insufficient balance',
        )
        self.client.login(username='admin', password='x')

    def test_bell_shows_unread_count_and_attention_badge(self):
        html = self.client.get(reverse('home')).content.decode()
        self.assertIn('Notifications, 1 unread', html)
        self.assertIn('notification-badge is-attention', html)
        self.assertIn('3 text messages failed to send', html)

    def test_badge_caps_at_nine(self):
        for index in range(12):
            Notification.objects.create(church=self.church, recipient=self.admin,
                                        kind=Notification.MEMBER_SELF_REGISTERED, group_key=f'reg-{index}')
        self.assertIn('>9+<', self.client.get(reverse('home')).content.decode())

    def test_opening_marks_read_and_goes_to_the_right_page(self):
        response = self.client.post(reverse('notification_open', args=[self.notification.pk]))
        self.assertRedirects(response, reverse('message_list') + '?status=failed', fetch_redirect_response=False)
        self.notification.refresh_from_db()
        self.assertIsNotNone(self.notification.read_at)

    def test_opening_requires_post(self):
        self.assertEqual(self.client.get(reverse('notification_open', args=[self.notification.pk])).status_code, 405)

    def test_nobody_can_open_someone_elses_notification(self):
        for username in ('pastor', 'outsider'):
            with self.subTest(username=username):
                self.client.login(username=username, password='x')
                response = self.client.post(reverse('notification_open', args=[self.notification.pk]))
                self.assertEqual(response.status_code, 404)

    def test_mark_all_as_read_returns_to_the_page(self):
        response = self.client.post(reverse('notification_mark_all_read'), {'next': reverse('member_list')})
        self.assertRedirects(response, reverse('member_list'), fetch_redirect_response=False)
        self.assertFalse(Notification.objects.filter(recipient=self.admin, read_at__isnull=True).exists())

    def test_mark_all_as_read_ignores_outside_addresses(self):
        response = self.client.post(reverse('notification_mark_all_read'), {'next': 'https://example.com/'})
        self.assertRedirects(response, reverse('notification_list'), fetch_redirect_response=False)

    def test_list_page_shows_only_your_own(self):
        Notification.objects.create(church=self.church, recipient=self.pastor, kind=Notification.MEMBER_SELF_REGISTERED,
                                    group_key='other', detail='Only for the pastor')
        html = self.client.get(reverse('notification_list')).content.decode()
        self.assertIn('The church has run out of SMS credit.', html)
        self.assertNotIn('Insufficient balance', html)
        self.assertNotIn('Only for the pastor', html)

    def test_technical_connection_errors_are_shown_in_plain_words(self):
        self.notification.detail = ("HTTPSConnectionPool(host='api.sandbox.africastalking.com', port=443): Max retries "
                                    "exceeded with url: /version1/messaging (Caused by SSLError(SSLError(1, "
                                    "'[SSL: WRONG_VERSION_NUMBER] wrong version number')))")
        self.notification.save()
        html = self.client.get(reverse('notification_list')).content.decode()
        self.assertIn('Could not connect to the text message service.', html)
        self.assertNotIn('HTTPSConnectionPool', html)

    def test_sign_in_required(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse('notification_list')).status_code, 302)

    def test_no_bell_on_login_pages(self):
        self.client.logout()
        html = self.client.get(reverse('church_login', args=[self.church.slug])).content.decode()
        self.assertNotIn('notification-toggle', html)
