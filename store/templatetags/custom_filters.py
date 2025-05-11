from django import template
import decimal

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Get item from dictionary by key"""
    return dictionary.get(key, [])

@register.filter
def get_dict_item(dictionary, key):
    """Get item from dictionary by key"""
    if not dictionary:
        return None
    
    # Handle string keys that might be quoted
    if isinstance(key, str) and key.startswith("'") and key.endswith("'"):
        key = key[1:-1]
    elif isinstance(key, str) and key.startswith('"') and key.endswith('"'):
        key = key[1:-1]
    
    return dictionary.get(key, None)

@register.filter
def multiply(value, arg):
    """Multiply the value by the argument"""
    try:
        return value * arg
    except (TypeError, decimal.InvalidOperation):
        return value 