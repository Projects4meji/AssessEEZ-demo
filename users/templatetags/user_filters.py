from django import template

register = template.Library()

@register.filter
def split(value, separator):
    if not value:
        return []
    return value.split(separator)

@register.filter
def trim(value):
    return value.strip() if value else ''