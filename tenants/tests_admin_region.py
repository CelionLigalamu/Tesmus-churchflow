from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from members.models import Member
from tenants.models import Church, Region
from tenants.services import resolve_region
from visitors.models import Visitor

User = get_user_model()


class AdminTypedRegionTests(TestCase):
    """Typing a member's or visitor's area in Django admin."""

    def setUp(self):
        self.ack = Church.objects.create(name='Anglican Churches of Kenya', code='ACK')
        self.plcm = Church.objects.create(name='Pentecostal Life Church Ministries', code='PLCM')
        self.kasarani = Region.objects.create(church=self.ack, name='Kasarani')
        User.objects.create_superuser('tesmus', 'admin@example.com', 'x')
        self.client.login(username='tesmus', password='x')

    def add_member(self, church, region):
        data = {'church': church.pk, 'region': region, 'full_name': 'Mary Wanjiku', 'phone_number': '0712345678'}
        return self.client.post(reverse('admin:members_member_add'), data)

    def test_a_typed_area_matches_whatever_the_capitals_and_spaces(self):
        response = self.add_member(self.ack, '  kasarani ')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Member.objects.get().region, self.kasarani)
        self.assertEqual(Region.objects.count(), 1)

    def test_a_new_area_is_added_as_a_region_of_the_chosen_church(self):
        response = self.add_member(self.ack, 'embakasi')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Member.objects.get().region, Region.objects.get(church=self.ack, name='Embakasi'))

    def test_another_churchs_region_is_never_used(self):
        self.add_member(self.plcm, 'Kasarani')
        member = Member.objects.get()
        self.assertEqual(member.region.church, self.plcm)
        self.assertNotEqual(member.region, self.kasarani)

    def test_a_blank_area_saves_without_one(self):
        self.add_member(self.ack, '')
        self.assertIsNone(Member.objects.get().region)

    def test_there_is_no_create_tickbox_any_more(self):
        self.assertNotContains(self.client.get(reverse('admin:members_member_add')), 'create_region')

    def test_the_edit_page_shows_the_region_name_and_suggestions(self):
        member = Member.objects.create(church=self.ack, region=self.kasarani, full_name='Mary Wanjiku',
                                       phone_number='0712345678', reference_number='ACK-01')
        html = self.client.get(reverse('admin:members_member_change', args=[member.pk])).content.decode()
        self.assertIn('value="Kasarani"', html)
        self.assertIn('<datalist id="id_region-options">', html)
        self.assertIn('js/admin_region_input.js', html)

    def test_changing_the_area_when_editing(self):
        member = Member.objects.create(church=self.ack, region=self.kasarani, full_name='Mary Wanjiku',
                                       phone_number='0712345678', reference_number='ACK-01')
        Region.objects.create(church=self.ack, name='Embakasi')
        response = self.client.post(reverse('admin:members_member_change', args=[member.pk]), {
            'church': self.ack.pk, 'region': 'EMBAKASI', 'full_name': 'Mary Wanjiku', 'phone_number': '0712345678',
        })
        self.assertEqual(response.status_code, 302)
        member.refresh_from_db()
        self.assertEqual(member.region.name, 'Embakasi')

    def test_visitors_use_the_same_typed_area(self):
        response = self.client.post(reverse('admin:visitors_visitor_add'), {
            'church': self.ack.pk, 'region': 'KASARANI', 'full_name': 'John Otieno', 'phone_number': '0799999999',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Visitor.objects.get().region, self.kasarani)


class NewAreaNameTests(TestCase):
    def setUp(self):
        self.church = Church.objects.create(name='Grace Chapel', code='GRC')

    def test_names_typed_all_in_lower_or_upper_case_are_tidied(self):
        self.assertEqual(resolve_region(self.church, 'sikhendu', create=True).name, 'Sikhendu')
        self.assertEqual(resolve_region(self.church, 'MSHARAGE WEST', create=True).name, 'Msharage West')

    def test_names_with_mixed_capitals_are_kept_as_typed(self):
        self.assertEqual(resolve_region(self.church, 'Kanduyi eastEnd', create=True).name, 'Kanduyi eastEnd')

    def test_an_existing_area_is_never_duplicated(self):
        first = resolve_region(self.church, 'Sikhendu', create=True)
        self.assertEqual(resolve_region(self.church, ' SIKHENDU ', create=True), first)
        self.assertEqual(Region.objects.count(), 1)
