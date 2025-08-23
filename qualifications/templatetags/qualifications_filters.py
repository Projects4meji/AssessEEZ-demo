from django import template
from uuid import UUID

register = template.Library()

@register.filter
def lookup(dictionary, key):
    if dictionary is None or key is None:
        return None
    if not isinstance(dictionary, dict):
        return None
    key = str(key)  # Convert key to string to match submission_dict keys
    return dictionary.get(key)  # Return raw object