import re
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings

LIVE_STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'churchflow_platform.storage.ForgivingManifestStaticFilesStorage'},
}


class LiveServerStaticFilesTests(TestCase):
    """The live server fingerprints static files; signed-in admin pages must still render.

    The strict storage crashed every signed-in admin page with a Server Error (500)
    because the Jazzmin theme links to a folder ({% static 'vendor/bootswatch' %}).
    """

    @classmethod
    def setUpClass(cls):
        cls.static_root = tempfile.mkdtemp()
        cls.live_static = override_settings(STATIC_ROOT=cls.static_root, STORAGES=LIVE_STORAGES)
        cls.live_static.enable()
        # The same step Render runs in build.sh.
        call_command('collectstatic', interactive=False, verbosity=0)
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls.live_static.disable()
        shutil.rmtree(cls.static_root, ignore_errors=True)

    def test_signed_in_admin_pages_render(self):
        admin = get_user_model().objects.create_superuser('tesmus', password='x', is_tesmus_staff=True)
        self.client.force_login(admin)
        for path in ('/admin/', '/admin/accounts/user/', '/admin/tenants/church/', '/admin/members/member/'):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'data-theme-base="/static/vendor/bootswatch"')

    def test_real_files_keep_their_fingerprinted_names(self):
        admin = get_user_model().objects.create_superuser('tesmus', password='x', is_tesmus_staff=True)
        self.client.force_login(admin)
        page = self.client.get('/admin/').content.decode()
        self.assertRegex(page, r'/static/css/admin-tesmus\.[0-9a-f]{12}\.css')
        self.assertTrue(re.search(r'/static/images/branding/tesmus-logo\.[0-9a-f]{12}\.png', page))
