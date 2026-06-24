from django import template

register = template.Library()


@register.filter
def as_list(value):
    return [value]


@register.filter
def get_item(dictionary, key):
    return dictionary.get(key, "")


@register.simple_tag(takes_context=True)
def sort_url(context, field):
    """Devuelve URL con ordering toggleado para el campo dado, preservando otros params."""
    request = context["request"]
    params = request.GET.copy()
    current = params.get("ordering", "")
    if current == field:
        params["ordering"] = "-" + field
    else:
        params["ordering"] = field
    return "?" + params.urlencode()


@register.simple_tag
def sort_arrow(ordering, field):
    """Devuelve flecha de dirección si la columna está activa."""
    if ordering == field:
        return "↑"
    if ordering == "-" + field:
        return "↓"
    return ""


_CAL_COLOR = {
    "INS": "text-danger",
    "REG": "text-warning",
    "BUE": "text-success",
    "MBU": "text-success",
    "EXC": "text-success",
}

_CAL_LABEL = dict([
    ("INS", "Insuficiente"),
    ("REG", "Regular"),
    ("BUE", "Bueno"),
    ("MBU", "Muy Bueno"),
    ("EXC", "Excelente"),
])

@register.simple_tag
def fraccion_color(entregados, debidos):
    """Clase Bootstrap para colorear la fracción X/Y de formularios."""
    if not debidos:
        return "text-muted"
    if entregados == 0:
        return "text-danger"
    if entregados >= debidos:
        return "text-success"
    return "text-warning"


@register.filter
def eval_circles(evaluaciones):
    """Devuelve lista de dicts {color, title} por evaluación, mínimo 2 entradas."""
    circles = []
    for ev in evaluaciones:
        cal = ev.calificacion
        circles.append({
            "color": _CAL_COLOR.get(cal, "text-secondary"),
            "title": f"Eval. {ev.numero_evaluacion}: {_CAL_LABEL.get(cal, 'Pendiente')}",
        })
    while len(circles) < 2:
        circles.append({"color": "text-secondary", "title": "Pendiente"})
    return circles
