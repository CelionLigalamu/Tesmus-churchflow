"""Explain why a text message failed, in words a church administrator understands.

The provider's technical error is always kept on the SMSMessage (and in the
audit log) for Tesmus support. These plain explanations are only for display.
"""
import re

UNREACHABLE = (
    'Could not connect to the text message service. Check the internet connection '
    'and try again. If this keeps happening, contact Tesmus support.'
)
NO_BALANCE = 'The church has run out of SMS credit. Top up the SMS account, then send again.'
ACCOUNT_SETTINGS = 'The text message account is not set up correctly. Please contact Tesmus support.'
SENDER_NAME = 'The sender name for this church has not been approved yet. Please contact Tesmus support.'
BAD_NUMBER = "The phone number is not valid. Check the member's phone number and try again."
BLOCKED_NUMBER = 'This phone number has blocked messages from the church, so the text could not be delivered.'
UNKNOWN = 'The text message could not be sent. Please try again later or contact Tesmus support.'

# Checked in order; the first matching pattern wins.
_RULES = (
    (r'insufficient|balance|credit', NO_BALANCE),
    (r'blacklist|blocked|do ?not ?disturb|\bdnd\b', BLOCKED_NUMBER),
    (r'sender.?id|senderid', SENDER_NAME),
    (r'invalid.?phone|phone.?number|invalid.?recipient|invalid number', BAD_NUMBER),
    (r'authenticat|api.?key|unauthori[sz]ed|\b401\b|username', ACCOUNT_SETTINGS),
    (r'ssl|connection|max retries|timed? ?out|timeout|name resolution|getaddrinfo|'
     r'unreachable|network|temporarily unavailable|\b50[234]\b', UNREACHABLE),
)
_PLAIN_REASONS = {UNREACHABLE, NO_BALANCE, ACCOUNT_SETTINGS, SENDER_NAME, BAD_NUMBER, BLOCKED_NUMBER, UNKNOWN}


def plain_failure_reason(raw):
    """Turn a provider error such as "HTTPSConnectionPool(...) SSLError" into plain words."""
    text = (raw or '').strip()
    if text in _PLAIN_REASONS:
        return text
    for pattern, reason in _RULES:
        if re.search(pattern, text, re.IGNORECASE):
            return reason
    return UNKNOWN
