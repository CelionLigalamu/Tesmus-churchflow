from django.db import transaction
from members.models import Member
from members.services import generate_reference_number


@transaction.atomic
def convert_visitor_to_member(visitor):
    if visitor.converted_to_member_id:
        return visitor.converted_to_member

    reference_number = generate_reference_number(visitor.church_id)
    member = Member.objects.create(
        church=visitor.church,
        region=visitor.region,
        branch=visitor.branch,
        full_name=visitor.full_name,
        phone_number=visitor.phone_number,
        reference_number=reference_number,
        status='active',
    )
    visitor.converted_to_member = member
    visitor.save(update_fields=['converted_to_member'])
    return member