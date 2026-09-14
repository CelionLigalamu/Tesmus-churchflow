from datetime import timedelta
from itertools import count
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from analytics.services import dashboard_summary
from attendance.models import Attendance
from members.models import Member, MinistryRole
from members.services import ensure_default_ministry_roles
from messaging.models import SMSMessage, SMSTemplate
from messaging.services import ensure_system_templates
from services.models import Service
from services.services import finalize_service, send_region_summaries
from tenants.admin import RegionAdminForm
from tenants.models import Church, Region

User = get_user_model()
_numbers = count(1)


class RegionTestBase(TestCase):
    def setUp(self):
        # Closing a service texts members; never reach the real SMS provider.
        provider = mock.patch('messaging.services.send_sms', return_value={'ok': 1})
        provider.start()
        self.addCleanup(provider.stop)
        self.church = Church.objects.create(name='Grace Chapel', code='GRC')
        self.sikhendu = Region.objects.create(church=self.church, name='Sikhendu')
        self.msharage = Region.objects.create(church=self.church, name='Msharage')
        self.admin = User.objects.create_user('admin', password='x', church=self.church, scope_type='church')

    def member(self, name, region=None, church=None):
        number = next(_numbers)
        church = church or self.church
        return Member.objects.create(
            church=church, region=region, full_name=name,
            phone_number=f'07{number:08d}', reference_number=f'{church.code}-{number:03d}',
        )

    def service(self):
        return Service.objects.create(church=self.church, name='Sunday Service', date=timezone.localdate(), status='closed')

    def check_in(self, service, member):
        return Attendance.objects.create(church=self.church, service=service, member=member, method='qr')

    def summaries(self):
        return SMSMessage.objects.filter(dedupe_key__startswith='region-summary:')


class PastorSummaryTests(RegionTestBase):
    def setUp(self):
        super().setUp()
        self.pastor_john = self.member('Pastor John')
        self.pastor_ruth = self.member('Pastor Ruth')
        self.sikhendu.pastors.add(self.pastor_john)
        self.msharage.pastors.add(self.pastor_ruth)

        self.service_obj = self.service()
        for name in ('Mary Wanjiku', 'Peter Kamau'):
            self.check_in(self.service_obj, self.member(name, self.sikhendu))
        self.member('Grace Achieng', self.sikhendu)
        self.check_in(self.service_obj, self.member('Samuel Otieno', self.msharage))
        self.member('Ruth Chebet', self.msharage)

    def close_service(self):
        with mock.patch('messaging.services.send_sms', return_value={'ok': 1}), \
                self.captureOnCommitCallbacks(execute=True):
            finalize_service(self.service_obj)

    def test_each_pastor_gets_only_their_regions_statistics_when_a_service_closes(self):
        self.close_service()
        self.assertEqual(self.summaries().count(), 2)

        john = self.summaries().get(recipient_phone=self.pastor_john.phone_number)
        self.assertIn('Mchungaji Pastor John', john.body)
        self.assertIn('Sikhendu', john.body)
        self.assertIn('waliohudhuria 2 kati ya 3 (67%), hawakuhudhuria 1', john.body)
        self.assertNotIn('Msharage', john.body)

        ruth = self.summaries().get(recipient_phone=self.pastor_ruth.phone_number)
        self.assertIn('waliohudhuria 1 kati ya 2 (50%), hawakuhudhuria 1', ruth.body)

    def test_the_message_contains_statistics_only_never_member_names(self):
        self.close_service()
        body = self.summaries().get(recipient_phone=self.pastor_john.phone_number).body
        for name in ('Mary Wanjiku', 'Peter Kamau', 'Grace Achieng'):
            self.assertNotIn(name, body)

    def test_pastors_are_never_texted_twice_for_the_same_service(self):
        self.close_service()
        with mock.patch('messaging.services.send_sms', return_value={'ok': 1}) as provider:
            send_region_summaries(self.service_obj)
        provider.assert_not_called()
        self.assertEqual(self.summaries().count(), 2)

    def test_regions_without_pastors_send_nothing(self):
        self.sikhendu.pastors.clear()
        self.close_service()
        self.assertEqual(list(self.summaries().values_list('recipient_phone', flat=True)), [self.pastor_ruth.phone_number])

    def test_a_paused_template_sends_nothing(self):
        ensure_system_templates(self.church)
        SMSTemplate.objects.filter(church=self.church, name='region_attendance_summary').update(is_active=False)
        self.close_service()
        self.assertFalse(self.summaries().exists())

    def test_a_broken_template_never_stops_the_service_closing(self):
        ensure_system_templates(self.church)
        SMSTemplate.objects.filter(church=self.church, name='region_attendance_summary').update(body='{% if %}')
        with self.assertLogs('services.services', level='ERROR'):
            self.close_service()
        self.service_obj.refresh_from_db()
        self.assertEqual(self.service_obj.status, 'finalized')
        self.assertFalse(self.summaries().exists())

    def test_the_template_is_listed_for_every_church_to_edit(self):
        names = [template.name for template in ensure_system_templates(self.church)]
        self.assertIn('region_attendance_summary', names)


