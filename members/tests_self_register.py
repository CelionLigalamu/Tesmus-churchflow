from unittest import mock

from django.test import TestCase, override_settings
from django.urls import reverse

from members.models import Member
from tenants.colors import church_palette
from tenants.models import Church, Region

BRIAN = {'full_name': 'Brian Irungu', 'phone_number': '0765432789', 'region': 'Sikhendu'}


class SelfRegistrationPageTests(TestCase):
    """The public page members use to register themselves."""

    def setUp(self):
        provider = mock.patch('messaging.services.send_sms', return_value={'ok': 1})
        provider.start()
        self.addCleanup(provider.stop)
        self.church = Church.objects.create(name='Preaching Life Change Ministry', code='PLCM', primary_color='#123F92')
        self.url = reverse('member_self_register', args=[self.church.registration_token])

    def test_every_field_including_the_area_is_required(self):
        page = self.client.get(self.url)
        self.assertContains(page, 'Where you live')
        self.assertNotContains(page, '(optional)')
        response = self.client.post(self.url, {'full_name': '', 'phone_number': '', 'region': ''})
        self.assertContains(response, 'Please enter your full name.')
        self.assertContains(response, 'Please enter your phone number.')
        self.assertContains(response, 'Please enter the area where you live.')
        self.assertFalse(Member.objects.exists())

    def test_the_area_must_be_a_real_name(self):
        response = self.client.post(self.url, {**BRIAN, 'region': '12'})
        self.assertContains(response, 'Please enter the area where you live.')
        self.assertFalse(Region.objects.exists())

    def test_a_new_area_typed_by_a_member_becomes_a_region(self):
        self.client.post(self.url, {**BRIAN, 'region': '  sikhendu '})
        region = Region.objects.get(church=self.church)
        self.assertEqual(region.name, 'Sikhendu')
        self.assertEqual(Member.objects.get().region, region)

    def test_the_next_member_typing_the_same_area_joins_that_region(self):
        Region.objects.create(church=self.church, name='Sikhendu')
        self.client.post(self.url, {**BRIAN, 'region': 'SIKHENDU'})
        self.assertEqual(Region.objects.filter(church=self.church).count(), 1)
        self.assertEqual(Member.objects.get().region.name, 'Sikhendu')
        self.assertContains(self.client.get(self.url), '<option value="Sikhendu">')

    def test_a_form_with_a_mistake_never_creates_a_region(self):
        self.client.post(self.url, {**BRIAN, 'phone_number': '12', 'region': 'Msharage'})
        self.assertFalse(Region.objects.exists())

    def test_a_general_welcome_is_shown_by_default(self):
        response = self.client.get(self.url)
        self.assertContains(response, 'Welcome to Preaching Life Change Ministry')
        self.assertContains(response, 'We are glad to have you with us.')

    @override_settings(SELF_REGISTRATION_DEFAULT_IMAGE='https://images.unsplash.com/photo-example?w=1400')
    def test_the_default_photo_is_shown_when_the_church_has_none(self):
        response = self.client.get(self.url)
        self.assertContains(response, 'class="join-panel has-image"')
        self.assertContains(response, 'src="https://images.unsplash.com/photo-example?w=1400"')

    @override_settings(SELF_REGISTRATION_DEFAULT_IMAGE='https://images.unsplash.com/photo-example?w=1400')
    def test_a_churchs_own_photo_replaces_the_default(self):
        self.church.registration_image = 'church_registration/plcm-welcome.jpg'
        self.church.save()
        response = self.client.get(self.url)
        self.assertContains(response, 'church_registration/plcm-welcome.jpg')
        self.assertNotContains(response, 'photo-example')

    @override_settings(SELF_REGISTRATION_DEFAULT_IMAGE='')
    def test_with_no_photo_at_all_the_church_colours_show(self):
        response = self.client.get(self.url)
        self.assertNotContains(response, 'join-panel-image')
        self.assertContains(response, 'class="join-panel"')

    def test_a_church_can_show_its_own_heading_and_message(self):
        self.church.registration_heading = 'Building Lives, Changing Nations'
        self.church.registration_message = 'Karibu nyumbani.'
        self.church.save()
        response = self.client.get(self.url)
        self.assertContains(response, 'Building Lives, Changing Nations')
        self.assertContains(response, 'Karibu nyumbani.')
        self.assertNotContains(response, 'Welcome to Preaching Life Change Ministry')

    def test_the_welcome_panel_comes_before_the_form(self):
        # On the left on computers, and first on phones.
        html = self.client.get(self.url).content.decode()
        self.assertLess(html.index('class="join-panel'), html.index('class="join-card"'))
        done = self.client.post(self.url, BRIAN).content.decode()
        self.assertLess(done.index('class="join-panel'), done.index('class="join-card"'))

    def test_the_page_uses_the_church_colours(self):
        html = self.client.get(self.url).content.decode()
        self.assertIn(f"--brand-fill-light: {church_palette(self.church)['--brand-fill-light']};", html)

    def test_registering_shows_the_reference_number_with_a_copy_button(self):
        response = self.client.post(self.url, BRIAN)
        member = Member.objects.get(church=self.church)
        self.assertContains(response, 'Welcome, Brian Irungu')
        self.assertContains(response, member.reference_number)
        self.assertContains(response, 'data-copy-target="reference-number"')
        self.assertContains(response, f'href="{self.url}"')

    def test_mistakes_are_shown_on_the_form(self):
        Member.objects.create(church=self.church, full_name='Brian Irungu', phone_number='0765432789', reference_number='PLCM-01')
        response = self.client.post(self.url, BRIAN)
        self.assertContains(response, 'This phone number is already registered at this church.')
        self.assertContains(response, 'join-field-error')
