from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from attendance.models import Attendance
from members.models import Member
from tenants.models import Church
from .models import Service
from .services import finalize_service


class FinalizeServiceTests(TestCase):
    def test_present_and_absent_members_receive_only_their_matching_message(self):
        church = Church.objects.create(name='Test Church', code='TEST')
        present_member = Member.objects.create(
            church=church,
            full_name='Present Member',
            phone_number='0700000001',
            reference_number='TEST-001',
        )
        absent_member = Member.objects.create(
            church=church,
            full_name='Absent Member',
            phone_number='0700000002',
            reference_number='TEST-002',
        )
        service = Service.objects.create(
            church=church,
            name='Sunday Service',
            date=timezone.localdate(),
            status='closed',
        )
        Attendance.objects.create(
            church=church,
            service=service,
            member=present_member,
            method='qr',
            result='present',
        )

        with patch('services.services.send_message') as send_message:
            finalize_service(service)

        self.assertTrue(
            Attendance.objects.filter(
                service=service,
                member=absent_member,
                result='absent',
            ).exists()
        )
        dedupe_keys = {
            call.kwargs['dedupe_key']
            for call in send_message.call_args_list
        }
        self.assertEqual(
            dedupe_keys,
            {
                f'attendance:{service.pk}:{present_member.pk}:present',
                f'attendance:{service.pk}:{absent_member.pk}:absent',
            },
        )
        self.assertEqual(send_message.call_count, 2)
