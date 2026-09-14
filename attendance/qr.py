"""QR codes for service check-in links, drawn on this server (no outside service)."""
import segno
from django.utils.safestring import mark_safe


def qr_svg(url, scale=6):
    """An inline SVG QR code for `url`, ready to place directly in a page."""
    code = segno.make(url, error='m', micro=False)
    return mark_safe(code.svg_inline(
        scale=scale, border=2, dark='#0F172A', light='#FFFFFF', omitsize=True, title='Check-in QR code',
    ))
