import os
import africastalking


def send_sms(recipient_phone, message, sender_id=None):
    username = os.getenv('AFRICASTALKING_USERNAME')
    api_key = os.getenv('AFRICASTALKING_API_KEY')

    africastalking.initialize(username, api_key)
    sms = africastalking.SMS

    kwargs = {}
    if sender_id:
        kwargs['sender_id'] = sender_id

    response = sms.send(message, [recipient_phone], **kwargs)
    return response