# carrera_academica/templatetags/pagination_tags.py
"""
Template tags para paginación.
"""
from django import template
from django.utils.html import format_html
from django.utils.http import urlencode

register = template.Library()


@register.simple_tag(takes_context=True)
def url_replace(context, **kwargs):
    """
    Reemplaza parámetros en la URL actual manteniendo los demás.

    Uso en template:
    <a href="?{% url_replace page=2 %}">Página 2</a>
    """
    query = context["request"].GET.copy()
    for key, value in kwargs.items():
        query[key] = value
    return query.urlencode()


@register.inclusion_tag("components/pagination.html", takes_context=True)
def render_pagination(context, page_obj, show_page_size=True):
    """
    Renderiza los controles de paginación.

    Args:
        page_obj: Objeto de página de Django
        show_page_size: Si mostrar el selector de tamaño de página
    """
    # Obtener rango de páginas
    paginator = page_obj.paginator
    page_number = page_obj.number

    # Calcular rango con elipsis
    page_range = []
    on_each_side = 2
    on_ends = 1
    num_pages = paginator.num_pages

    if num_pages <= 7:
        page_range = list(range(1, num_pages + 1))
    else:
        # Páginas del inicio
        page_range.extend(range(1, min(on_ends + 1, num_pages + 1)))

        # Primera elipsis
        if page_number > (on_each_side + on_ends + 1):
            page_range.append("...")

        # Páginas alrededor de la actual
        start = max(on_ends + 1, page_number - on_each_side)
        end = min(num_pages - on_ends, page_number + on_each_side)
        page_range.extend(range(start, end + 1))

        # Segunda elipsis
        if page_number < (num_pages - on_each_side - on_ends):
            page_range.append("...")

        # Páginas del final
        page_range.extend(
            range(max(num_pages - on_ends + 1, on_ends + 1), num_pages + 1)
        )

    return {
        "page_obj": page_obj,
        "page_range": page_range,
        "show_page_size": show_page_size,
        "request": context["request"],
    }


@register.filter
def multiply(value, arg):
    """Multiplica dos valores."""
    try:
        return int(value) * int(arg)
    except (ValueError, TypeError):
        return ""


@register.filter
def get_page_size_options(paginator):
    """Retorna las opciones de tamaño de página."""
    return [10, 25, 50, 100]
