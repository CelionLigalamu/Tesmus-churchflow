from django.template import Context, Template
from django.utils import timezone

from .failure_reasons import plain_failure_reason
from .models import SMSMessage, SMSTemplate
from .providers.africastalking import send_sms
from notifications.services import notify_sms_failed


# Every automated message the platform can send. Churches edit the wording
# themselves under Church setup -> SMS templates, so onboarding a new church
# never requires touching this file. Add an entry here only when introducing a
# genuinely new kind of message.
SYSTEM_TEMPLATES = {
    'attendance_present': {
        'label': 'Attendance - Present',
        'description': 'Sent to a member who attended a service.',
        'placeholders': ('member_name', 'church_name', 'service_name', 'service_date', 'start_time', 'end_time'),
        'body': (
            'Mpendwa {{member_name}}, tunakushukuru kwa kushiriki nasi katika '
            '{{service_name}} ya {{service_date}}. Mungu akubariki.'
        ),
    },
    'attendance_absent': {
        'label': 'Attendance - Absent',
        'description': 'Sent to a member who missed a service.',
        'placeholders': ('member_name', 'church_name', 'service_name', 'service_date', 'start_time', 'end_time'),
        'body': (
            'Mpendwa {{member_name}}, tulikukosa katika {{service_name}} ya '
            '{{service_date}}. Tunatumaini uko salama. Ikiwa kuna changamoto '
            'yoyote unayopitia, tafadhali wasiliana na kanisa.'
        ),
    },
    'region_attendance_summary': {
        'label': 'Region attendance summary',
        'description': "Sent to each region's pastors when a service closes.",
        'placeholders': (
            'pastor_name', 'region_name', 'church_name', 'service_name', 'service_date',
            'total_members', 'present', 'absent', 'attendance_rate',
        ),
        'body': (
            'Mchungaji {{pastor_name}}, mahudhurio ya {{region_name}} katika '
            '{{service_name}} ya {{service_date}}: waliohudhuria {{present}} kati ya '
            '{{total_members}} ({{attendance_rate}}%), hawakuhudhuria {{absent}}. '
            '{{church_name}}'
        ),
    },
    'member_reference': {
        'label': 'Member reference number',
        'description': 'Sent to a member with their registration reference number.',
        'placeholders': ('member_name', 'church_name', 'reference_number', 'phone_number'),
        'body': (
            'Mpendwa {{member_name}}, namba yako ya usajili katika {{church_name}} '
            'ni {{reference_number}}. Tafadhali ihifadhi kwa matumizi ya mahudhurio '
            'ya ibada na shughuli nyingine za kanisa. Mungu akubariki.'
        ),
    },
    'visitor_welcome': {
        'label': 'Visitor welcome',
        'description': 'Sent to a first-time visitor after their visit.',
        'placeholders': ('visitor_name', 'church_name'),
        'body': (
            'Mpendwa {{visitor_name}}, tunakushukuru kwa kututembelea na kushiriki '
            'nasi katika ibada ya leo. Tunafurahi kuwa nawe na tunakukaribisha tena '
            'katika familia ya {{church_name}}. Mungu akubariki.'
        ),
    },
}

TEMPLATE_ORDER = list(SYSTEM_TEMPLATES)


def ensure_system_templates(church):
    """Create any missing system templates for a church, in display order."""
    for name in TEMPLATE_ORDER:
        SMSTemplate.objects.get_or_create(
            church=church,
            name=name,
            defaults={'body': SYSTEM_TEMPLATES[name]['body']},
        )
    by_name = {
        t.name: t
        for t in SMSTemplate.objects.filter(church=church, name__in=TEMPLATE_ORDER)
    }
    return [by_name[name] for name in TEMPLATE_ORDER if name in by_name]


def get_system_template(church, name):
    """Return a church's template, or None when they have switched it off."""
    template, _ = SMSTemplate.objects.get_or_create(
        church=church,
        name=name,
        defaults={'body': SYSTEM_TEMPLATES[name]['body']},
    )
    return template if template.is_active else None


def render_sms(template, **context):
    return Template(template.body).render(Context(context)).strip()


def get_attendance_template(church, result):
    return get_system_template(church, f'attendance_{result}')


def attendance_context(member, service):
    return {
        'member_name': member.full_name,
        'church_name': service.church.name,
        'service_name': service.name,
        'service_date': service.date.strftime('%d %b %Y'),
        'start_time': service.start_time.strftime('%H:%M') if service.start_time else '',
        'end_time': service.end_time.strftime('%H:%M') if service.end_time else '',
    }


def render_attendance_message(template, member, service):
    return render_sms(template, **attendance_context(member, service))


def send_reference_number_sms(member):
    """Send a member their registration reference number.

    Deliberately not deduplicated: a member may legitimately ask for their
    reference number again after losing it. Returns None when the church has
    switched this template off.
    """
    template = get_system_template(member.church, 'member_reference')
    if template is None:
        return None
    body = render_sms(
        template,
        member_name=member.full_name,
        church_name=member.church.name,
        reference_number=member.reference_number,
        phone_number=member.phone_number,
    )
    return send_message(
        member.church,
        member.phone_number,
        body,
        template=template,
        audience_type='individual',
        audience_label=f'Reference number - {member.reference_number}',
    )


