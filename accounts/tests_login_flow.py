from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from tenants.models import Church

User = get_user_model()


class SignInDestinationTests(TestCase):
    def setUp(self):
        self.church = Church.objects.create(name='Pentecostal Life Church Ministries', code='PLCM', slug='plcm')

    def test_tesmus_staff_go_straight_to_django_admin_after_signing_in(self):
        User.objects.create_user('tesmus', password='x', is_tesmus_staff=True, is_staff=True, is_superuser=True)
        response = self.client.post(reverse('login'), {'username': 'tesmus', 'password': 'x'}, follow=True)
        self.assertEqual(response.redirect_chain[-1][0], reverse('admin:index'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateNotUsed(response, 'dashboard/tesmus_home.html')

    def test_the_church_setup_link_also_takes_tesmus_staff_to_admin(self):
        User.objects.create_user('tesmus', password='x', is_tesmus_staff=True, is_staff=True, is_superuser=True)
        self.client.login(username='tesmus', password='x')
        self.assertRedirects(self.client.get(reverse('settings_page')), reverse('admin:index'))

    def test_tesmus_staff_without_admin_access_keep_the_platform_page(self):
        User.objects.create_user('helper', password='x', is_tesmus_staff=True)
        self.client.login(username='helper', password='x')
        self.assertTemplateUsed(self.client.get(reverse('home')), 'dashboard/tesmus_home.html')

    def test_church_users_signing_in_at_the_general_page_reach_their_dashboard(self):
        User.objects.create_user('plcm_admin', password='x', church=self.church, scope_type='church')
        response = self.client.post(reverse('login'), {'username': 'plcm_admin', 'password': 'x'})
        self.assertRedirects(response, reverse('home'))

    def test_a_requested_page_is_still_opened_after_signing_in(self):
        User.objects.create_user('plcm_admin', password='x', church=self.church, scope_type='church')
        response = self.client.post(
            reverse('login') + '?next=' + reverse('member_list'),
            {'username': 'plcm_admin', 'password': 'x'},
        )
        self.assertRedirects(response, reverse('member_list'))


class LogoutDestinationTests(TestCase):
    def setUp(self):
        self.church = Church.objects.create(name='Pentecostal Life Church Ministries', code='PLCM', slug='plcm')

    def test_church_users_return_to_their_own_church_sign_in_page(self):
        User.objects.create_user('plcm_admin', password='x', church=self.church, scope_type='church')
        self.client.login(username='plcm_admin', password='x')
        response = self.client.post(reverse('logout'))
        self.assertRedirects(response, reverse('church_login', args=['plcm']))
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_tesmus_staff_return_to_the_general_sign_in_page(self):
        User.objects.create_user('tesmus', password='x', is_tesmus_staff=True, is_staff=True, is_superuser=True)
        self.client.login(username='tesmus', password='x')
        self.assertRedirects(self.client.post(reverse('logout')), reverse('login'))

    def test_users_of_an_inactive_church_go_to_the_general_sign_in_page(self):
        User.objects.create_user('plcm_admin', password='x', church=self.church, scope_type='church')
        self.client.login(username='plcm_admin', password='x')
        self.church.is_active = False
        self.church.save()
        self.assertRedirects(self.client.post(reverse('logout')), reverse('login'))

    def test_logging_out_when_already_signed_out_goes_to_the_general_page(self):
        self.assertRedirects(self.client.post(reverse('logout')), reverse('login'))

    def test_logout_still_requires_a_form_post(self):
        self.assertEqual(self.client.get(reverse('logout')).status_code, 405)
