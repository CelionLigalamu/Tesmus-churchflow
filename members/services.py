from django.db import transaction
from tenants.models import Church
from .models import DEFAULT_MINISTRY_ROLES, MinistryRole


def ensure_default_ministry_roles(church):
    existing = set(
        MinistryRole.objects.filter(church=church).values_list('name', flat=True)
    )
    for index, name in enumerate(DEFAULT_MINISTRY_ROLES, start=1):
        if name not in existing:
            MinistryRole.objects.create(church=church, name=name, sort_order=index * 10)
    return MinistryRole.objects.filter(church=church).order_by('sort_order', 'name')


def generate_reference_number(church_id):
    with transaction.atomic():
        church = Church.objects.select_for_update().get(id=church_id)
        church.last_member_sequence += 1
        church.save(update_fields=['last_member_sequence'])
        seq = church.last_member_sequence
        return f"{church.code}-{str(seq).zfill(2)}"
