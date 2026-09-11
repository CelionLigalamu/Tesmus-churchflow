from django.test import TestCase

from django.contrib.auth import get_user_model
from django.urls import reverse

from tenants.models import Church


User = get_user_model()


class ChurchLoginTests(TestCase):
    def setUp(self):
        self.church_a = Church.objects.create(
            name='Preaching Life Change Ministry',
            code='PLCM',
            primary_color='#123456',
        )
        self.church_b = Church.objects.create(
            name='Another Church',
            code='ANOTHER',
        )
        self.user_a = User.objects.create_user(
            username='plcm_admin',
            password='testpass123',
            church=self.church_a,
        )

    def test_church_login_uses_slug_and_keeps_username_password_authentication(self):
        response = self.client.post(
            reverse('church_login', kwargs={'church_slug': self.church_a.slug}),
            {'username': 'plcm_admin', 'password': 'testpass123'},
        )

        self.assertRedirects(response, reverse('home'))

    def test_church_login_renders_church_branding_context(self):
        response = self.client.get(
            reverse('church_login', kwargs={'church_slug': self.church_a.slug}),
        )

        self.assertContains(response, 'Preaching Life Change Ministry')
        self.assertContains(response, '#123456')

    def test_user_cannot_login_through_another_church_url(self):
        response = self.client.post(
            reverse('church_login', kwargs={'church_slug': self.church_b.slug}),
            {'username': 'plcm_admin', 'password': 'testpass123'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.wsgi_request.user.is_authenticated)

# Create your tests here.
