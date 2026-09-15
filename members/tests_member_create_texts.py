from unittest import mock

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.urls import reverse

from members.models import Member
from messaging.models import SMSMessage, SMSTemplate
from messaging.services import get_system_template
from tenants.models import Church

User = get_user_model()


class RunAtOnce:
    """Stands in for threading.Thread so the background text runs inside the test."""

    def __init__(self, target, args=(), **kwargs):
        self.target, self.args = target, args

    def start(self):
        with mock.patch('members.reference_texts.connections.close_all'):
            self.target(*self.args)


class NewMembersAreTextedTheirReferenceNumberTests(TestCase):
    """A member added by an administrator gets their reference number, like self-registration."""

    def setUp(self):
        self.church = Church.objects.create(name='Grace Chapel', code='GRC')
        self.admin_user = User.objects.create_user('admin', password='x', church=self.church, scope_type='church')
        send_sms = mock.patch('messaging.services.send_sms', return_value='ATXid_1')
        self.send_sms = send_sms.start()
        self.addCleanup(send_sms.stop)
        thread = mock.patch('members.reference_texts.threading.Thread', RunAtOnce)
        thread.start()
        self.addCleanup(thread.stop)

    def add_from_dashboard(self):
        self.client.login(username='admin', password='x')
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(reverse('member_create'), {
                'full_name': 'Celion Ligalamu', 'phone_number': '0704786804', 'region': 'Nairobi',
            }, follow=True)

    def page_messages(self, response):
        return ' '.join(str(message) for message in response.context['messages'])

    def test_a_member_added_on_the_dashboard_is_texted_their_reference_number(self):
        response = self.add_from_dashboard()
        member = Member.objects.get(full_name='Celion Ligalamu')
        text = SMSMessage.objects.get()
        self.assertEqual((text.recipient_phone, text.audience_label, text.status),
                         ('0704786804', f'Reference number - {member.reference_number}', 'sent'))
        self.assertIn(member.reference_number, text.body)
        self.assertIn(f'is being texted to 0704786804', self.page_messages(response))

    def test_nothing_is_texted_when_the_church_switched_the_message_off(self):
        get_system_template(self.church, 'member_reference')
        SMSTemplate.objects.filter(church=self.church, name='member_reference').update(is_active=False)
        response = self.add_from_dashboard()
        self.assertTrue(Member.objects.filter(full_name='Celion Ligalamu').exists())
        self.assertFalse(SMSMessage.objects.exists())
        self.assertIn('No text was sent because', self.page_messages(response))

    def test_editing_a_member_in_django_admin_does_not_text_them_again(self):
        model_admin = admin.site._registry[Member]
        staff = User.objects.create_superuser('tesmus', password='x', is_tesmus_staff=True)
        request = RequestFactory().post('/admin/members/member/add/')
        request.user = staff
        member = Member(church=self.church, full_name='Ruth Chebet', phone_number='0733000222')

        with self.captureOnCommitCallbacks(execute=True):
            model_admin.save_model(request, member, form=None, change=False)
        self.assertEqual(SMSMessage.objects.filter(recipient_phone='0733000222').count(), 1)

        member.full_name = 'Ruth Chebet Kiprop'
        with self.captureOnCommitCallbacks(execute=True):
            model_admin.save_model(request, member, form=None, change=True)
        self.assertEqual(SMSMessage.objects.filter(recipient_phone='0733000222').count(), 1)
