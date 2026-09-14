from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from attendance.models import Attendance
from members.models import Member
from services.models import Service
from tenants.models import Church, Region
from tenants.services import PlaceError, merge_regions
from visitors.models import Visitor

User = get_user_model()


class MergeRegionsTestBase(TestCase):
    def setUp(self):
        self.church = Church.objects.create(name='Grace Chapel', code='GRC')
        self.kept = Region.objects.create(church=self.church, name='Sikhendu')
        self.typo = Region.objects.create(church=self.church, name='Sikendu')
        self.admin = User.objects.create_user('admin', password='x', church=self.church, scope_type='church')

    def member(self, name, region, number):
        return Member.objects.create(church=self.church, region=region, full_name=name,
                                     phone_number=f'07110000{number:02d}', reference_number=f'GRC-{number:02d}')


class MergeRegionsServiceTests(MergeRegionsTestBase):
    def test_everything_moves_into_the_kept_region_and_the_typo_is_removed(self):
        mary = self.member('Mary Wanjiku', self.typo, 1)
        peter = self.member('Peter Kamau', self.kept, 2)
        visitor = Visitor.objects.create(church=self.church, region=self.typo, full_name='John Otieno', phone_number='0799000001')
        service = Service.objects.create(church=self.church, region=self.typo, name='Sunday Service', date=timezone.localdate())
        attendance = Attendance.objects.create(church=self.church, service=service, member=mary, method='qr', result='present')
        pastor_user = User.objects.create_user('pastor', password='x', church=self.church, scope_type='region', scope_region=self.typo)
        self.typo.pastors.add(peter)
        self.kept.pastors.add(mary)

        self.assertEqual(merge_regions(self.typo, self.kept), 1)

        self.assertFalse(Region.objects.filter(pk=self.typo.pk).exists())
        for record in (mary, visitor, service, attendance, pastor_user):
            record.refresh_from_db()
        self.assertEqual(mary.region, self.kept)
        self.assertEqual(visitor.region, self.kept)
        self.assertEqual(service.region, self.kept)
        self.assertEqual(attendance.region, self.kept)
        self.assertEqual(pastor_user.scope_region, self.kept)
        self.assertEqual(set(self.kept.pastors.all()), {mary, peter})
        self.assertTrue(Member.objects.filter(pk=peter.pk).exists())

    def test_a_region_cannot_be_merged_into_itself_or_another_church(self):
        with self.assertRaises(PlaceError):
            merge_regions(self.typo, self.typo)
        other = Region.objects.create(church=Church.objects.create(name='Hope Centre', code='HOP'), name='Sikhendu')
        with self.assertRaises(PlaceError):
            merge_regions(self.typo, other)
        self.assertTrue(Region.objects.filter(pk=self.typo.pk).exists())


class MergeRegionsPageTests(MergeRegionsTestBase):
    def setUp(self):
        super().setUp()
        self.client.login(username='admin', password='x')
        self.url = reverse('region_merge', args=[self.typo.pk])

    def test_the_regions_page_offers_merge(self):
        self.assertContains(self.client.get(reverse('region_list')), self.url)

    def test_the_page_shows_what_will_move_and_suggests_the_similar_region(self):
        self.member('Mary Wanjiku', self.typo, 1)
        response = self.client.get(self.url)
        self.assertContains(response, 'What will move')
        self.assertContains(response, '<li><span>Members</span><strong>1</strong></li>', html=True)
        self.assertContains(response, '"Sikhendu" looks like the same area')
        self.assertContains(response, f'<option value="{self.kept.pk}" selected>Sikhendu</option>', html=True)

    def test_nothing_is_merged_without_ticking_the_confirmation(self):
        response = self.client.post(self.url, {'target': self.kept.pk})
        self.assertContains(response, 'Tick the box to confirm the merge.')
        self.assertTrue(Region.objects.filter(pk=self.typo.pk).exists())

    def test_merging_moves_members_and_reports_it(self):
        mary = self.member('Mary Wanjiku', self.typo, 1)
        response = self.client.post(self.url, {'target': self.kept.pk, 'confirm': 'on'})
        self.assertRedirects(response, reverse('region_list'), fetch_redirect_response=False)
        mary.refresh_from_db()
        self.assertEqual(mary.region, self.kept)
        self.assertIn('"Sikendu" was merged into "Sikhendu". 1 member(s) moved.', [str(m) for m in get_messages(response.wsgi_request)])

    def test_another_churchs_region_cannot_be_chosen(self):
        other = Region.objects.create(church=Church.objects.create(name='Hope Centre', code='HOP'), name='Sikhendu')
        response = self.client.post(self.url, {'target': other.pk, 'confirm': 'on'})
        self.assertContains(response, 'Choose one of your regions.')
        self.assertTrue(Region.objects.filter(pk=self.typo.pk).exists())

    def test_only_church_wide_administrators_can_merge(self):
        User.objects.create_user('pastor', password='x', church=self.church, scope_type='region', scope_region=self.kept)
        self.client.login(username='pastor', password='x')
        self.client.post(self.url, {'target': self.kept.pk, 'confirm': 'on'})
        self.assertTrue(Region.objects.filter(pk=self.typo.pk).exists())


class MergeRegionsAdminActionTests(MergeRegionsTestBase):
    def setUp(self):
        super().setUp()
        User.objects.create_superuser('tesmus', 'admin@example.com', 'x')
        self.client.login(username='tesmus', password='x')
        self.changelist = reverse('admin:tenants_region_changelist')

    def test_admin_can_merge_selected_regions_after_choosing_the_one_to_keep(self):
        mary = self.member('Mary Wanjiku', self.typo, 1)
        selection = {'action': 'merge_selected_regions', '_selected_action': [self.kept.pk, self.typo.pk]}
        confirm_page = self.client.post(self.changelist, selection)
        self.assertContains(confirm_page, 'Keep this region')

        response = self.client.post(self.changelist, {**selection, 'target': self.kept.pk})
        self.assertEqual(response.status_code, 302)
        mary.refresh_from_db()
        self.assertEqual(mary.region, self.kept)
        self.assertFalse(Region.objects.filter(pk=self.typo.pk).exists())

    def test_regions_of_different_churches_are_refused(self):
        other = Region.objects.create(church=Church.objects.create(name='Hope Centre', code='HOP'), name='Kanduyi')
        response = self.client.post(self.changelist, {'action': 'merge_selected_regions', '_selected_action': [self.kept.pk, other.pk]}, follow=True)
        self.assertContains(response, 'Only regions of the same church can be merged.')
        self.assertEqual(Region.objects.count(), 3)
