"""Bulk member import from a CSV file.

Deliberately two-phase: a file is parsed and validated into a preview, and
only committed after the user confirms. The same validation runs in both
phases, so what the preview promises is exactly what the commit performs.

This module never sends SMS itself. After an import is confirmed, the view
texts each new member their reference number in the background (see
members/reference_texts.py), unless the church has switched that message off.
"""
import csv
import io
import re

from django.db import transaction

from tenants.services import find_region, normalize_place_name, resolve_region

from .models import Member
from .phones import phone_key
from .services import generate_reference_number

MAX_ROWS = 5000
MAX_FILE_BYTES = 2 * 1024 * 1024

REQUIRED_COLUMNS = ('full_name', 'phone_number')
OPTIONAL_COLUMNS = ('region',)
TEMPLATE_HEADER = REQUIRED_COLUMNS + OPTIONAL_COLUMNS

CREATE = 'create'
SKIP = 'skip'
ERROR = 'error'


class ImportError_(Exception):
    """The file as a whole cannot be processed."""


def _normalise_header(name):
    return re.sub(r'[\s\-]+', '_', (name or '').strip().lower())


def read_rows(uploaded_file):
    """Parse the upload into a list of dicts. Raises ImportError_ on bad files."""
    if uploaded_file.size > MAX_FILE_BYTES:
        raise ImportError_(
            f'That file is {uploaded_file.size // 1024}KB. The limit is '
            f'{MAX_FILE_BYTES // 1024}KB.'
        )

    raw = uploaded_file.read()
    try:
        # utf-8-sig strips the byte-order mark Excel adds when saving as CSV.
        text = raw.decode('utf-8-sig')
    except UnicodeDecodeError:
        raise ImportError_(
            'That file is not plain text. In Excel choose File > Save As > CSV.'
        )

    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise ImportError_('That file is empty.')

    reader.fieldnames = [_normalise_header(name) for name in reader.fieldnames]
    missing = [c for c in REQUIRED_COLUMNS if c not in reader.fieldnames]
    if missing:
        raise ImportError_(
            'The file must have a header row containing: '
            + ', '.join(TEMPLATE_HEADER)
            + '. Missing: ' + ', '.join(missing) + '.'
        )

    rows = []
    for line_number, row in enumerate(reader, start=2):
        if len(rows) >= MAX_ROWS:
            raise ImportError_(f'That file has more than {MAX_ROWS} rows.')
        if not any((value or '').strip() for value in row.values()):
            continue  # blank spacer line
        rows.append((line_number, row))
    if not rows:
        raise ImportError_('That file has a header but no data rows.')
    return rows


def validate(church, rows):
    """Turn parsed rows into per-row outcomes. Touches nothing in the database."""
    existing_phones = {
        phone_key(p)
        for p in Member.objects.filter(church=church).values_list('phone_number', flat=True)
    }
    seen_in_file = {}
    results = []

    for line_number, row in rows:
        full_name = normalize_place_name(row.get('full_name'))
        phone_raw = (row.get('phone_number') or '').strip()
        region_name = normalize_place_name(row.get('region'))
        key = phone_key(phone_raw)

        entry = {
            'line': line_number,
            'full_name': full_name,
            'phone_number': phone_raw,
            'region': region_name,
            'action': CREATE,
            'message': '',
        }

        if not full_name:
            entry.update(action=ERROR, message='Missing full name.')
        elif not key:
            entry.update(action=ERROR, message='Missing or invalid phone number.')
        elif key in seen_in_file:
            entry.update(
                action=ERROR,
                message=f'Same phone number as row {seen_in_file[key]} in this file.',
            )
        elif key in existing_phones:
            entry.update(action=SKIP, message='Already a member - will be left unchanged.')
        elif region_name and not find_region(church, region_name):
            # Any area is accepted: one the church does not have yet is added.
            entry['message'] = f'New area "{region_name}" will be added as a region.'

        if entry['action'] != ERROR and key:
            seen_in_file.setdefault(key, line_number)
        results.append(entry)

    return results


def summarise(results):
    return {
        'total': len(results),
        'create': sum(1 for r in results if r['action'] == CREATE),
        'skip': sum(1 for r in results if r['action'] == SKIP),
        'error': sum(1 for r in results if r['action'] == ERROR),
    }


@transaction.atomic
def commit(church, results):
    """Create the members the preview marked as `create`. All or nothing.

    Returns the members created, in the order they appeared in the file.
    """
    created = []
    for entry in results:
        if entry['action'] != CREATE:
            continue
        region = resolve_region(church, entry['region'], create=True)
        created.append(Member.objects.create(
            church=church,
            region=region,
            full_name=entry['full_name'],
            phone_number=entry['phone_number'],
            reference_number=generate_reference_number(church.id),
        ))
    return created
