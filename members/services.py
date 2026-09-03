from django.db import transaction
from tenants.models import Church


def generate_reference_number(church_id):
    with transaction.atomic():
        church = Church.objects.select_for_update().get(id=church_id)
        church.last_member_sequence += 1
        church.save(update_fields=['last_member_sequence'])
        seq = church.last_member_sequence
        return f"{church.code}-{str(seq).zfill(2)}"