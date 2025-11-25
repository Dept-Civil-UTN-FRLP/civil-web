from django import template

register = template.Library()


@register.filter
def lookup(dictionary, key):
    """Permite acceder a valores de diccionario en templates"""
    return dictionary.get(key, [])
