from django import template

register = template.Library()


@register.filter
def as_list(value):
    return [value]


@register.filter
def get_item(dictionary, key):
    return dictionary.get(key, "")
