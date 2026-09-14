from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from members import importer
from members.models import Member
from tenants.models import Church, Region

User = get_user_model()


class ImportAreasTests(TestCase):
    """Areas in a member spreadsheet become regions without any extra step."""

    def setUp(self):
        self.church = Church.objects.create(name='Grace Chapel', code='GRC')

    def test_new_areas_in_a_spreadsheet_become_regions(self):
        rows = [
            (2, {'full_name': 'Mary Wanjiku', 'phone_number': '0711000001', 'region': 'sikhendu'}),
            (3, {'full_name': 'Peter Kamau', 'phone_number': '0711000002', 'region': 'Sikhendu'}),
            (4, {'full_name': 'Ruth Chebet', 'phone_number': '0711000003', 'region': ''}),
        ]
        results = importer.validate(self.church, rows)
        self.assertEqual([row['action'] for row in results], [importer.CREATE] * 3)
        self.assertIn('New area "sikhendu" will be added as a region.', results[0]['message'])

        self.assertEqual(importer.commit(self.church, results), 3)
        self.assertEqual(list(Region.objects.filter(church=self.church).values_list('name', flat=True)), ['Sikhendu'])
        self.assertEqual(Member.objects.filter(church=self.church, region__name='Sikhendu').count(), 2)
        self.assertIsNone(Member.objects.get(full_name='Ruth Chebet').region)

    def test_the_import_page_has_no_create_tickbox(self):
        User.objects.create_user('admin', password='x', church=self.church, scope_type='church')
        self.client.login(username='admin', password='x')
        response = self.client.get(reverse('member_import'))
        self.assertContains(response, 'New areas are added as regions automatically')
        self.assertNotContains(response, 'create_places')
