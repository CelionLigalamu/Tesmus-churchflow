from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from attendance.models import Attendance
from members.models import Member
from messaging.models import SMSMessage, SMSTemplate
from messaging.services import get_system_template
from notifications.models import Notification
from pastoral.absence import missed_in_a_row
from pastoral.models import PastoralFollowUp
from services.models import Service
from services.services import finalize_service
from tenants.models import Church, Region

User = get_user_model()


class AbsenceTestBase(TestCase):
    """A church with a Kasarani pastor (John) and a member (Mary) who lives there."""

    def setUp(self):
        send_sms = mock.patch('messaging.services.send_sms', return_value='ATXid_ok')
        self.send_sms = send_sms.start()
        self.addCleanup(send_sms.stop)
        self.church = Church.objects.create(name='Grace Chapel', code='GRC')
        self.admin_user = User.objects.create_user('admin', password='x', church=self.church, scope_type='church')
        self.kasarani = Region.objects.create(church=self.church, name='Kasarani')
        self.pastor = Member.objects.create(church=self.church, region=self.kasarani, full_name='John Otieno',
                                            phone_number='0700000001', reference_number='GRC-01')
        self.kasarani.pastors.add(self.pastor)
        self.mary = Member.objects.create(church=self.church, region=self.kasarani, full_name='Mary Wanjiku',
                                          phone_number='0711000001', reference_number='GRC-02')
        self.services_held = 0

    def hold_service(self, present=()):
        """Close a service that the pastor and any `present` members attended."""
        self.services_held += 1
        service = Service.objects.create(church=self.church, name='Sunday Service',
                                         date=timezone.localdate() - timedelta(days=100 - self.services_held))
        for member in (self.pastor, *present):
            Attendance.objects.create(church=self.church, service=service, member=member, method='manual')
        with self.captureOnCommitCallbacks(execute=True):
            finalize_service(service)
        return service

    def alerts(self):
        return SMSMessage.objects.filter(audience_label__startswith='Follow-up alert')


class AbsenceDetectionTests(AbsenceTestBase):
    def test_a_member_who_misses_three_services_in_a_row_is_flagged_and_their_pastor_texted(self):
        self.hold_service()
        self.hold_service()
        self.assertFalse(PastoralFollowUp.objects.exists())
        latest = self.hold_service()

        followup = PastoralFollowUp.objects.get()
        self.assertEqual((followup.member, followup.reason, followup.missed_count, followup.status),
                         (self.mary, PastoralFollowUp.MISSED_SERVICES, 3, 'pending'))
        self.assertEqual(followup.trigger_service, latest)
        self.assertEqual(list(followup.pastors.all()), [self.pastor])
        self.assertIn('Missed the last 3 services in a row', followup.notes)
        alert = self.alerts().get()
        self.assertEqual((alert.recipient_phone, alert.audience_label, alert.status),
                         ('0700000001', 'Follow-up alert - GRC-02', 'sent'))
        for detail in ('John Otieno', 'Mary Wanjiku', 'GRC-02', '0711000001', 'Kasarani', 'amekosa ibada 3'):
            self.assertIn(detail, alert.body)

    def test_further_absences_never_text_the_pastor_again(self):
        for _ in range(6):
            self.hold_service()
        self.assertEqual(PastoralFollowUp.objects.count(), 1)
        self.assertEqual(self.alerts().count(), 1)

    def test_only_missing_in_a_row_counts(self):
        self.hold_service()
        self.hold_service()
        self.hold_service(present=[self.mary])
        self.hold_service()
        self.hold_service()
        self.assertEqual(missed_in_a_row(self.mary), 2)
        self.assertFalse(PastoralFollowUp.objects.exists())

    def test_coming_back_closes_the_follow_up_as_returned(self):
        for _ in range(3):
            self.hold_service()
        self.hold_service(present=[self.mary])
        followup = PastoralFollowUp.objects.get()
        self.assertEqual(followup.status, 'returned')
        self.assertIsNotNone(followup.closed_at)
        self.assertIn('Came back to Sunday Service', followup.notes)

        for _ in range(3):
            self.hold_service()
        self.assertEqual(PastoralFollowUp.objects.filter(status='pending').count(), 1)
        self.assertEqual(self.alerts().count(), 2)

    def test_a_member_with_no_pastor_is_flagged_for_the_church_admin(self):
        ruth = Member.objects.create(church=self.church, full_name='Ruth Chebet', phone_number='0722000001',
                                     reference_number='GRC-03')
        for _ in range(3):
            self.hold_service(present=[self.mary])
        followup = PastoralFollowUp.objects.get(member=ruth)
        self.assertFalse(followup.pastors.exists())
        self.assertIn('no region', followup.notes)
        self.assertFalse(self.alerts().exists())
        notification = Notification.objects.get(recipient=self.admin_user, kind=Notification.FOLLOWUP_UNASSIGNED)
        self.assertIn('Ruth Chebet', notification.detail)
        self.assertEqual(notification.target_url, reverse('pastoral_followup_list') + '?status=needs_pastor')

    def test_each_church_chooses_how_many_missed_services_count(self):
        self.church.absence_alert_after = 2
        self.church.save()
        self.hold_service()
        self.hold_service()
        self.assertEqual(PastoralFollowUp.objects.get().missed_count, 2)

    def test_alerts_can_be_turned_off(self):
        self.church.absence_alert_after = 0
        self.church.save()
        for _ in range(4):
            self.hold_service()
        self.assertFalse(PastoralFollowUp.objects.exists())

    def test_switching_the_text_off_still_opens_the_follow_up(self):
        get_system_template(self.church, 'pastor_followup_alert')
        SMSTemplate.objects.filter(church=self.church, name='pastor_followup_alert').update(is_active=False)
        for _ in range(3):
            self.hold_service()
        self.assertTrue(PastoralFollowUp.objects.filter(member=self.mary).exists())
        self.assertFalse(self.alerts().exists())


