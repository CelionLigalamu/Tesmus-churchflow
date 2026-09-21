"""Tests for church colour handling and the dashboard light/dark theme."""
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from tenants.admin_forms import ChurchAdminForm
from tenants.colors import (
    DARK_BODY,
    DARK_SURFACE,
    DEFAULT_PRIMARY,
    LIGHT_BODY,
    LIGHT_SURFACE,
    TEXT_CONTRAST,
    UI_CONTRAST,
    church_palette,
    contrast_ratio,
    normalize_hex,
)
from tenants.models import Church

User = get_user_model()


class ColourMathsTests(SimpleTestCase):
    def test_normalize_hex(self):
        self.assertEqual(normalize_hex('#abc'), '#AABBCC')
        self.assertEqual(normalize_hex('1d3f91'), '#1D3F91')
        self.assertEqual(normalize_hex(' #386641 '), '#386641')
        for bad in ('green', '#12345', '', None, 'red;}body{'):
            self.assertIsNone(normalize_hex(bad))

    def test_contrast_ratio_extremes(self):
        self.assertAlmostEqual(contrast_ratio('#FFFFFF', '#000000'), 21, places=1)
        self.assertAlmostEqual(contrast_ratio('#386641', '#386641'), 1, places=5)

    def test_derived_colours_stay_readable_for_any_church_colour(self):
        # Pale, neon, very dark and real church colours.
        for colour in ('#FFFFFF', '#FFFF00', '#F5F5F5', '#0B1F4D', '#000000', '#808080',
                       '#386641', '#0D3B8C', '#ADBABD', '#262730'):
            with self.subTest(colour=colour):
                palette = church_palette(Church(primary_color=colour, secondary_color=colour, accent_color=colour))
                for background in (palette['--brand-tint-light'], LIGHT_SURFACE, LIGHT_BODY):
                    self.assertGreaterEqual(contrast_ratio(palette['--brand-ink-light'], background), TEXT_CONTRAST)
                for background in (palette['--brand-tint-dark'], DARK_SURFACE, DARK_BODY):
                    self.assertGreaterEqual(contrast_ratio(palette['--brand-ink-dark'], background), TEXT_CONTRAST)
                for background in (palette['--brand-accent-tint-light'], LIGHT_SURFACE):
                    self.assertGreaterEqual(contrast_ratio(palette['--brand-accent-ink-light'], background), UI_CONTRAST)
                for background in (palette['--brand-accent-tint-dark'], DARK_SURFACE):
                    self.assertGreaterEqual(contrast_ratio(palette['--brand-accent-ink-dark'], background), UI_CONTRAST)
                self.assertGreaterEqual(contrast_ratio(palette['--brand-on-primary'], palette['--brand-primary']), TEXT_CONTRAST)
                # Filled buttons stand out from the page and their labels read.
                for background in (LIGHT_SURFACE, LIGHT_BODY):
                    self.assertGreaterEqual(contrast_ratio(palette['--brand-fill-light'], background), UI_CONTRAST)
                for background in (DARK_SURFACE, DARK_BODY):
                    self.assertGreaterEqual(contrast_ratio(palette['--brand-fill-dark'], background), UI_CONTRAST)
                self.assertGreaterEqual(contrast_ratio(palette['--brand-on-fill-light'], palette['--brand-fill-light']), TEXT_CONTRAST)
                self.assertGreaterEqual(contrast_ratio(palette['--brand-on-fill-dark'], palette['--brand-fill-dark']), TEXT_CONTRAST)

    def test_invalid_stored_colours_fall_back_to_defaults(self):
        palette = church_palette(Church(primary_color='red;}body{x', secondary_color='', accent_color=None))
        self.assertEqual(palette['--brand-primary'], DEFAULT_PRIMARY)
        self.assertTrue(all(value.startswith('#') and len(value) == 7 for value in palette.values()))


class ChurchAdminFormTests(TestCase):
    def build(self, **overrides):
        data = {
            'name': 'Colour Test Church', 'code': 'CTC', 'slug': 'colour-test',
            'primary_color': '#386641', 'secondary_color': '#F5EEE4', 'accent_color': '#C6A16A',
            'is_active': 'on', 'last_member_sequence': 0, 'self_registration_enabled': 'on',
            'absence_alert_after': 3,
        }
        data.update(overrides)
        return ChurchAdminForm(data=data)

    def test_accepts_existing_church_colours(self):
        for primary in ('#386641', '#0D3B8C'):
            with self.subTest(primary=primary):
                form = self.build(primary_color=primary)
                self.assertTrue(form.is_valid(), form.errors)

    def test_rejects_primary_too_pale_for_buttons_and_links(self):
        form = self.build(primary_color='#F5F5F5')
        self.assertFalse(form.is_valid())
        self.assertIn('too pale', form.errors['primary_color'][0])

    def test_rejects_values_that_are_not_hex_colours(self):
        form = self.build(accent_color='green')
        self.assertFalse(form.is_valid())
        self.assertIn('accent_color', form.errors)

    def test_normalises_shorthand_and_case(self):
        form = self.build(primary_color='#123', accent_color='#c6a16a')
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['primary_color'], '#112233')
        self.assertEqual(form.cleaned_data['accent_color'], '#C6A16A')

    def test_warns_but_saves_when_login_footer_would_be_hard_to_read(self):
        form = self.build(secondary_color='#ADBABD')
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(len(form.colour_warnings), 1)
        self.assertIn('login page', form.colour_warnings[0])


class ThemePreferenceTests(TestCase):
    def setUp(self):
        self.church = Church.objects.create(name='Theme Church', code='THM', primary_color='#386641')
        self.user = User.objects.create_user('theme_admin', password='x', church=self.church, scope_type='church')
        self.client.login(username='theme_admin', password='x')
        self.url = reverse('set_theme_preference')

    def test_new_people_follow_their_device_by_default(self):
        html = self.client.get(reverse('home')).content.decode()
        self.assertIn('data-theme-preference="system"', html)
        self.assertIn('--brand-ink-dark:', html)

    def test_saving_a_preference(self):
        response = self.client.post(self.url, {'theme': 'dark'})
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.theme_preference, 'dark')
        html = self.client.get(reverse('home')).content.decode()
        self.assertIn('data-theme="dark"', html)
        self.assertIn('data-bs-theme="dark"', html)

    def test_rejects_unknown_values(self):
        response = self.client.post(self.url, {'theme': 'purple'})
        self.assertEqual(response.status_code, 400)
        self.user.refresh_from_db()
        self.assertEqual(self.user.theme_preference, 'system')

    def test_only_accepts_post(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_requires_sign_in(self):
        self.client.logout()
        response = self.client.post(self.url, {'theme': 'dark'})
        self.assertEqual(response.status_code, 302)

    def test_login_pages_never_switch_to_dark(self):
        self.user.theme_preference = 'dark'
        self.user.save()
        self.client.logout()
        html = self.client.get(reverse('church_login', args=[self.church.slug])).content.decode()
        self.assertNotIn('data-theme', html)
