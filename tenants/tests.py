from django.test import TestCase
from django.contrib.auth import get_user_model
from tenants.models import Church
from members.models import Member

User = get_user_model()


class TenantIsolationTests(TestCase):
    def setUp(self):
        self.church_a = Church.objects.create(name="Church A", code="CHA")
        self.church_b = Church.objects.create(name="Church B", code="CHB")

        self.user_a = User.objects.create_user(username="admin_a", password="testpass123", church=self.church_a)
        self.user_b = User.objects.create_user(username="admin_b", password="testpass123", church=self.church_b)

        self.member_a = Member.objects.create(
            church=self.church_a, full_name="Member A", phone_number="0700000001", reference_number="CHA-01"
        )
        self.member_b = Member.objects.create(
            church=self.church_b, full_name="Member B", phone_number="0700000002", reference_number="CHB-01"
        )

    def test_user_a_only_sees_church_a_members(self):
        visible = Member.objects.for_user(self.user_a)
        self.assertIn(self.member_a, visible)
        self.assertNotIn(self.member_b, visible)

    def test_user_b_only_sees_church_b_members(self):
        visible = Member.objects.for_user(self.user_b)
        self.assertIn(self.member_b, visible)
        self.assertNotIn(self.member_a, visible)

    def test_tesmus_staff_sees_all_members(self):
        tesmus_user = User.objects.create_user(username="tesmus_test", password="testpass123", is_tesmus_staff=True)
        visible = Member.objects.for_user(tesmus_user)
        self.assertIn(self.member_a, visible)
        self.assertIn(self.member_b, visible)
