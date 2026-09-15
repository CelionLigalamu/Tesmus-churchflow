from django.db import transaction
from django.db.models.functions import Length
from tenants.models import Church
from .models import DEFAULT_MINISTRY_ROLES, MinistryRole


# The default role whose holders are texted their region's statistics. Each
# church can choose a different role, or none, on the Regions page.
DEFAULT_REGION_PASTOR_ROLE = 'Pastor'
# The default role that marks a church's ushers; each church can choose another.
DEFAULT_USHER_ROLE = 'Ushers'


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
    # clears these choices keeps them cleared.
    chosen = []
    if DEFAULT_REGION_PASTOR_ROLE in created and not church.region_pastor_role_id:
        church.region_pastor_role = MinistryRole.objects.get(church=church, name=DEFAULT_REGION_PASTOR_ROLE)
        chosen.append('region_pastor_role')
    if DEFAULT_USHER_ROLE in created and not church.usher_role_id:
        church.usher_role = MinistryRole.objects.get(church=church, name=DEFAULT_USHER_ROLE)
        chosen.append('usher_role')
    if chosen:
        church.save(update_fields=chosen)
    return MinistryRole.objects.filter(church=church).order_by('sort_order', 'name')


def in_reference_number_order(members):
    """Order members by reference number as people count: PLCM-2, PLCM-10, PLCM-100.

    Plain text sorting would put PLCM-100 before PLCM-11. Within a church every
    number shares the same prefix, so shorter numbers come first and equal
    lengths sort alphabetically. Church name first keeps churches apart for
    Tesmus staff, who see every church.
    """
    return members.order_by('church__name', Length('reference_number'), 'reference_number')


def generate_reference_number(church_id):
    with transaction.atomic():
        church = Church.objects.select_for_update().get(id=church_id)
        church.last_member_sequence += 1
        church.save(update_fields=['last_member_sequence'])
        seq = church.last_member_sequence
        return f"{church.code}-{str(seq).zfill(2)}"
