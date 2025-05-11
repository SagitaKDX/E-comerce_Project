from django import template
import datetime

register = template.Library()

@register.filter
def timedelta(value):
    """Format a timedelta object into a human-readable string"""
    if not value or not isinstance(value, datetime.timedelta):
        return "0 min"
    
    total_seconds = int(value.total_seconds())
    
    # Format as hours and minutes if more than 60 minutes
    if total_seconds >= 3600:
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        return f"{hours}h {minutes}m"
    # Format as minutes if less than 60 minutes
    elif total_seconds >= 60:
        minutes = total_seconds // 60
        return f"{minutes}m"
    # Format as seconds if less than 60 seconds
    else:
        return f"{total_seconds}s"

@register.filter
def percentage(value, total):
    """Calculate percentage of a value against a total"""
    if not value or not total or total == 0:
        return 0
    
    return round((value / total) * 100, 1) 