from unittest import mock

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from members.models import Member
from messaging import failure_reasons as reasons
from messaging.failure_reasons import plain_failure_reason
from messaging.services import delivery_report, describe_delivery, send_message
from tenants.models import Church

SSL_ERROR = ("HTTPSConnectionPool(host='api.sandbox.africastalking.com', port=443): Max retries exceeded with url: "
             "/version1/messaging (Caused by SSLError(SSLError(1, '[SSL: WRONG_VERSION_NUMBER] wrong version number')))")


class PlainFailureReasonTests(SimpleTestCase):
    def test_provider_errors_become_plain_words(self):
        cases = {
            SSL_ERROR: reasons.UNREACHABLE,
            'Read timed out.': reasons.UNREACHABLE,
            'Insufficient balance': reasons.NO_BALANCE,
            'The supplied authentication is invalid': reasons.ACCOUNT_SETTINGS,
            'InvalidSenderId': reasons.SENDER_NAME,
            'InvalidPhoneNumber': reasons.BAD_NUMBER,
            'UserInBlacklist': reasons.BLOCKED_NUMBER,
            'Something odd happened': reasons.UNKNOWN,
            '': reasons.UNKNOWN,
            None: reasons.UNKNOWN,
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(plain_failure_reason(raw), expected)

    def test_a_plain_reason_stays_the_same(self):
        self.assertEqual(plain_failure_reason(reasons.NO_BALANCE), reasons.NO_BALANCE)


class PlainFailureReasonPagesTests(TestCase):
    def setUp(self):
        self.church = Church.objects.create(name='Grace Chapel', code='GRC')
        get_user_model().objects.create_user('admin', password='x', church=self.church, scope_type='church')
        self.client.login(username='admin', password='x')

    def failed_message(self):
        with mock.patch('messaging.services.send_sms', side_effect=Exception(SSL_ERROR)):
            return send_message(self.church, '0700000001', 'Hello')

    def test_the_delivery_summary_uses_plain_words_once(self):
        with mock.patch('messaging.services.send_sms', side_effect=Exception(SSL_ERROR)):
            sent = [send_message(self.church, f'070000000{n}', 'Hello') for n in range(3)]
        level, text = describe_delivery(delivery_report(sent))
        self.assertEqual(level, 'error')
        self.assertEqual(text.count('Could not connect to the text message service.'), 1)
        self.assertNotIn('HTTPSConnectionPool', text)

    def test_message_detail_explains_and_keeps_the_technical_error_for_support(self):
        message = self.failed_message()
        self.assertEqual(message.failure_reason, SSL_ERROR)
        page = self.client.get(reverse('message_detail', args=[message.pk]))
        self.assertContains(page, 'Could not connect to the text message service.')
        self.assertContains(page, 'Technical details for Tesmus support')

    def test_sending_a_reference_number_explains_the_failure_plainly(self):
        member = Member.objects.create(church=self.church, full_name='Mary Wanjiku', phone_number='0712345678', reference_number='GRC-01')
        with mock.patch('messaging.services.send_sms', side_effect=Exception(SSL_ERROR)):
            response = self.client.post(reverse('member_send_reference', args=[member.pk]), follow=True)
        text = ' '.join(str(m) for m in response.context['messages'])
        self.assertIn('Could not send the reference number to Mary Wanjiku. Could not connect', text)
        self.assertNotIn('HTTPSConnectionPool', text)
