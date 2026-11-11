from decimal import Decimal

from django import template
from django.utils.safestring import mark_safe

from core.icons import svg
from core.roles import has_role as _has_role

register = template.Library()


@register.filter
def has_role(user, roles: str) -> bool:
    """Usage: {% if user|has_role:"Owner,Manager" %}"""
    return _has_role(user, *[r.strip() for r in roles.split(",") if r.strip()])


@register.filter
def money(value) -> str:
    """Format a Decimal as money with two places and thousands separators."""
    if value in (None, ""):
        return ""
    return f"{Decimal(value):,.2f}"


@register.simple_tag
def icon(name: str, size: int = 20, css: str = ""):
    """Usage: {% icon "calendar" %} or {% icon "check" 16 "text-ok" %}"""
    return mark_safe(svg(name, size, css))  # noqa: S308 - fixed, trusted SVG markup


@register.filter
def initials(user) -> str:
    name = (user.get_full_name() or user.get_username() or "?").split()
    return "".join(part[0] for part in name[:2]).upper()


@register.filter
def percent(value) -> str:
    """0.045 → "4.5%", 0.12 → "12%". Exact, unlike {% widthratio %} which rounds."""
    if value in (None, ""):
        return ""
    pct = (Decimal(value) * 100).quantize(Decimal("0.01")).normalize()
    return f"{pct:f}%"


@register.simple_tag(takes_context=True)
def query_with(context, **kwargs) -> str:
    """Current query string with some keys replaced (used to keep filters while paging)."""
    params = context["request"].GET.copy()
    for key, value in kwargs.items():
        params[key] = value
    return params.urlencode()
