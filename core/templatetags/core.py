from decimal import Decimal

from django import template

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


@register.simple_tag(takes_context=True)
def query_with(context, **kwargs) -> str:
    """Current query string with some keys replaced (used to keep filters while paging)."""
    params = context["request"].GET.copy()
    for key, value in kwargs.items():
        params[key] = value
    return params.urlencode()