class PastoralPagesTests(AbsenceTestBase):
    def setUp(self):
        super().setUp()
        for _ in range(3):
            self.hold_service()
        self.followup = PastoralFollowUp.objects.get()

    def test_the_list_shows_why_and_which_pastor_follows_up(self):
        self.client.login(username='admin', password='x')
        page = self.client.get(reverse('pastoral_followup_list'))
        for text in ('Mary Wanjiku', 'Missed 3 services in a row', 'John Otieno', 'Members who miss 3 services in a row'):
            self.assertContains(page, text)
        self.assertContains(page, 'name="absence_alert_after"')

    def test_region_leaders_only_see_their_own_region(self):
        embakasi = Region.objects.create(church=self.church, name='Embakasi')
        User.objects.create_user('leader', password='x', church=self.church, scope_type='region', scope_region=embakasi)
        self.client.login(username='leader', password='x')
        page = self.client.get(reverse('pastoral_followup_list'))
        self.assertNotContains(page, 'Mary Wanjiku')
        self.assertNotContains(page, 'name="absence_alert_after"')
        self.assertEqual(self.client.get(reverse('pastoral_followup_detail', args=[self.followup.pk])).status_code, 404)

    def test_progress_is_recorded_with_dated_notes(self):
        self.client.login(username='admin', password='x')
        self.client.post(reverse('pastoral_followup_update', args=[self.followup.pk]),
                         {'status': 'in_progress', 'note': 'Called her, she has been unwell.'})
        self.followup.refresh_from_db()
        self.assertEqual(self.followup.status, 'in_progress')
        self.assertIn('Status changed from Pending to In Progress.', self.followup.notes)
        self.assertIn('admin: Called her, she has been unwell.', self.followup.notes)
        self.assertIn('Missed the last 3 services', self.followup.notes)

        self.client.post(reverse('pastoral_followup_update', args=[self.followup.pk]), {'status': 'completed', 'note': ''})
        self.followup.refresh_from_db()
        self.assertEqual(self.followup.status, 'completed')
        self.assertIsNotNone(self.followup.closed_at)

    def test_the_church_admin_chooses_the_number(self):
        self.client.login(username='admin', password='x')
        self.client.post(reverse('pastoral_absence_setting'), {'absence_alert_after': 4})
        self.church.refresh_from_db()
        self.assertEqual(self.church.absence_alert_after, 4)
        self.client.post(reverse('pastoral_absence_setting'), {'absence_alert_after': 99})
        self.church.refresh_from_db()
        self.assertEqual(self.church.absence_alert_after, 4)

    def test_region_leaders_cannot_change_the_number(self):
        User.objects.create_user('leader', password='x', church=self.church, scope_type='region', scope_region=self.kasarani)
        self.client.login(username='leader', password='x')
        self.assertContains(self.client.get(reverse('pastoral_followup_list')), 'Mary Wanjiku')
        self.client.post(reverse('pastoral_absence_setting'), {'absence_alert_after': 1})
        self.church.refresh_from_db()
        self.assertEqual(self.church.absence_alert_after, 3)

    def test_the_pastor_alert_text_is_editable_like_the_others(self):
        self.client.login(username='admin', password='x')
        self.assertContains(self.client.get(reverse('sms_template_list')), 'Pastor follow-up alert')
