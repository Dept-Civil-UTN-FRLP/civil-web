# equivalencias/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # La página principal del dashboard
    path("", views.dashboard_view, name="dashboard"),
    # La página de detalle para una solicitud específica
    # <int:pk> es un parámetro dinámico que captura el ID de la solicitud
    path("solicitud/<int:pk>/", views.solicitud_detalle_view, name="solicitud_detalle"),
    path("solicitud/nueva/", views.crear_solicitud_view, name="crear_solicitud"),
    path(
        "solicitud/<int:pk>/generar_pdf/",
        views.generar_acta_pdf_view,
        name="generar_acta_pdf",
    ),
    path(
        "solicitud/<int:pk>/finalizar/",
        views.finalizar_solicitud_view,
        name="finalizar_solicitud",
    ),
    path(
        "solicitud/<int:pk>/reenviar/<int:detalle_pk>/",
        views.reenviar_email_asignatura_view,
        name="reenviar_email_asignatura",
    ),
    path(
        "solicitud/<int:pk>/reenviar_pendientes/",
        views.reenviar_pendientes_view,
        name="reenviar_pendientes",
    ),
    path("estadisticas/", views.estadisticas_view, name="estadisticas"),
]
