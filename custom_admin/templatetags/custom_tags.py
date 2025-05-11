from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """
    Allow dictionary access in Django templates
    Usage example: {{ my_dict|get_item:key_var }}
    """
    if dictionary is None:
        return None
    return dictionary.get(key)

@register.filter
def add_class(field, css_class):
    """
    Add a CSS class to a form field
    Usage example: {{ form.field|add_class:"form-control" }}
    """
    if field:
        if 'class' in field.field.widget.attrs:
            field.field.widget.attrs['class'] += f" {css_class}"
        else:
            field.field.widget.attrs['class'] = css_class
    return field

@register.filter
def attr(field, attr_value):
    """
    Add a custom attribute to a form field
    Usage example: {{ form.field|attr:"min:1" }}
    """
    if field and attr_value:
        parts = attr_value.split(":", 1)
        if len(parts) == 2:
            attr_name, value = parts
            field.field.widget.attrs[attr_name] = value
    return field 