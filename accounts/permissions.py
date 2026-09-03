def user_can_access_church(user, church):
    if user.is_tesmus_staff:
        return True
    return user.church_id == church.id


def user_can_access_region(user, region):
    if user.is_tesmus_staff:
        return True
    if user.church_id != region.church_id:
        return False
    if user.scope_type == 'church':
        return True
    if user.scope_type == 'region':
        return user.scope_region_id == region.id
    if user.scope_type == 'branch' and user.scope_branch_id:
        return user.scope_branch.region_id == region.id
    return False


def user_can_access_branch(user, branch):
    if user.is_tesmus_staff:
        return True
    if user.church_id != branch.church_id:
        return False
    if user.scope_type == 'church':
        return True
    if user.scope_type == 'region':
        return branch.region_id == user.scope_region_id
    if user.scope_type == 'branch':
        return user.scope_branch_id == branch.id
    return False