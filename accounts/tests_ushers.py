from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from attendance.models import Attendance
from members.models import Member, MinistryRole
from members.services import ensure_default_ministry_roles
from services.models import Service
from tenants.models import Church, Region

User = get_user_model()
PASSWORD = 'Str0ng-pass-123'


class UsherTests(TestCase):
    """Usher sign-ins: given to members by church admins, kept to the usher screen."""

    def setUp(self):
        self.church = Church.objects.create(name='Preaching Life Change Ministry', code='PLCM', slug='plcm')
        ensure_default_ministry_roles(self.church)
        self.church.refresh_from_db()
        self.admin = User.objects.create_user('admin', password=PASSWORD, church=self.church, scope_type='church')
        self.mary = Member.objects.create(church=self.church, full_name='Mary Wanjiku', phone_number='0712 345 678', reference_number='PLCM-01')
        self.simon = Member.objects.create(church=self.church, full_name='Simon Mbuthia', phone_number='0784639561', reference_number='PLCM-02')
        self.service = Service.objects.create(church=self.church, name='Sunday Service', date=timezone.localdate())

    def create_usher(self, username='usher1', member=None, is_active=True):
        member = member or self.simon
        return User.objects.create_user(username, password=PASSWORD, church=self.church, is_usher=True,
                                        first_name=member.full_name, member=member, is_active=is_active)

    def add_usher(self, **overrides):
        data = {'member': self.simon.pk, 'username': 'simon', 'password1': PASSWORD, 'password2': PASSWORD, **overrides}
        return self.client.post(reverse('usher_list'), data)

    def login_admin(self):
        self.client.login(username='admin', password=PASSWORD)

    # --- Giving members a sign-in --------------------------------------

    def test_a_new_church_marks_ushers_with_its_ushers_ministry_role(self):
        self.assertEqual(self.church.usher_role.name, 'Ushers')

    def test_a_church_admin_makes_a_member_an_usher(self):
        self.login_admin()
        response = self.add_usher()
        self.assertRedirects(response, reverse('usher_list'), fetch_redirect_response=False)
        usher = User.objects.get(username='simon')
        self.assertTrue(usher.is_usher)
        self.assertEqual(usher.member, self.simon)
        self.assertEqual(usher.first_name, 'Simon Mbuthia')
        self.assertEqual(usher.church, self.church)
        self.assertEqual(usher.scope_type, 'none')
        self.assertFalse(usher.is_staff)
        self.assertTrue(self.simon.ministry_roles.filter(pk=self.church.usher_role_id).exists())

    def test_the_members_pages_show_the_usher_role_and_sign_in(self):
        self.login_admin()
        self.add_usher()
        self.assertContains(self.client.get(reverse('member_list')), 'Ushers')
        detail = self.client.get(reverse('member_detail', args=[self.simon.pk]))
        self.assertContains(detail, 'Usher sign-in')
        self.assertContains(detail, 'simon')
        self.assertContains(self.client.get(reverse('ministry_role_list')), 'Ushers')

    def test_a_member_can_have_only_one_sign_in(self):
        self.create_usher()
        self.login_admin()
        self.assertNotContains(self.client.get(reverse('usher_list')), f'name="member" value="{self.simon.pk}"')
        response = self.add_usher(username='simon2')
        self.assertContains(response, 'Choose one of your members who does not have a sign-in yet.')
        self.assertFalse(User.objects.filter(username='simon2').exists())

    def test_another_churchs_member_cannot_be_chosen(self):
        other = Church.objects.create(name='Hope Centre', code='HOP')
        outsider = Member.objects.create(church=other, full_name='Ruth Chebet', phone_number='0733000222', reference_number='HOP-01')
        self.login_admin()
        response = self.add_usher(member=outsider.pk)
        self.assertContains(response, 'Choose one of your members who does not have a sign-in yet.')
        self.assertFalse(User.objects.filter(username='simon').exists())

    def test_passwords_must_match_and_usernames_must_be_free(self):
        self.login_admin()
        response = self.add_usher(username='ADMIN', password2='different-pass-456')
        self.assertContains(response, 'That username is already taken.')
        self.assertContains(response, 'The two passwords do not match.')
        self.assertFalse(User.objects.filter(is_usher=True).exists())

    def test_members_with_the_usher_role_but_no_sign_in_are_listed(self):
        self.mary.ministry_roles.add(self.church.usher_role)
        self.login_admin()
        page = self.client.get(reverse('usher_list'))
        self.assertContains(page, 'Ushers without a sign-in')
        self.assertContains(page, f'?member={self.mary.pk}')
        preselected = self.client.get(reverse('usher_list'), {'member': self.mary.pk})
        self.assertContains(preselected, f'value="{self.mary.pk}" data-member-name="Mary Wanjiku" checked')

    def test_an_older_unlinked_sign_in_can_be_linked_to_its_member(self):
        usher = User.objects.create_user('Simoo', password=PASSWORD, church=self.church, is_usher=True, first_name='Simon Mbuthia')
        self.login_admin()
        self.assertContains(self.client.get(reverse('usher_list')), 'Not linked')
        page = self.client.get(reverse('usher_link', args=[usher.pk]))
        self.assertContains(page, f'value="{self.simon.pk}" data-member-name="Simon Mbuthia" checked')
        response = self.client.post(reverse('usher_link', args=[usher.pk]), {'member': self.simon.pk})
        self.assertRedirects(response, reverse('usher_list'), fetch_redirect_response=False)
        usher.refresh_from_db()
        self.assertEqual(usher.member, self.simon)
        self.assertTrue(self.simon.ministry_roles.filter(pk=self.church.usher_role_id).exists())

    def test_the_church_chooses_which_ministry_role_marks_ushers(self):
        stewards = MinistryRole.objects.create(church=self.church, name='Stewards')
        self.login_admin()
        self.client.post(reverse('usher_role_update'), {'usher_role': stewards.pk})
        self.church.refresh_from_db()
        self.assertEqual(self.church.usher_role, stewards)
        foreign = MinistryRole.objects.create(church=Church.objects.create(name='Hope Centre', code='HOP'), name='Ushers')
        self.client.post(reverse('usher_role_update'), {'usher_role': foreign.pk})
        self.church.refresh_from_db()
        self.assertEqual(self.church.usher_role, stewards)

    def test_turning_a_sign_in_off_keeps_the_ministry_role(self):
        usher = self.create_usher()
        self.simon.ministry_roles.add(self.church.usher_role)
        self.login_admin()
        self.client.post(reverse('usher_toggle_active', args=[usher.pk]))
        usher.refresh_from_db()
        self.assertFalse(usher.is_active)
        self.assertTrue(self.simon.ministry_roles.filter(pk=self.church.usher_role_id).exists())
        self.client.logout()
        self.assertFalse(self.client.login(username='usher1', password=PASSWORD))

    def test_only_church_wide_administrators_manage_ushers(self):
        region = Region.objects.create(church=self.church, name='Sikhendu')
        User.objects.create_user('pastor', password=PASSWORD, church=self.church, scope_type='region', scope_region=region)
        self.client.login(username='pastor', password=PASSWORD)
        self.assertRedirects(self.client.get(reverse('usher_list')), reverse('home'), fetch_redirect_response=False)

    # --- Using the usher screen ----------------------------------------

    def test_an_usher_signing_in_goes_straight_to_the_check_in_screen(self):
        self.create_usher()
        response = self.client.post(reverse('church_login', args=['plcm']),
                                    {'username': 'usher1', 'password': PASSWORD}, follow=True)
        self.assertEqual(response.redirect_chain[-1][0], reverse('usher_home'))
        self.assertContains(response, 'Sunday Service')

    def test_an_usher_can_open_nothing_else(self):
        self.create_usher()
        self.client.login(username='usher1', password=PASSWORD)
        for url in (reverse('home'), reverse('member_list'), reverse('region_list'), reverse('message_list'),
                    reverse('settings_page'), reverse('usher_list'), reverse('notification_list'), '/admin/'):
            with self.subTest(url=url):
                self.assertRedirects(self.client.get(url), reverse('usher_home'), fetch_redirect_response=False)

    def test_an_usher_finds_and_checks_in_a_member(self):
        usher = self.create_usher()
        self.client.login(username='usher1', password=PASSWORD)
        page = self.client.get(reverse('usher_service', args=[self.service.pk]), {'q': 'mary'})
        self.assertContains(page, 'Mary Wanjiku')
        self.assertNotContains(page, '0712 345 678')
        response = self.client.post(reverse('usher_check_in', args=[self.service.pk]), {'member': self.mary.pk, 'q': 'mary'})
        self.assertRedirects(response, reverse('usher_service', args=[self.service.pk]) + '?q=mary', fetch_redirect_response=False)
        attendance = Attendance.objects.get(service=self.service, member=self.mary)
        self.assertEqual(attendance.method, 'usher')
        self.assertEqual(attendance.checked_in_by, usher)

    def test_an_usher_can_search_by_phone_number(self):
        self.create_usher()
        self.client.login(username='usher1', password=PASSWORD)
        page = self.client.get(reverse('usher_service', args=[self.service.pk]), {'q': '+254712345678'})
        self.assertContains(page, 'Mary Wanjiku')

    def test_an_usher_cannot_use_another_churchs_service(self):
        other = Church.objects.create(name='Hope Centre', code='HOP')
        other_service = Service.objects.create(church=other, name='Other Service', date=timezone.localdate())
        self.create_usher()
        self.client.login(username='usher1', password=PASSWORD)
        self.assertEqual(self.client.get(reverse('usher_service', args=[other_service.pk])).status_code, 404)

    def test_church_admins_can_also_use_the_usher_screen(self):
        self.login_admin()
        response = self.client.get(reverse('usher_home'))
        self.assertContains(response, 'Sunday Service')
        self.assertContains(response, 'Dashboard')