class RegionStatisticsTests(RegionTestBase):
    def test_past_statistics_stay_the_same_after_a_member_moves(self):
        member = self.member('Mary Wanjiku', self.sikhendu)
        attendance = self.check_in(self.service(), member)
        member.region = self.msharage
        member.save()
        attendance.refresh_from_db()
        self.assertEqual(attendance.region, self.sikhendu)

    def test_a_member_given_a_region_before_the_service_closes_is_counted(self):
        member = self.member('Mary Wanjiku')
        service = self.service()
        self.check_in(service, member)
        member.region = self.sikhendu
        member.save()
        finalize_service(service)
        self.assertEqual(Attendance.objects.get(service=service, member=member).region, self.sikhendu)

    def test_dashboard_shows_a_regions_statistics(self):
        service = self.service()
        self.check_in(service, self.member('Mary Wanjiku', self.sikhendu))
        self.member('Peter Kamau', self.sikhendu)
        self.check_in(service, self.member('Samuel Otieno', self.msharage))
        finalize_service(service)

        today = timezone.localdate()
        summary = dashboard_summary(self.church, start_date=today, end_date=today, region=self.sikhendu)
        self.assertEqual((summary['present'], summary['absent'], summary['attendance_rate']), (1, 1, 50.0))

        self.client.login(username='admin', password='x')
        response = self.client.get(reverse('home'), {'region': self.sikhendu.pk, 'range': '7d'})
        self.assertEqual(response.status_code, 200)


class RegionPageTests(RegionTestBase):
    def setUp(self):
        super().setUp()
        self.client.login(username='admin', password='x')
        self.other_church = Church.objects.create(name='Hope Centre', code='HOP')
        self.outsider = self.member('Outside Pastor', church=self.other_church)

    def test_list_shows_regions_and_their_pastors(self):
        self.sikhendu.pastors.add(self.member('Pastor John'))
        html = self.client.get(reverse('region_list')).content.decode()
        self.assertIn('Sikhendu', html)
        self.assertIn('Pastor John', html)
        self.assertIn('No pastor yet', html)

    def test_add_a_region_with_pastors(self):
        pastor = self.member('Pastor John')
        response = self.client.post(reverse('region_create'), {'name': '  Kanduyi ', 'pastors': [pastor.pk]})
        self.assertRedirects(response, reverse('region_list'))
        region = Region.objects.get(church=self.church, name='Kanduyi')
        self.assertEqual(list(region.pastors.all()), [pastor])

    def test_change_a_regions_pastors(self):
        old, new = self.member('Pastor John'), self.member('Pastor Ruth')
        self.sikhendu.pastors.add(old)
        self.client.post(reverse('region_edit', args=[self.sikhendu.pk]), {'name': 'Sikhendu', 'pastors': [new.pk]})
        self.assertEqual(list(self.sikhendu.pastors.all()), [new])

    def test_duplicate_names_are_refused_whatever_the_capitals(self):
        response = self.client.post(reverse('region_create'), {'name': 'sikhendu'})
        self.assertContains(response, 'A region with this name already exists.')

    def test_another_churchs_member_cannot_be_made_a_pastor(self):
        self.assertNotContains(self.client.get(reverse('region_create')), 'Outside Pastor')
        response = self.client.post(reverse('region_edit', args=[self.sikhendu.pk]), {'name': 'Sikhendu', 'pastors': [self.outsider.pk]})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.sikhendu.pastors.exists())

    def test_another_churchs_region_is_not_found(self):
        foreign = Region.objects.create(church=self.other_church, name='Kanduyi')
        self.assertEqual(self.client.get(reverse('region_edit', args=[foreign.pk])).status_code, 404)

    def test_only_church_wide_administrators_manage_regions(self):
        User.objects.create_user('pastor', password='x', church=self.church, scope_type='region', scope_region=self.sikhendu)
        self.client.login(username='pastor', password='x')
        self.assertRedirects(self.client.get(reverse('region_list')), reverse('home'), fetch_redirect_response=False)
        self.assertNotIn(reverse('region_list'), self.client.get(reverse('member_list')).content.decode())

    def test_django_admin_refuses_a_pastor_from_another_church(self):
        form = RegionAdminForm(data={'church': self.church.pk, 'name': 'Kanduyi', 'pastors': [self.outsider.pk]})
        self.assertFalse(form.is_valid())
        self.assertIn('Pastors must be members of Grace Chapel', str(form.errors))


