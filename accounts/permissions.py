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
    return False