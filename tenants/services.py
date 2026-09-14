"""Resolving region names that people type in free text.

A region is simply the area a member lives in. Members type it themselves (or
whoever adds them does), so the same area can arrive as "Kasarani",
"kasarani" or "  Kasarani ". These helpers normalise the text and match it
case-insensitively against what the church already has, so all of those
resolve to one region, and an area nobody has typed before becomes a new one.
"""
import re

from django.db import IntegrityError, transaction

from .models import Region


class PlaceError(ValueError):
    """A typed region name could not be used as given."""


def normalize_place_name(value):
    """Trim the text and collapse runs of whitespace."""
    if not value:
        return ''
    return re.sub(r'\s+', ' ', str(value)).strip()


def tidy_new_place_name(name):
    """Neaten a brand-new area name typed all in lower or all in upper case.

    "sikhendu" and "SIKHENDU" are saved as "Sikhendu". A name typed with mixed
    capitals, for example "Kanduyi East", is kept exactly as typed.
    """
    name = normalize_place_name(name)
    if name and (name.islower() or name.isupper()):
        return ' '.join(word[:1].upper() + word[1:].lower() for word in name.split(' '))
    return name


def find_region(church, name):
    name = normalize_place_name(name)
    if not name:
        return None
    return Region.objects.filter(church=church, name__iexact=name).first()


def resolve_region(church, name, create=False):
    """Return the church's region for this typed name.

    With create=True an area the church does not have yet becomes a new
    region. With create=False an unknown name raises PlaceError, for people
    who may only choose existing regions (for example a region-scoped user).
    """
    name = normalize_place_name(name)
    if not name:
        return None

    region = find_region(church, name)
    if region:
        return region
    if not create:
        raise PlaceError(f'"{name}" is not one of your regions.')
    try:
        # If two people add the same new area at the same moment, the database
        # allows only one; the second simply joins it.
        with transaction.atomic():
            return Region.objects.create(church=church, name=tidy_new_place_name(name))
    except IntegrityError:
        return find_region(church, name)


# Friendly names for records that point at a region, used on the merge page.
REGION_USAGE_LABELS = {
    'members': 'Members',
    'visitors': 'Visitors',
    'services': 'Services',
    'attendances': 'Attendance records',
    'scoped_users': 'Dashboard users limited to this region',
    'pastors': 'Pastors picked for this region',
}


def region_usage(region):
    """How many records of each kind belong to a region, for the merge page."""
    usage = []
    for relation in Region._meta.related_objects:
        if relation.one_to_many:
            count = relation.related_model._base_manager.filter(**{relation.field.name: region}).count()
        elif relation.many_to_many:
            count = getattr(region, relation.get_accessor_name()).count()
        else:
            continue
        name = relation.get_accessor_name()
        usage.append((REGION_USAGE_LABELS.get(name, name.replace('_', ' ').capitalize()), count))
    usage.append((REGION_USAGE_LABELS['pastors'], region.pastors.count()))
    return usage


def merge_regions(source, target):
    """Move everything from `source` into `target`, then remove `source`.

    For the same area typed two ways ("Sikendu" and "Sikhendu"). Every record
    that points at a region is found from the model itself, so a record type
    added later can never be left behind or deleted with the old region.
    Returns how many members moved.
    """
    if source.pk == target.pk:
        raise PlaceError('Choose a different region to merge into.')
    if source.church_id != target.church_id:
        raise PlaceError('Regions can only be merged within the same church.')

    with transaction.atomic():
        members_moved = 0
        for relation in Region._meta.related_objects:
            if relation.one_to_many:
                moved = relation.related_model._base_manager.filter(
                    **{relation.field.name: source}
                ).update(**{relation.field.name: target})
                if relation.get_accessor_name() == 'members':
                    members_moved = moved
            elif relation.many_to_many:
                accessor = relation.get_accessor_name()
                getattr(target, accessor).add(*getattr(source, accessor).all())
            else:
                raise PlaceError(f'Cannot merge regions: unexpected link from {relation.related_model.__name__}.')
        target.pastors.add(*source.pastors.all())
        source.delete()
    return members_moved


def region_names(church):
    """Existing region names, for autocomplete suggestions."""
    return list(
        Region.objects.filter(church=church).order_by('name').values_list('name', flat=True)
    )
