import os
import africastalking

def normalize_phone(phone):
    phone = phone.strip().replace(' ', '')
    if phone.startswith('0'):
        return '+254' + phone[1:]
    if phone.startswith('+'):
        return phone
    if phone.startswith('254'):
        return '+' + phone
    return phone

def send_sms(recipient_phone, message, sender_id=None):
    username = os.getenv('AFRICASTALKING_USERNAME')
    api_key = os.getenv('AFRICASTALKING_API_KEY')

    africastalking.initialize(username, api_key)
    sms = africastalking.SMS

    recipient_phone = normalize_phone(recipient_phone)

    kwargs = {}
    if sender_id:
        kwargs['sender_id'] = sender_id

    response = sms.send(message, [recipient_phone], **kwargs)
    return message_id_from_response(response)


# Per-recipient status codes meaning Africa's Talking accepted the message:
# 100 Processed, 101 Sent, 102 Queued. Anything else (e.g. 403 InvalidPhoneNumber,
# 405 InsufficientBalance, 406 UserInBlacklist) means it will not be delivered.
ACCEPTED_STATUS_CODES = {100, 101, 102}


class SMSRejected(Exception):
    """Africa's Talking answered, but refused to send the message."""


def message_id_from_response(response):
    """Return the provider's message id for a one-recipient send.

    The full response is several hundred characters; only the id is worth
    keeping. Raises SMSRejected when the recipient was not accepted, so the
    message is recorded as failed with the provider's reason.
    """
    data = response.get('SMSMessageData') if isinstance(response, dict) else None
    recipients = (data or {}).get('Recipients') or []
    if not recipients:
        raise SMSRejected((data or {}).get('Message') or 'The SMS provider did not accept the message.')
    recipient = recipients[0]
    try:
        status_code = int(recipient.get('statusCode'))
    except (TypeError, ValueError):
        status_code = None
    if status_code not in ACCEPTED_STATUS_CODES:
        raise SMSRejected(recipient.get('status') or f'The SMS provider refused the message (code {status_code}).')
    return str(recipient.get('messageId') or '')