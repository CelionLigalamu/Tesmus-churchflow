from django.db import transaction
from tenants.models import Church
from .models import DEFAULT_MINISTRY_ROLES, MinistryRole


# The default role whose holders are texted their region's statistics. Each
# church can choose a different role, or none, on the Regions page.
DEFAULT_REGION_PASTOR_ROLE = 'Pastor'


def ensure_default_ministry_roles(church):
    existing = set(
        MinistryRole.objects.filter(church=church).values_list('name', flat=True)
    )
    created = set()
    for index, name in enumerate(DEFAULT_MINISTRY_ROLES, start=1):
        if name not in existing:
            MinistryRole.objects.create(church=church, name=name, sort_order=index * 10)
            created.add(name)
    # Only when the default roles are first created, so a church that later
    # clears this choice keeps it cleared.
    if DEFAULT_REGION_PASTOR_ROLE in created and not church.region_pastor_role_id:
        church.region_pastor_role = MinistryRole.objects.get(church=church, name=DEFAULT_REGION_PASTOR_ROLE)
        church.save(update_fields=['region_pastor_role'])
    return MinistryRole.objects.filter(church=church).order_by('sort_order', 'name')


def generate_reference_number(church_id):
    with transaction.atomic():
        church = Church.objects.select_for_update().get(id=church_id)
        church.last_member_sequence += 1
        church.save(update_fields=['last_member_sequence'])
        seq = church.last_member_sequence
        return f"{church.code}-{str(seq).zfill(2)}"
