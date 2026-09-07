from django.conf import settings

DEPARTAMENTO_LABELS = {
    "civil": "Depto Ing. Civil",
    "industrial": "Depto Ing. Industrial",
}


def modulos_activos(request):
    departamento = settings.DEPARTAMENTO
    return {
        "MODULOS_ACTIVOS": settings.MODULOS_ACTIVOS,
        "DEPARTAMENTO": departamento,
        "DEPARTAMENTO_LABEL": DEPARTAMENTO_LABELS.get(departamento, departamento.title()),
        "PORTAL_JURADOS_ENABLED": settings.PORTAL_JURADOS_ENABLED,
    }
