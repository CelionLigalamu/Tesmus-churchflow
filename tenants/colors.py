"""Colour maths for church branding.

Churches choose their own colours in admin. The dashboard never uses those
colours raw for text: it derives versions that are guaranteed to be readable
on light surfaces and on dark surfaces, so a pale or very dark brand colour
can't make text disappear in either theme.
"""
import re

HEX_PATTERN = re.compile(r'^#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$')

WHITE = '#FFFFFF'
BLACK = '#000000'
DARK_TEXT = '#1F1F1F'

# Backgrounds the derived colours must stay readable on. Keep in step with
# --bg-surface and --bg-body in static/css/theme.css (light and dark themes).
LIGHT_SURFACE = '#FFFFFF'
LIGHT_BODY = '#F5EEE4'
DARK_SURFACE = '#1E2127'
DARK_BODY = '#16181C'

# WCAG AA for normal-size text.
TEXT_CONTRAST = 4.5
# WCAG AA for buttons, borders, icons and other interface parts.
UI_CONTRAST = 3.0

DEFAULT_PRIMARY = '#2C2C2C'
DEFAULT_SECONDARY = '#F5EEE4'
DEFAULT_ACCENT = '#C6A16A'


def normalize_hex(value):
    """Return '#RRGGBB' in upper case, or None if the value isn't a hex colour."""
    if value is None:
        return None
    match = HEX_PATTERN.match(str(value).strip())
    if not match:
        return None
    digits = match.group(1)
    if len(digits) == 3:
        digits = ''.join(ch * 2 for ch in digits)
    return '#' + digits.upper()


def _rgb(hex_value):
    value = normalize_hex(hex_value)
    return tuple(int(value[i:i + 2], 16) for i in (1, 3, 5))


def _to_hex(rgb):
    return '#' + ''.join(f'{max(0, min(255, round(channel))):02X}' for channel in rgb)


def relative_luminance(hex_value):
    def linear(channel):
        channel /= 255
        return channel / 12.92 if channel <= 0.03928 else ((channel + 0.055) / 1.055) ** 2.4

    red, green, blue = (linear(channel) for channel in _rgb(hex_value))
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast_ratio(first, second):
    lighter, darker = sorted((relative_luminance(first), relative_luminance(second)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def mix(first, second, weight):
    """Blend two colours; `weight` is the share of `first` (0..1)."""
    return _to_hex(
        a * weight + b * (1 - weight) for a, b in zip(_rgb(first), _rgb(second))
    )


def ensure_contrast(color, backgrounds, minimum=TEXT_CONTRAST):
    """Move `color` towards black or white until it reads on every background.

    `backgrounds` is one colour or a list. All of them must be on the same side
    (all light or all dark), which is how the theme uses them.
    """
    if isinstance(backgrounds, str):
        backgrounds = [backgrounds]
    color = normalize_hex(color)

    def weakest(candidate):
        return min(contrast_ratio(candidate, background) for background in backgrounds)

    if weakest(color) >= minimum:
        return color
    average = sum(relative_luminance(background) for background in backgrounds) / len(backgrounds)
    target = BLACK if average > 0.5 else WHITE
    for step in range(1, 21):
        candidate = mix(color, target, 1 - step * 0.05)
        if weakest(candidate) >= minimum:
            return candidate
    return target


def readable_text_on(background):
    """White or black, whichever reads better on `background`.

    Pure black (not the softer body-text colour) is used deliberately: for any
    background one of white or black always reaches at least 4.5:1.
    """
    return WHITE if contrast_ratio(WHITE, background) >= contrast_ratio(BLACK, background) else BLACK


def church_palette(church):
    """CSS custom properties for a church, safe in both light and dark themes."""
    primary = normalize_hex(getattr(church, 'primary_color', None)) or DEFAULT_PRIMARY
    secondary = normalize_hex(getattr(church, 'secondary_color', None)) or DEFAULT_SECONDARY
    accent = normalize_hex(getattr(church, 'accent_color', None)) or DEFAULT_ACCENT

    tint_light = mix(primary, LIGHT_SURFACE, 0.12)
    tint_dark = mix(primary, DARK_SURFACE, 0.30)
    accent_tint_light = mix(accent, LIGHT_SURFACE, 0.14)
    accent_tint_dark = mix(accent, DARK_SURFACE, 0.30)

    # Filled controls (buttons, avatar, active filters) must stand out from
    # the page. Dark church colours are lifted for the dark theme; pale ones
    # are deepened for the light theme. Their text colour follows the fill.
    fill_light = ensure_contrast(primary, [LIGHT_SURFACE, LIGHT_BODY], UI_CONTRAST)
    fill_dark = ensure_contrast(primary, [DARK_SURFACE, DARK_BODY], UI_CONTRAST)

    return {
        '--brand-primary': primary,
        '--brand-secondary': secondary,
        '--brand-accent': accent,
        '--brand-on-primary': readable_text_on(primary),
        '--brand-fill-light': fill_light,
        '--brand-fill-dark': fill_dark,
        '--brand-on-fill-light': readable_text_on(fill_light),
        '--brand-on-fill-dark': readable_text_on(fill_dark),
        '--brand-tint-light': tint_light,
        '--brand-tint-dark': tint_dark,
        # Checked against every background the colour can sit on in each
        # theme: its own tint, cards and the page itself.
        '--brand-ink-light': ensure_contrast(primary, [tint_light, LIGHT_SURFACE, LIGHT_BODY]),
        '--brand-ink-dark': ensure_contrast(primary, [tint_dark, DARK_SURFACE, DARK_BODY]),
        '--brand-accent-tint-light': accent_tint_light,
        '--brand-accent-tint-dark': accent_tint_dark,
        '--brand-accent-ink-light': ensure_contrast(accent, [accent_tint_light, LIGHT_SURFACE], UI_CONTRAST),
        '--brand-accent-ink-dark': ensure_contrast(accent, [accent_tint_dark, DARK_SURFACE], UI_CONTRAST),
    }
