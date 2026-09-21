from datetime import timedelta
from unittest import mock

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from messaging.models import SMSMessage
from messaging.resend import resend_now
from messaging.services import send_message
from notifications.models import Notification
from tenants.models import Church, Region

User = get_user_model()


class RunAtOnce:
    """Stands in for threading.Thread so background resends run inside the test."""

    def __init__(self, target, args=(), **kwargs):
        self.target, self.args = target, args

    def start(self):
        with mock.patch('messaging.resend.connections.close_all'):
            self.target(*self.args)


class ResendTestBase(TestCase):
    def setUp(self):
        self.church = Church.objects.create(name='Grace Chapel', code='GRC')
        self.admin_user = User.objects.create_user('admin', password='x', church=self.church, scope_type='church')
        send_sms = mock.patch('messaging.services.send_sms', return_value='ATXid_ok')
        self.send_sms = send_sms.start()
        self.addCleanup(send_sms.stop)
        thread = mock.patch('messaging.resend.threading.Thread', RunAtOnce)
        thread.start()
        self.addCleanup(thread.stop)

    def failed_message(self, phone='0711000001', reason='Could not connect', **kwargs):
        with mock.patch('messaging.services.send_sms', side_effect=Exception(reason)):
            return send_message(self.church, phone, 'Hello from Grace Chapel', **kwargs)

    def sent_message(self, phone='0711000009'):
        return send_message(self.church, phone, 'Hello from Grace Chapel')

    def page_messages(self, response):
        return ' '.join(str(message) for message in response.context['messages'])

    def resend_many(self, **data):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(reverse('message_resend_many'), data, follow=True)


class ResendOneTextTests(ResendTestBase):
    def setUp(self):
        super().setUp()
        self.client.login(username='admin', password='x')

    def test_a_resent_text_switches_to_sent_on_the_same_record(self):
        message = self.failed_message()
        response = self.client.post(reverse('message_resend', args=[message.pk]), follow=True)
        message.refresh_from_db()
        self.assertEqual((message.status, message.attempt_count, message.failure_reason), ('sent', 2, ''))
        self.assertEqual(message.provider_message_id, 'ATXid_ok')
        self.assertIsNotNone(message.sent_at)
        self.assertEqual(SMSMessage.objects.count(), 1)
        self.assertIn('Text resent to 0711000001.', self.page_messages(response))
        self.assertContains(response, 'status-pill-success')

    def test_a_text_that_fails_again_stays_failed_with_the_new_reason(self):
        message = self.failed_message()
        self.send_sms.side_effect = Exception('Insufficient balance')
        response = self.client.post(reverse('message_resend', args=[message.pk]), follow=True)
        message.refresh_from_db()
        self.assertEqual((message.status, message.attempt_count, message.failure_reason), ('failed', 2, 'Insufficient balance'))
        self.assertIn('failed again. The church has run out of SMS credit.', self.page_messages(response))
        self.assertEqual(Notification.objects.get(recipient=self.admin_user).count, 2)

    def test_a_sent_text_is_never_sent_again(self):
        message = self.sent_message()
        response = self.client.post(reverse('message_resend', args=[message.pk]), follow=True)
        message.refresh_from_db()
        self.assertEqual(self.send_sms.call_count, 1)
        self.assertEqual((message.status, message.attempt_count), ('sent', 1))
        self.assertIn('was already sent, so it was not sent again', self.page_messages(response))

    def test_resending_twice_sends_only_once(self):
        message = self.failed_message()
        self.assertEqual(resend_now(message).status, 'sent')
        self.assertIsNone(resend_now(message))
        self.assertEqual(self.send_sms.call_count, 1)

    def test_attendance_texts_can_be_retried_without_ever_duplicating(self):
        message = self.failed_message(dedupe_key='attendance:1:1:present')
        self.client.post(reverse('message_resend', args=[message.pk]))
        again = send_message(self.church, '0711000001', 'Hello from Grace Chapel', dedupe_key='attendance:1:1:present')
        self.assertEqual(again.pk, message.pk)
        self.assertEqual(again.status, 'sent')
        self.assertEqual(self.send_sms.call_count, 1)

    def test_an_interrupted_send_can_be_retried_but_one_in_progress_cannot(self):
        in_progress = SMSMessage.objects.create(church=self.church, recipient_phone='0711000002', body='Hi',
                                                status='queued', last_attempt_at=timezone.now())
        interrupted = SMSMessage.objects.create(church=self.church, recipient_phone='0711000003', body='Hi',
                                                status='queued', last_attempt_at=timezone.now() - timedelta(minutes=11))
        self.assertTrue(in_progress.is_sending)
        self.assertFalse(in_progress.can_resend)
        self.assertEqual(in_progress.status_label, 'Sending…')
        self.assertTrue(interrupted.can_resend)
        self.assertIsNone(resend_now(in_progress))
        self.assertEqual(resend_now(interrupted).status, 'sent')

    def test_the_detail_page_offers_resend_only_for_failed_texts(self):
        failed, sent = self.failed_message(), self.sent_message()
        self.assertContains(self.client.get(reverse('message_detail', args=[failed.pk])), 'Resend text')
        self.assertNotContains(self.client.get(reverse('message_detail', args=[sent.pk])), 'Resend text')
        self.assertContains(self.client.get(reverse('message_detail', args=[failed.pk])), 'Attempts')


