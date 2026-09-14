"""Resolving region and branch names that users type in free text.

Users type a place name rather than picking from a dropdown, so the same
region can arrive as "Kasarani", "kasarani" or "  Kasarani ". These helpers
normalise the text and match it case-insensitively against what the church
already has, so those three all resolve to one region instead of three.
"""
import re

from .models import Branch, Region


class PlaceError(ValueError):
    """A typed region or branch name could not be used as given."""


def normalize_place_name(value):
    """Trim, collapse runs of whitespace, and drop surrounding punctuation."""
    if not value:
        return ''
    return re.sub(r'\s+', ' ', str(value)).strip()


def find_region(church, name):
    name = normalize_place_name(name)
    if not name:
        return None
    return Region.objects.filter(church=church, name__iexact=name).first()


def find_branch(church, name):
    name = normalize_place_name(name)
    if not name:
        return None
    return Branch.objects.filter(church=church, name__iexact=name).first()


def resolve_region(church, name, create=False):
    """Return the church's region for this typed name.

    With create=False an unknown name raises PlaceError, which is what the
    spreadsheet import wants: a typo in row 400 should be reported, not
    silently turned into a new region.
    """
    name = normalize_place_name(name)
    if not name:
        return None

    region = find_region(church, name)
    if region:
        return region
    if not create:
        raise PlaceError(f'"{name}" is not one of your regions.')
    return Region.objects.create(church=church, name=name)


def resolve_branch(church, name, region=None, create=False):
    """Return the church's branch for this typed name, tied to `region`.

    A branch belongs to at most one region. If the branch already exists under
    a different region, that is a genuine conflict and is reported rather than
    silently reassigned.
    """
    name = normalize_place_name(name)
    if not name:
        return None

    branch = find_branch(church, name)
    if branch:
        if region and branch.region_id and branch.region_id != region.id:
            raise PlaceError(
                f'"{branch.name}" already belongs to the {branch.region.name} region.'
            )
        if region and not branch.region_id:
            branch.region = region
            branch.save(update_fields=['region'])
        return branch

    if not create:
        raise PlaceError(f'"{name}" is not one of your branches.')
    return Branch.objects.create(church=church, name=name, region=region)


def region_names(church):
    """Existing region names, for autocomplete suggestions."""
    return list(
        Region.objects.filter(church=church).order_by('name').values_list('name', flat=True)
    )


def branch_names(church, region=None):
    """Existing branch names, for autocomplete suggestions."""
    queryset = Branch.objects.filter(church=church)
    if region is not None:
        queryset = queryset.filter(region=region)
    return list(queryset.order_by('name').values_list('name', flat=True))
