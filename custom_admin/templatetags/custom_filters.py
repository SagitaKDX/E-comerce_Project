from django import template
from django.utils import timezone
import re

register = template.Library()

@register.filter
def timesince_hours(value):
    """
    Returns the number of hours since the given datetime.
    """
    if not value:
        return 0
    
    now = timezone.now()
    diff = now - value
    hours = diff.total_seconds() / 3600
    return hours 

@register.filter
def split(value, arg):
    """
    Splits a string by the given separator and returns a list.
    
    Example:
    {% with items=value|split:"," %}
        {% for item in items %}
            {{ item }}
        {% endfor %}
    {% endwith %}
    """
    return value.split(arg)

@register.filter
def trim(value):
    """
    Trims whitespace from the beginning and end of a string.
    
    Example:
    {{ value|trim }}
    """
    return value.strip() if value else value 