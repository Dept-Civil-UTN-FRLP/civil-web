from django.conf import settings


def modulos_activos(request):
    return {"MODULOS_ACTIVOS": settings.MODULOS_ACTIVOS}
