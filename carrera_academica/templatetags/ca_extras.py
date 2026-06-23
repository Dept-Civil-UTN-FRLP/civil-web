from django import template

register = template.Library()


@register.filter
def as_list(value):
    return [value]


@register.filter
def get_item(dictionary, key):
    return dictionary.get(key, "")


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
