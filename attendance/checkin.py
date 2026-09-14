"""Checking members in to a service from the public check-in link.

Members type their phone number or their reference number. To make checking
in on someone else's behalf hard, each phone (browser) can check in one member
per service, wrong attempts are limited, and only the member's first name and
initial are shown.
"""
import secrets
from dataclasses import dataclass

from django.core.cache import cache
from django.db import IntegrityError, transaction

from members.models import Member
from members.phones import members_with_phone, phone_key

from .models import Attendance

MAX_FAILED_ATTEMPTS = 5
# A wider limit per internet connection stops a script that clears cookies,
# while staying high enough for a church's shared Wi-Fi.
MAX_FAILED_ATTEMPTS_PER_NETWORK = 50
ATTEMPT_WINDOW_SECONDS = 10 * 60

DEVICE_COOKIE = 'churchflow_checkin_device'
DEVICE_COOKIE_SALT = 'churchflow.checkin.device'
DEVICE_COOKIE_MAX_AGE = 365 * 24 * 60 * 60

CHECKED_IN = 'checked_in'
ALREADY_CHECKED_IN = 'already_checked_in'
NOT_FOUND = 'not_found'
SHARED_NUMBER = 'shared_number'
DEVICE_USED = 'device_used'
TOO_MANY_ATTEMPTS = 'too_many_attempts'
INVALID = 'invalid'

MESSAGES = {
    NOT_FOUND: "We couldn't check you in. Check your phone number or reference number, or ask an usher.",
    SHARED_NUMBER: 'More than one member uses this phone number. Please use your reference number, or ask an usher.',
    DEVICE_USED: 'This phone has already been used to check someone in for this service. Please ask an usher to check you in.',
    TOO_MANY_ATTEMPTS: 'Too many attempts. Please wait a few minutes or ask an usher.',
    INVALID: 'Please enter your phone number or reference number.',
}


def short_name(full_name):
    """First name and last initial, e.g. "Mary Wanjiku Muthoni" -> "Mary M."."""
    parts = (full_name or '').split()
    if not parts:
        return ''
    if len(parts) == 1:
        return parts[0]
    return f'{parts[0]} {parts[-1][0].upper()}.'


@dataclass
class CheckInOutcome:
    status: str
    member: Member = None

    @property
    def succeeded(self):
        return self.status in (CHECKED_IN, ALREADY_CHECKED_IN)

    @property
    def display_name(self):
        return short_name(self.member.full_name) if self.member else ''

    @property
    def message(self):
        return MESSAGES.get(self.status, '')


def device_id_for(request):
    """This browser's check-in id, and whether it is new and must be remembered."""
    device_id = request.get_signed_cookie(DEVICE_COOKIE, default=None, salt=DEVICE_COOKIE_SALT)
    if device_id and len(device_id) <= 64:
        return device_id, False
    return secrets.token_urlsafe(24), True


def remember_device(response, device_id, secure=False):
    response.set_signed_cookie(
        DEVICE_COOKIE, device_id, salt=DEVICE_COOKIE_SALT, max_age=DEVICE_COOKIE_MAX_AGE,
        httponly=True, samesite='Lax', secure=secure,
    )


def client_ip(request):
    return request.META.get('REMOTE_ADDR') or 'unknown'


def _limits(device_id, ip):
    return (
        (f'checkin-failures:device:{device_id}', MAX_FAILED_ATTEMPTS),
        (f'checkin-failures:network:{ip}', MAX_FAILED_ATTEMPTS_PER_NETWORK),
    )


def _is_blocked(limits):
    return any(cache.get(key, 0) >= limit for key, limit in limits)


def _record_failure(limits):
    for key, _limit in limits:
        if not cache.add(key, 1, ATTEMPT_WINDOW_SECONDS):
            try:
                cache.incr(key)
            except ValueError:
                cache.set(key, 1, ATTEMPT_WINDOW_SECONDS)


def find_members(service, identifier):
    """Members matching a typed reference number (any capitals) or phone number (any format)."""
    church_members = Member.objects.filter(church_id=service.church_id)
    by_reference = list(church_members.filter(reference_number__iexact=identifier)[:1])
    if by_reference:
        return by_reference
    if len(phone_key(identifier)) >= 9:
        return list(members_with_phone(church_members, identifier)[:2])
    return []


def check_in(service, identifier, device_id, ip):
    """Check a member in to an open service by phone number or reference number."""
    limits = _limits(device_id, ip)
    if _is_blocked(limits):
        return CheckInOutcome(TOO_MANY_ATTEMPTS)
    identifier = (identifier or '').strip()
    if not identifier:
        return CheckInOutcome(INVALID)

    members = find_members(service, identifier)
    if not members:
        # Wrong reference numbers count too: they run in order and are easy to guess.
        _record_failure(limits)
        return CheckInOutcome(NOT_FOUND)
    if len(members) > 1:
        return CheckInOutcome(SHARED_NUMBER)

    member = members[0]
    if Attendance.objects.filter(service=service, member=member).exists():
        return CheckInOutcome(ALREADY_CHECKED_IN, member)
    if Attendance.objects.filter(service=service, device_id=device_id).exists():
        return CheckInOutcome(DEVICE_USED)
    try:
        with transaction.atomic():
            Attendance.objects.create(
                church_id=service.church_id, service=service, member=member,
                method='qr', device_id=device_id,
            )
    except IntegrityError:
        # The same member was checked in at the same moment from elsewhere.
        return CheckInOutcome(ALREADY_CHECKED_IN, member)
    return CheckInOutcome(CHECKED_IN, member)
