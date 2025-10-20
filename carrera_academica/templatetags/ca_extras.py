from django import template

register = template.Library()


@register.filter
def as_list(value):
    return [value]
