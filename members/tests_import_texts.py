from unittest import mock

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from members.models import Member
from members.reference_texts import send_reference_numbers
from messaging.models import SMSMessage, SMSTemplate
from messaging.services import get_system_template
from tenants.models import Church

User = get_user_model()

# Two good rows and one without a name, which the import refuses.
CSV = (
    'full_name,phone_number,region\n'
    'Mary Wanjiku,0711000001,Kasarani\n'
    'Peter Kamau,0711000002,Kasarani\n'
    ',0711000003,Kasarani\n'
)


class RunAtOnce:
    """Stands in for threading.Thread so the background texts run inside the test.

    A real background thread closes its own database connections when done; here
    it shares the test's connection, which must stay open.
    """

    def __init__(self, target, args=(), **kwargs):
        self.target, self.args = target, args

    def start(self):
        with mock.patch('members.reference_texts.connections.close_all') as close_all:
            self.target(*self.args)
        close_all.assert_called_once()


class ImportedMembersAreTextedTests(TestCase):
    def setUp(self):
        self.church = Church.objects.create(name='Grace Chapel', code='GRC')
        User.objects.create_user('admin', password='x', church=self.church, scope_type='church')
        self.client.login(username='admin', password='x')
        send_sms = mock.patch('messaging.services.send_sms', return_value='ATXid_1')
        self.send_sms = send_sms.start()
        self.addCleanup(send_sms.stop)
        thread = mock.patch('members.reference_texts.threading.Thread', RunAtOnce)
        thread.start()
        self.addCleanup(thread.stop)

    def upload(self):
        csv_file = SimpleUploadedFile('members.csv', CSV.encode(), content_type='text/csv')
        return self.client.post(reverse('member_import'), {'file': csv_file})

    def confirm(self):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(reverse('member_import_confirm'), follow=True)

    def page_messages(self, response):
        return ' '.join(str(message) for message in response.context['messages'])

    def test_each_imported_member_is_texted_their_reference_number(self):
        self.assertContains(self.upload(), 'Each new member will be texted their reference number.')
        response = self.confirm()
        self.assertIn('Each new member is being texted their reference number.', self.page_messages(response))
        texts = SMSMessage.objects.order_by('audience_label')
        self.assertEqual(
            [(text.recipient_phone, text.audience_label, text.status) for text in texts],
            [('0711000001', 'Reference number - GRC-01', 'sent'), ('0711000002', 'Reference number - GRC-02', 'sent')],
        )
        self.assertIn('GRC-01', texts[0].body)

    def test_texts_start_only_once_the_import_is_saved(self):
        self.upload()
        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            self.client.post(reverse('member_import_confirm'))
        self.assertEqual(Member.objects.count(), 2)
        self.assertFalse(SMSMessage.objects.exists())
        self.assertEqual(len(callbacks), 1)

    def test_nothing_is_texted_when_the_church_switched_the_message_off(self):
        get_system_template(self.church, 'member_reference')
        SMSTemplate.objects.filter(church=self.church, name='member_reference').update(is_active=False)
        self.assertContains(self.upload(), 'No text messages will be sent because the member reference number message is switched off')
        with mock.patch('members.reference_texts.threading.Thread') as thread:
            response = self.confirm()
        thread.assert_not_called()
        self.assertEqual(Member.objects.count(), 2)
        self.assertFalse(SMSMessage.objects.exists())
        self.assertIn('No text messages were sent because', self.page_messages(response))

    def test_a_failed_text_does_not_stop_the_others(self):
        self.send_sms.side_effect = [Exception('Insufficient balance'), 'ATXid_2']
        self.upload()
        self.confirm()
        self.assertEqual(
            list(SMSMessage.objects.order_by('audience_label').values_list('status', flat=True)),
            ['failed', 'sent'],
        )

    def test_an_unexpected_error_for_one_member_is_logged_and_the_rest_still_sent(self):
        first = Member.objects.create(church=self.church, full_name='Mary Wanjiku', phone_number='0711000001', reference_number='GRC-01')
        second = Member.objects.create(church=self.church, full_name='Peter Kamau', phone_number='0711000002', reference_number='GRC-02')
        with mock.patch('members.reference_texts.send_reference_number_sms', side_effect=[RuntimeError('boom'), None]) as sender, \
                self.assertLogs('members.reference_texts', level='ERROR'):
            send_reference_numbers([first.pk, second.pk])
        self.assertEqual([call.args[0] for call in sender.call_args_list], [first, second])


class MemberListOrderTests(TestCase):
    def test_members_are_listed_in_reference_number_order(self):
        church = Church.objects.create(name='Grace Chapel', code='GRC')
        User.objects.create_user('admin', password='x', church=church, scope_type='church')
        for reference, name in (('GRC-100', 'Aaron Otieno'), ('GRC-09', 'Zawadi Achieng'), ('GRC-10', 'Brian Mwangi'), ('GRC-01', 'Yusuf Kibet')):
            Member.objects.create(church=church, full_name=name, phone_number=f'07{len(reference)}{reference[-2:]}00000', reference_number=reference)
        self.client.login(username='admin', password='x')
        html = self.client.get(reverse('member_list')).content.decode()
        positions = [html.index(f'>{reference}<') for reference in ('GRC-01', 'GRC-09', 'GRC-10', 'GRC-100')]
        self.assertEqual(positions, sorted(positions))
