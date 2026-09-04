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
    return response