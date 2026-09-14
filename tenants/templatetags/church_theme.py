from django import template
from django.utils.safestring import mark_safe

from tenants.colors import church_palette

register = template.Library()


@register.simple_tag
def church_theme_style(church):
    """Inline CSS custom properties for a church's colours.

    Every value is a normalised '#RRGGBB' produced by tenants.colors, so the
    output can't carry anything other than colour codes into the page.
    """
    palette = church_palette(church)
    return mark_safe(' '.join(f'{name}: {value};' for name, value in palette.items()))
