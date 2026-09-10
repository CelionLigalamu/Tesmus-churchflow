from django.test import TestCase

from accounts.models import User
from .models import Member, MinistryRole
from tenants.models import Church


class MinistryRoleWorkflowTests(TestCase):
    def setUp(self):
        self.church = Church.objects.create(name='Role Church', code='ROLE')
        self.user = User.objects.create_user(username='role_admin', password='testpass123', church=self.church, scope_type='church')

    def test_member_can_have_multiple_roles_and_be_edited(self):
        self.client.force_login(self.user)
        role_a = MinistryRole.objects.create(church=self.church, name='Choir')
        role_b = MinistryRole.objects.create(church=self.church, name='Youth Leaders')
        member = Member.objects.create(church=self.church, full_name='Grace', phone_number='0700000010', reference_number='ROLE-01')
        member.ministry_roles.set([role_a, role_b])
        response = self.client.post(f'/members/{member.pk}/edit/', {'full_name': 'Grace Updated', 'phone_number': '0700000011', 'ministry_roles': [role_a.pk, role_b.pk]})
        self.assertEqual(response.status_code, 302)
        member.refresh_from_db()
        self.assertEqual(set(member.ministry_roles.values_list('pk', flat=True)), {role_a.pk, role_b.pk})

    def test_church_admin_can_create_role(self):
        self.client.force_login(self.user)
        response = self.client.post('/members/ministry-roles/new/', {'name': 'Media Team'})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(MinistryRole.objects.filter(church=self.church, name='Media Team').exists())

    def test_default_roles_are_in_requested_order(self):
        from .services import ensure_default_ministry_roles
        names = list(ensure_default_ministry_roles(self.church).values_list('name', flat=True))
        self.assertEqual(names[:7], ['Bishop', 'Pastor', 'Elder', 'Deacon', 'Deaconess', 'Ushers', 'Instrumentalists'])
