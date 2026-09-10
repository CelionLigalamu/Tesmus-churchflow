from django.template import Context, Template

from .models import SMSMessage, SMSTemplate
from .providers.africastalking import send_sms


ATTENDANCE_TEMPLATE_DEFAULTS = {
    'attendance_present': (
        'Mpendwa {{member_name}}, tunakushukuru kwa kushiriki nasi katika '
        '{{service_name}} ya {{service_date}}. Mungu akubariki.'
    ),
    'attendance_absent': (
        'Mpendwa {{member_name}}, tulikukosa katika {{service_name}} ya '
        '{{service_date}}. Tunatumaini uko salama. Ikiwa kuna changamoto '
        'yoyote unayopitia, tafadhali wasiliana na kanisa.'
    ),
}


def get_attendance_template(church, result):
    name = f'attendance_{result}'
    body = ATTENDANCE_TEMPLATE_DEFAULTS[name]
    template, _ = SMSTemplate.objects.get_or_create(
        church=church,
        name=name,
        defaults={'body': body},
    )
    return template if template.is_active else None


def render_attendance_message(template, member, service):
    return Template(template.body).render(Context({
        'member_name': member.full_name,
        'church_name': service.church.name,
        'service_name': service.name,
        'service_date': service.date.strftime('%d %b %Y'),
        'start_time': service.start_time.strftime('%H:%M') if service.start_time else '',
        'end_time': service.end_time.strftime('%H:%M') if service.end_time else '',
    })).strip()


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

        response = send_sms(recipient_phone, body, sender_id=sender_id)

        sms_message.status = 'sent'
        sms_message.provider_message_id = str(response)
        sms_message.save(update_fields=['status', 'provider_message_id'])
    except Exception as e:
        sms_message.status = 'failed'
        sms_message.failure_reason = str(e)
        sms_message.save(update_fields=['status', 'failure_reason'])

    return sms_message


def send_bulk(church, recipients, body, template=None, audience_type='individual', audience_label=''):
    results = []
    for member in recipients:
        msg = send_message(church, member.phone_number, body, template=template, audience_type=audience_type, audience_label=audience_label)
        results.append(msg)
    return results