class PastorRoleTests(RegionTestBase):
    def setUp(self):
        super().setUp()
        self.role = MinistryRole.objects.create(church=self.church, name='Pastor')
        self.church.region_pastor_role = self.role
        self.church.save()
        self.mary = self.member('Mary Wanjiku', self.sikhendu)
        self.mary.ministry_roles.add(self.role)
        self.service_obj = self.service()
        self.check_in(self.service_obj, self.member('Peter Kamau', self.sikhendu))
        self.member('Samuel Otieno', self.msharage)

    def close_service(self):
        with self.captureOnCommitCallbacks(execute=True):
            finalize_service(self.service_obj)

    def test_members_with_the_pastor_role_are_texted_their_own_region(self):
        self.close_service()
        self.assertEqual(list(self.summaries().values_list('recipient_phone', flat=True)), [self.mary.phone_number])
        body = self.summaries().get().body
        self.assertIn('Sikhendu', body)
        self.assertIn('waliohudhuria 1 kati ya 2 (50%)', body)

    def test_a_pastor_picked_and_holding_the_role_is_texted_once(self):
        self.sikhendu.pastors.add(self.mary)
        self.close_service()
        self.assertEqual(self.summaries().count(), 1)

    def test_with_no_role_chosen_only_picked_pastors_are_texted(self):
        self.church.region_pastor_role = None
        self.church.save()
        self.close_service()
        self.assertFalse(self.summaries().exists())

    def test_regions_page_shows_pastors_found_by_role(self):
        self.client.login(username='admin', password='x')
        html = self.client.get(reverse('region_list')).content.decode()
        self.assertIn('Mary Wanjiku', html)
        self.assertIn('(Pastor)', html)
        self.assertNotIn('No pastor yet</span></td>', html.split('Msharage')[0])

    def test_church_chooses_the_role_on_the_regions_page(self):
        self.client.login(username='admin', password='x')
        self.client.post(reverse('region_pastor_role'), {'region_pastor_role': ''})
        self.church.refresh_from_db()
        self.assertIsNone(self.church.region_pastor_role)

        other_church = Church.objects.create(name='Hope Centre', code='HOP')
        foreign_role = MinistryRole.objects.create(church=other_church, name='Pastor')
        self.client.post(reverse('region_pastor_role'), {'region_pastor_role': foreign_role.pk})
        self.church.refresh_from_db()
        self.assertIsNone(self.church.region_pastor_role)

        self.client.post(reverse('region_pastor_role'), {'region_pastor_role': self.role.pk})
        self.church.refresh_from_db()
        self.assertEqual(self.church.region_pastor_role, self.role)

    def test_a_new_church_starts_with_its_pastor_role_and_can_clear_it(self):
        church = Church.objects.create(name='New Life', code='NLC')
        ensure_default_ministry_roles(church)
        church.refresh_from_db()
        self.assertEqual(church.region_pastor_role.name, 'Pastor')

        church.region_pastor_role = None
        church.save()
        ensure_default_ministry_roles(church)
        church.refresh_from_db()
        self.assertIsNone(church.region_pastor_role)


class TextRegionPastorsButtonTests(RegionTestBase):
    def setUp(self):
        super().setUp()
        self.sikhendu.pastors.add(self.member('Pastor John'))
        self.service_obj = Service.objects.create(
            church=self.church, name='Sunday Service', date=timezone.localdate(), status='finalized',
        )
        Attendance.objects.create(church=self.church, service=self.service_obj,
                                  member=self.member('Mary Wanjiku', self.sikhendu), method='qr', result='present')

    def press(self, username='admin'):
        self.client.login(username=username, password='x')
        response = self.client.post(reverse('service_send_region_summaries', args=[self.service_obj.pk]))
        return response, [str(note) for note in get_messages(response.wsgi_request)]

    def test_pastors_can_be_texted_for_a_service_that_already_closed(self):
        response, notes = self.press()
        self.assertRedirects(response, reverse('service_detail', args=[self.service_obj.pk]), fetch_redirect_response=False)
        self.assertEqual(self.summaries().count(), 1)
        self.assertIn('Sent to 1 pastor.', notes)

    def test_pressing_again_never_texts_twice(self):
        self.press()
        _, notes = self.press()
        self.assertEqual(self.summaries().count(), 1)
        self.assertTrue(any('already texted' in note for note in notes))

    def test_only_church_wide_administrators_can_text_pastors(self):
        User.objects.create_user('pastor_user', password='x', church=self.church,
                                 scope_type='region', scope_region=self.sikhendu)
        self.press('pastor_user')
        self.assertFalse(self.summaries().exists())

    def test_a_service_that_has_not_closed_is_refused(self):
        self.service_obj.status = 'upcoming'
        self.service_obj.date = timezone.localdate() + timedelta(days=3)
        self.service_obj.save()
        _, notes = self.press()
        self.assertFalse(self.summaries().exists())
        self.assertTrue(any('once the service has closed' in note for note in notes))

    def test_the_button_shows_on_a_closed_service(self):
        self.client.login(username='admin', password='x')
        self.assertContains(self.client.get(reverse('service_detail', args=[self.service_obj.pk])), 'Text region pastors')
