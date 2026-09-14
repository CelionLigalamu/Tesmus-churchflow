"""Recognising the same phone number however it was typed."""
import re


def phone_key(value):
    """A comparison key for phone numbers, not a storage format.

    Lets 0712345678, +254712345678 and 254 712 345 678 be recognised as the
    same person without changing how numbers are stored.
    """
    digits = re.sub(r'\D', '', str(value or ''))
    if digits.startswith('254'):
        digits = digits[3:]
    elif digits.startswith('0'):
        digits = digits[1:]
    return digits


def phone_variants(raw):
    """The common ways the same number is saved, for a fast database lookup."""
    key = phone_key(raw)
    if not key:
        return [raw]
    return [raw, key, f'0{key}', f'254{key}', f'+254{key}']


def members_with_phone(queryset, raw):
    """Members in `queryset` whose saved phone number is the same number as `raw`."""
    key = phone_key(raw)
    if len(key) < 9:
        return queryset.none()
    exact = queryset.filter(phone_number__in=phone_variants(raw))
    if exact.exists():
        return exact
    # Numbers saved with spaces or dashes, such as "0712 345 678".
    matching_ids = [pk for pk, phone in queryset.values_list('pk', 'phone_number') if phone_key(phone) == key]
    return queryset.filter(pk__in=matching_ids)
