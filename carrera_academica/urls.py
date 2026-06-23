# carrera_academica/urls.py
from django.urls import path
from . import views

app_name = 'carrera_academica'

urlpatterns = [
    path("", views.dashboard_ca_view, name="dashboard_ca"),
    path("historial/", views.historial_ca_view, name="historial_ca"),
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
        "expediente/<int:pk>/desvincular_resolucion/<str:campo>/",
        views.desvincular_resolucion_ca_view,
        name="desvincular_resolucion_ca",
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
    path("expediente/<int:pk>/notificar_pendientes/", views.notificar_pendientes_view, name="notificar_pendientes"),
    path("formulario/<int:pk>/descargar_plantilla/", views.descargar_plantilla_view, name="descargar_plantilla"),
    path("evaluacion/<int:pk>/notificar_junta/", views.notificar_junta_view, name="notificar_junta"),
    path("evaluacion/<int:pk>/agendar/", views.agendar_evaluacion_view, name="agendar_evaluacion"),
    path("expediente/<int:pk>/gestionar-anios/", views.gestionar_anios_ca_view, name="gestionar_anios_ca"),
    path("expediente/<int:pk>/anio/<int:anio>/formularios/", views.gestionar_formularios_anio_view, name="gestionar_formularios_anio"),
    path('ca/<int:pk>/archivar/', views.archivar_ca_view, name='archivar_ca'),
    path('ca/<int:pk>/gestionar-archivada/', views.gestionar_ca_archivada_view, name='gestionar_ca_archivada'),
    path('formulario/<int:pk>/borrar-archivo/', views.borrar_archivo_formulario_view, name='borrar_archivo_formulario'),
    path(
        'expediente/<int:ca_pk>/formulario/<int:formulario_pk>/subir/',
        views.subir_formulario_view,
        name='subir_formulario',
    ),
    # ===== JURADOS =====
    path('jurados/', views.lista_jurados_view, name='lista_jurados'),
    path('jurados/crear/', views.crear_jurado_view, name='crear_jurado'),
    path('jurados/<int:pk>/', views.detalle_jurado_view, name='detalle_jurado'),
    path('jurados/<int:pk>/editar/', views.editar_jurado_view, name='editar_jurado'),
    path('jurados/<int:pk>/planilla/', views.descargar_planilla_jurado_view, name='descargar_planilla_jurado'),
    path('ca/<int:ca_pk>/asignar-jurado/', views.asignar_jurado_ca_view, name='asignar_jurado_ca'),

    # ===== VEEDORES =====
    path('veedores/graduados/', views.lista_veedores_graduados_view, name='lista_veedores_graduados'),
    path('veedores/graduados/crear/', views.crear_veedor_graduado_view, name='crear_veedor_graduado'),
    path('veedores/estudiantes/', views.lista_veedores_estudiantes_view, name='lista_veedores_estudiantes'),
    path('veedores/estudiantes/crear/', views.crear_veedor_estudiante_view, name='crear_veedor_estudiante'),
    path('veedores/graduados/ajax/', views.crear_veedor_graduado_ajax, name='crear_veedor_graduado_ajax'),
    path('veedores/estudiantes/ajax/', views.crear_veedor_estudiante_ajax, name='crear_veedor_estudiante_ajax'),
    # ===== JURADOS EXTERNOS =====
    path('jurados-externos/', views.lista_jurados_externos_view,
         name='lista_jurados_externos'),
    path('jurados-externos/crear/', views.crear_jurado_externo_view,
         name='crear_jurado_externo'),
    path('jurados-externos/<int:pk>/', views.detalle_jurado_externo_view,
         name='detalle_jurado_externo'),
    path('jurados-externos/<int:pk>/editar/',
         views.editar_jurado_externo_view, name='editar_jurado_externo'),
    path('jurados-externos/ajax/', views.crear_jurado_externo_ajax,
         name='crear_jurado_externo_ajax'),

    # ===== UNIVERSIDADES =====
    path('universidades/', views.lista_universidades_view,
         name='lista_universidades'),
    path('universidades/crear/', views.crear_universidad_view,
         name='crear_universidad'),
    path('universidades/<int:pk>/editar/',
         views.editar_universidad_view, name='editar_universidad'),
]