class ResendManyTextsTests(ResendTestBase):
    def setUp(self):
        super().setUp()
        self.client.login(username='admin', password='x')

    def test_only_the_ticked_failed_texts_are_resent(self):
        first, second, sent = self.failed_message('0711000001'), self.failed_message('0711000002'), self.sent_message()
        untouched = self.failed_message('0711000003')
        response = self.resend_many(message=[first.pk, second.pk, sent.pk])
        statuses = dict(SMSMessage.objects.values_list('recipient_phone', 'status'))
        self.assertEqual(statuses, {'0711000001': 'sent', '0711000002': 'sent', '0711000009': 'sent', '0711000003': 'failed'})
        self.assertEqual(SMSMessage.objects.get(pk=sent.pk).attempt_count, 1)
        self.assertIn('2 texts are being resent', self.page_messages(response))
        self.assertEqual(untouched.attempt_count, 1)

    def test_resend_all_failed_texts(self):
        for index in range(3):
            self.failed_message(f'071100000{index}')
        response = self.resend_many(scope='all_failed')
        self.assertEqual(set(SMSMessage.objects.values_list('status', flat=True)), {'sent'})
        self.assertIn('3 texts are being resent', self.page_messages(response))

    def test_nothing_ticked_is_refused_politely(self):
        self.failed_message()
        response = self.resend_many()
        self.assertIn('Tick the failed texts you want to resend.', self.page_messages(response))
        self.assertEqual(SMSMessage.objects.get().status, 'failed')

    def test_the_list_shows_resend_controls_for_failed_texts_only(self):
        failed, sent = self.failed_message(), self.sent_message()
        page = self.client.get(reverse('message_list'))
        self.assertContains(page, 'Resend all failed')
        self.assertContains(page, f'name="message" value="{failed.pk}" aria-label')
        self.assertContains(page, f'value="{sent.pk}" aria-label="Select the text to 0711000009" data-resend-control hidden disabled')

    def test_live_status_reports_only_this_churchs_texts(self):
        mine = self.failed_message()
        other_church = Church.objects.create(name='Hope Centre', code='HOP')
        theirs = SMSMessage.objects.create(church=other_church, recipient_phone='0722000000', body='Hi', status='failed')
        data = self.client.get(reverse('message_status'), {'ids': f'{mine.pk},{theirs.pk}'}).json()
        self.assertEqual(list(data['messages']), [str(mine.pk)])
        self.assertEqual(data['messages'][str(mine.pk)], {
            'status': 'failed', 'label': 'Failed', 'css': 'status-pill-warning', 'sending': False, 'can_resend': True,
        })
        self.assertEqual(data['totals']['failed'], 1)


class ResendPermissionTests(ResendTestBase):
    def test_only_church_wide_administrators_can_resend(self):
        message = self.failed_message()
        region = Region.objects.create(church=self.church, name='Kasarani')
        User.objects.create_user('pastor', password='x', church=self.church, scope_type='region', scope_region=region)
        self.client.login(username='pastor', password='x')
        response = self.client.post(reverse('message_resend', args=[message.pk]), follow=True)
        self.assertIn('Only church-wide administrators can resend text messages.', self.page_messages(response))
        self.assertNotContains(self.client.get(reverse('message_list')), 'Resend all failed')
        self.resend_many(scope='all_failed')
        self.assertEqual(SMSMessage.objects.get().status, 'failed')
        self.assertEqual(self.send_sms.call_count, 0)

    def test_another_churchs_texts_cannot_be_resent(self):
        other_church = Church.objects.create(name='Hope Centre', code='HOP')
        theirs = SMSMessage.objects.create(church=other_church, recipient_phone='0722000000', body='Hi', status='failed')
        self.client.login(username='admin', password='x')
        self.assertEqual(self.client.post(reverse('message_resend', args=[theirs.pk])).status_code, 404)
        self.resend_many(message=[theirs.pk])
        theirs.refresh_from_db()
        self.assertEqual(theirs.status, 'failed')

    def test_resending_requires_a_post(self):
        message = self.failed_message()
        self.client.login(username='admin', password='x')
        self.assertEqual(self.client.get(reverse('message_resend', args=[message.pk])).status_code, 405)

    def test_tesmus_staff_can_resend_from_django_admin(self):
        failed, sent = self.failed_message(), self.sent_message()
        staff = User.objects.create_superuser('tesmus', password='x', is_tesmus_staff=True)
        request = RequestFactory().post('/admin/messaging/smsmessage/')
        request.user = staff
        request.session = self.client.session
        request._messages = FallbackStorage(request)
        model_admin = admin.site._registry[SMSMessage]
        with self.captureOnCommitCallbacks(execute=True):
            model_admin.resend_failed(request, SMSMessage.objects.filter(pk__in=[failed.pk, sent.pk]))
        failed.refresh_from_db()
        self.assertEqual((failed.status, failed.attempt_count), ('sent', 2))
        self.assertEqual(SMSMessage.objects.get(pk=sent.pk).attempt_count, 1)
