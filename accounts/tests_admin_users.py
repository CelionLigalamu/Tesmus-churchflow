from django.contrib.auth import get_user_model
from django.test import TestCase

from members.models import Member
from tenants.models import Church

User = get_user_model()
PASSWORD = 'Str0ng-pass-123'


class AdminUserPagesTests(TestCase):
    """The /admin/ pages for adding and editing sign-ins."""

    def setUp(self):
        self.church = Church.objects.create(name='Preaching Life Change Ministry', code='PLCM', slug='plcm')
        self.other = Church.objects.create(name='Hope Centre', code='HOP', slug='hope')
        self.simon = Member.objects.create(church=self.church, full_name='Simon Mbuthia', phone_number='0784639561', reference_number='PLCM-02')
        User.objects.create_superuser('tesmus', password=PASSWORD, is_tesmus_staff=True)
        self.client.login(username='tesmus', password=PASSWORD)

    def add_user(self, **overrides):
        data = {
            'username': 'simon', 'usable_password': 'true', 'password1': PASSWORD, 'password2': PASSWORD,
            'church': self.church.pk, 'scope_type': 'none', 'is_usher': 'on', 'member': self.simon.pk, **overrides,
        }
        return self.client.post('/admin/accounts/user/add/', data)

    def test_the_add_user_page_opens(self):
        self.assertEqual(self.client.get('/admin/accounts/user/add/').status_code, 200)

    def test_a_user_can_be_added_and_linked_to_a_member(self):
        response = self.add_user()
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(username='simon')
        self.assertEqual(user.member, self.simon)
        self.assertTrue(user.check_password(PASSWORD))
        self.assertEqual(self.client.get(f'/admin/accounts/user/{user.pk}/change/').status_code, 200)

    def test_a_member_of_another_church_is_refused(self):
        response = self.add_user(church=self.other.pk)
        self.assertContains(response, 'Choose a member of the same church as this sign-in.')
        self.assertFalse(User.objects.filter(username='simon').exists())