def send_visitor_welcome_sms(visitor):
    """Welcome a first-time visitor. None when the template is switched off."""
    template = get_system_template(visitor.church, 'visitor_welcome')
    if template is None:
        return None
    body = render_sms(
        template,
        visitor_name=visitor.full_name,
        church_name=visitor.church.name,
    )
    return send_message(
        visitor.church,
        visitor.phone_number,
        body,
        template=template,
        audience_type='individual',
        audience_label='Visitor welcome',
    )


def send_attendance_present_sms(attendance):
    """Thank a member for attending. None when the template is switched off."""
    template = get_attendance_template(attendance.church, 'present')
    if template is None:
        return None
    body = render_attendance_message(template, attendance.member, attendance.service)
    return send_message(
        attendance.church,
        attendance.member.phone_number,
        body,
        template=template,
        audience_type='service_present',
        audience_label=attendance.service.name,
    )


def send_region_summary_sms(pastor, stats, service, template):
    """Text one pastor their region's statistics for a service.

    Deduplicated per service, region and pastor, so re-running finalisation
    never texts a pastor twice.
    """
    region = stats['region']
    body = render_sms(
        template,
        pastor_name=pastor.full_name,
        region_name=region.name,
        church_name=service.church.name,
        service_name=service.name,
        service_date=service.date.strftime('%d %b %Y'),
        total_members=stats['total_members'],
        present=stats['present'],
        absent=stats['absent'],
        attendance_rate=stats['attendance_rate'],
    )
    return send_message(
        service.church,
        pastor.phone_number,
        body,
        template=template,
        dedupe_key=f'region-summary:{service.pk}:{region.pk}:{pastor.pk}',
        audience_label=f'{region.name} attendance summary - {service.name}',
    )


def send_message(church, recipient_phone, body, template=None, dedupe_key=None, audience_type='individual', audience_label=''):
    if dedupe_key:
        existing = SMSMessage.objects.filter(dedupe_key=dedupe_key).first()
        if existing:
            return existing

    sms_message = SMSMessage.objects.create(
        church=church,
        recipient_phone=recipient_phone,
        body=body,
        audience_type=audience_type,
        audience_label=audience_label,
        template=template,
        dedupe_key=dedupe_key,
        status='queued',
    )

    try:
        sender_id = None
        if hasattr(church, 'sms_config'):
            sender_id = church.sms_config.sender_id or None

        message_id = send_sms(recipient_phone, body, sender_id=sender_id)

        sms_message.status = 'sent'
        # Trimmed to the column size: PostgreSQL refuses longer text, which would
        # wrongly record a delivered message as failed.
        id_length = SMSMessage._meta.get_field('provider_message_id').max_length
        sms_message.provider_message_id = str(message_id or '')[:id_length]
        sms_message.sent_at = timezone.now()
        sms_message.save(update_fields=['status', 'provider_message_id', 'sent_at'])
    except Exception as e:
        sms_message.status = 'failed'
        sms_message.failure_reason = str(e)
        sms_message.save(update_fields=['status', 'failure_reason'])
        notify_sms_failed(sms_message)

    return sms_message


def send_bulk(church, recipients, body, template=None, audience_type='individual', audience_label=''):
    results = []
    for member in recipients:
        msg = send_message(church, member.phone_number, body, template=template, audience_type=audience_type, audience_label=audience_label)
        results.append(msg)
    return results


MAX_REPORTED_REASONS = 2


def delivery_report(sms_messages):
    """Summarise what actually happened to a batch of sent messages.

    `send_message` never raises - it records a failed SMSMessage instead - so
    the only way to know whether anything reached the provider is to inspect
    the returned records. Callers must report from this, never from the number
    of recipients they intended to reach.
    """
    sms_messages = list(sms_messages)
    # A None entry means the send was skipped because the church switched that
    # template off - not a provider failure, and worth saying so distinctly.
    skipped = [m for m in sms_messages if m is None]
    attempted = [m for m in sms_messages if m is not None]
    failed = [m for m in attempted if m.status == 'failed']

    reasons = []
    for message in failed:
        reason = plain_failure_reason(message.failure_reason)
        if reason not in reasons:
            reasons.append(reason)

    return {
        'total': len(sms_messages),
        'sent': len(attempted) - len(failed),
        'failed': len(failed),
        'skipped': len(skipped),
        'reasons': reasons,
    }


def describe_delivery(report, noun='recipient'):
    """Turn a delivery_report into a (level, text) pair for the user.

    Level is 'success', 'warning' or 'error' so that callers can map it onto
    whichever messaging framework they use (admin or dashboard).
    """
    total, sent, failed = report['total'], report['sent'], report['failed']
    skipped = report.get('skipped', 0)
    plural = noun if total == 1 else noun + 's'

    detail = ''
    if report['reasons']:
        shown = report['reasons'][:MAX_REPORTED_REASONS]
        detail = ' Reason: ' + '; '.join(shown)
        if len(report['reasons']) > len(shown):
            detail += '; and other errors'
    if skipped:
        detail += (
            f' {skipped} skipped because the message template is switched off '
            'in Church setup.'
        )

    if total == 0:
        return 'warning', f'No {noun}s to send to.'
    if skipped == total:
        return 'warning', (
            'Nothing was sent - the message template is switched off in '
            'Church setup.'
        )
    if failed == 0:
        return 'success', f'Sent to {sent} {plural}.{detail}'
    if sent == 0:
        if total == 1:
            return 'error', f'Could not send to the {noun}.{detail}'
        return 'error', f'Could not send to any of the {total} {plural}.{detail}'
    return 'warning', f'Sent to {sent} of {total} {plural}. {failed} failed.{detail}'
