# carrera_academica/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("", views.dashboard_ca_view, name="dashboard_ca"),
    path("expediente/<int:pk>/", views.detalle_ca_view, name="detalle_ca"),
    path(
        "expediente/<int:pk>/iniciar_evaluacion/",
        views.iniciar_evaluacion_view,
        name="iniciar_evaluacion",
    ),
    path(
        "expediente/<int:pk>/registrar_resolucion/",
        views.registrar_resolucion_view,
        name="registrar_resolucion",
    ),
    path("nueva/", views.crear_ca_view, name="crear_ca"),
    path(
        "expediente/<int:pk>/editar_junta/",
        views.editar_junta_view,
        name="editar_junta",
    ),
    path(
        "expediente/<int:pk>/asignar_expediente/",
        views.asignar_expediente_view,
        name="asignar_expediente",
    ),
    path(
        "api/docentes_filtrados/",
        views.docentes_filtrados_api_view,
        name="api_docentes_filtrados",
    ),
    path(
        "expediente/<int:pk>/finalizar/", views.finalizar_ca_view, name="finalizar_ca"
    ),
    path(
        "expediente/<int:pk>/consolidar_pdf/",
        views.consolidar_pdf_view,
        name="consolidar_pdf",
    ),
    path(
        "expediente/<int:pk>/generar_propuesta_jurado/",
        views.generar_propuesta_jurado_view,
        name="generar_propuesta_jurado",
    ),
    path(
        "expediente/<int:pk>/notificar_pendientes/",
        views.notificar_pendientes_view,
        name="notificar_pendientes",
    ),
    path(
        "formulario/<int:pk>/descargar_plantilla/",
        views.descargar_plantilla_view,
        name="descargar_plantilla",
    ),
    path(
        "evaluacion/<int:pk>/notificar_junta/",
        views.notificar_junta_view,
        name="notificar_junta",
    ),
    path(
        "evaluacion/<int:pk>/agendar/",
        views.agendar_evaluacion_view,
        name="agendar_evaluacion",
    ),
]
