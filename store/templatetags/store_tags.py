from django import template
from django.utils.safestring import mark_safe

register = template.Library()

@register.simple_tag
def query_transform(request, **kwargs):
    """
    Returns the URL-encoded query string for the current page,
    updating the params with the key/value pairs from the kwargs dict.
    """
    updated = request.GET.copy()
    for key, value in kwargs.items():
        if value is not None:
            updated[key] = value
        else:
            updated.pop(key, None)
    
    return updated.urlencode()

@register.filter
def star_rating(value):
    """
    Convert a numeric rating to star icons.
    """
    full_stars = int(value)
    half_star = value - full_stars >= 0.5
    empty_stars = 5 - full_stars - (1 if half_star else 0)
    
    stars = '<i class="fas fa-star text-warning"></i>' * full_stars
    if half_star:
        stars += '<i class="fas fa-star-half-alt text-warning"></i>'
    stars += '<i class="far fa-star text-warning"></i>' * empty_stars
    
    return mark_safe(stars)

@register.filter
def multiply(value, arg):
    """
    Multiplies the value by the argument
    """
    return int(value) * int(arg)

@register.simple_tag
def set_var(val=None):
    return val

@register.filter
def get_item(dictionary, key):
    if dictionary is None:
        return None
    return dictionary.get(key)

@register.filter
def get_attr(obj, attr):
    if obj is None:
        return None
    return getattr(obj, attr, None)
