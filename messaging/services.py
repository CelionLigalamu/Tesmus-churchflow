from .models import SMSMessage
from .providers.africastalking import send_sms


def send_message(church, recipient_phone, body, template=None):
    sms_message = SMSMessage.objects.create(
        church=church,
        recipient_phone=recipient_phone,
        body=body,
        template=template,
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


def send_bulk(church, recipients, body, template=None):
    results = []
    for member in recipients:
        msg = send_message(church, member.phone_number, body, template=template)
        results.append(msg)
    return results