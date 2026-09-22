import os
from unittest import mock

from django.test import SimpleTestCase, TestCase

from messaging import failure_reasons as reasons
from messaging.failure_reasons import plain_failure_reason
from messaging.models import SMSConfiguration, SMSMessage
from messaging.providers.africastalking import SMSRejected, message_id_from_response, send_sms
from messaging.services import send_message
from tenants.models import Church


def at_response(status='Success', status_code=101, message_id='ATXid_4a1b2c3d4e5f60718293a4b5c6d7e8f9'):
    """The shape Africa's Talking returns for a one-recipient send."""
    return {
        'SMSMessageData': {
            'Message': 'Sent to 1/1 Total Cost: KES 0.8000',
            'Recipients': [{
                'statusCode': status_code, 'number': '+254712345678', 'cost': 'KES 0.8000',
                'status': status, 'messageId': message_id,
            }],
        }
    }


class ProviderResponseTests(SimpleTestCase):
    def test_only_the_message_id_is_kept(self):
        response = at_response()
        self.assertGreater(len(str(response)), 100)
        self.assertEqual(message_id_from_response(response), 'ATXid_4a1b2c3d4e5f60718293a4b5c6d7e8f9')

    def test_queued_and_processed_messages_count_as_accepted(self):
        for code in (100, 101, 102, '101'):
            with self.subTest(code=code):
                self.assertTrue(message_id_from_response(at_response(status_code=code)))

    def test_a_refused_recipient_is_a_failure_with_the_providers_reason(self):
        with self.assertRaisesMessage(SMSRejected, 'InsufficientBalance'):
            message_id_from_response(at_response(status='InsufficientBalance', status_code=405, message_id='None'))

    def test_a_response_without_recipients_is_a_failure(self):
        with self.assertRaisesMessage(SMSRejected, 'InvalidSenderId'):
            message_id_from_response({'SMSMessageData': {'Message': 'InvalidSenderId', 'Recipients': []}})
        with self.assertRaises(SMSRejected):
            message_id_from_response('unexpected')

    def test_send_sms_returns_the_message_id(self):
        with mock.patch('messaging.providers.africastalking.africastalking') as provider:
            provider.SMS.send.return_value = at_response()
            self.assertEqual(send_sms('0712345678', 'Hello'), 'ATXid_4a1b2c3d4e5f60718293a4b5c6d7e8f9')
        provider.SMS.send.assert_called_once_with('Hello', ['+254712345678'])


class SendMessageRecordTests(TestCase):
    def setUp(self):
        self.church = Church.objects.create(name='Grace Chapel', code='GRC')

    def test_a_delivered_message_is_recorded_as_sent_with_its_id(self):
        with mock.patch('messaging.providers.africastalking.africastalking') as provider:
            provider.SMS.send.return_value = at_response()
            message = send_message(self.church, '0712345678', 'Hello')
        message.refresh_from_db()
        self.assertEqual(message.status, 'sent')
        self.assertEqual(message.provider_message_id, 'ATXid_4a1b2c3d4e5f60718293a4b5c6d7e8f9')
        self.assertIsNotNone(message.sent_at)

    def test_an_overlong_id_is_trimmed_to_fit_the_database(self):
        with mock.patch('messaging.services.send_sms', return_value='x' * 300):
            message = send_message(self.church, '0712345678', 'Hello')
        message.refresh_from_db()
        self.assertEqual(message.status, 'sent')
        self.assertEqual(len(message.provider_message_id), SMSMessage._meta.get_field('provider_message_id').max_length)

    def test_settings_with_a_stray_line_break_still_send(self):
        """A key copied into a server usually carries a line break, which a header refuses."""
        env = {'AFRICASTALKING_USERNAME': 'TesmusTechnologiesLimited\n', 'AFRICASTALKING_API_KEY': ' atsk_livekey \n'}
        with mock.patch.dict(os.environ, env), mock.patch('messaging.providers.africastalking.africastalking') as provider:
            provider.SMS.send.return_value = at_response()
            message = send_message(self.church, '0712345678', 'Hello')
        provider.initialize.assert_called_once_with('TesmusTechnologiesLimited', 'atsk_livekey')
        self.assertEqual(message.status, 'sent')

    def test_a_stray_line_break_in_the_church_sender_name_is_trimmed(self):
        SMSConfiguration.objects.create(church=self.church, sender_id=' PLCM\n')
        self.church.refresh_from_db()
        env = {'AFRICASTALKING_USERNAME': 'TesmusTechnologiesLimited', 'AFRICASTALKING_API_KEY': 'atsk_livekey'}
        with mock.patch.dict(os.environ, env), mock.patch('messaging.providers.africastalking.africastalking') as provider:
            provider.SMS.send.return_value = at_response()
            send_message(self.church, '0712345678', 'Hello')
        provider.SMS.send.assert_called_once_with('Hello', ['+254712345678'], sender_id='PLCM')

    def test_missing_settings_are_reported_in_plain_words(self):
        env = {'AFRICASTALKING_USERNAME': '', 'AFRICASTALKING_API_KEY': ''}
        with mock.patch.dict(os.environ, env):
            message = send_message(self.church, '0712345678', 'Hello')
        self.assertEqual(message.status, 'failed')
        self.assertEqual(plain_failure_reason(message.failure_reason), reasons.ACCOUNT_SETTINGS)

    def test_a_refused_recipient_is_recorded_as_failed_in_plain_words(self):
        with mock.patch('messaging.providers.africastalking.africastalking') as provider:
            provider.SMS.send.return_value = at_response(status='InsufficientBalance', status_code=405)
            message = send_message(self.church, '0712345678', 'Hello')
        self.assertEqual(message.status, 'failed')
        self.assertEqual(message.failure_reason, 'InsufficientBalance')
        self.assertEqual(message.plain_failure_reason, reasons.NO_BALANCE)
