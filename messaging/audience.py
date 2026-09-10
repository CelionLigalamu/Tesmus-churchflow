from members.models import Member
from visitors.models import Visitor


def get_recipients(church, audience_type, region=None, branch=None, service=None, result=None):
    qs = Member.objects.filter(church=church)

    if audience_type == 'visitor_present' and service:
        visitor_ids = service.attendances.filter(
            visitor__isnull=False,
            result='present',
        ).values_list('visitor_id', flat=True)
        return Visitor.objects.filter(church=church, id__in=visitor_ids)

    if audience_type == 'church':
        return qs
    if audience_type == 'region' and region:
        return qs.filter(region=region)
    if audience_type == 'branch' and branch:
        return qs.filter(branch=branch)
    if audience_type == 'leadership' and result:
        recipients = qs.filter(ministry_roles=result)
        if region:
            recipients = recipients.filter(region=region)
        if branch:
            recipients = recipients.filter(branch=branch)
        return recipients.distinct()
    if audience_type == 'service_present' and service:
        member_ids = service.attendances.filter(result='present').values_list('member_id', flat=True)
        return qs.filter(id__in=member_ids)
    if audience_type == 'service_absent' and service:
        member_ids = service.attendances.filter(result='absent').values_list('member_id', flat=True)
        return qs.filter(id__in=member_ids)
    return qs.none()


from accounts.permissions import user_can_access_region, user_can_access_branch


def user_can_send_to(user, audience_type, region=None, branch=None):
    if user.is_tesmus_staff:
        return True
    if audience_type == 'church':
        return user.scope_type == 'church'
    if audience_type == 'visitor_present':
        if user.scope_type == 'region':
            return bool(region and user_can_access_region(user, region))
        if user.scope_type == 'branch':
            return bool(branch and user_can_access_branch(user, branch))
        return user.scope_type == 'church'
    if audience_type in {'region', 'visitor_region'} and region:
        return user_can_access_region(user, region)
    if audience_type in {'branch', 'visitor_branch'} and branch:
        return user_can_access_branch(user, branch)
    if audience_type == 'leadership':
        if user.scope_type == 'region':
            return bool(region and user_can_access_region(user, region))
        if user.scope_type == 'branch':
            return bool(branch and user_can_access_branch(user, branch))
        return user.scope_type == 'church'
    return True
