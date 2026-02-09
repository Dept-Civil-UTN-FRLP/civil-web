# planta_docente/urls.py
from django.urls import path
from planta_docente import views

app_name = "planta_docente"

urlpatterns = [
    # Dashboard principal
    path("", views.dashboard_planta_view, name="dashboard"),
    # Vista de detalle de cargo
    path("cargo/<int:pk>/", views.detalle_cargo_view, name="detalle_cargo"),
    # Vista de detalle de docente
    path("docente/<int:pk>/", views.detalle_docente_view, name="detalle_docente"),
    # Reportes y filtros
    path("vencimientos/", views.vencimientos_view, name="vencimientos"),
    path("jubilaciones/", views.jubilaciones_view, name="jubilaciones"),
    path("sin-ca/", views.cargos_sin_ca_view, name="sin_ca"),
    # Acciones
    path(
        "cargo/<int:pk>/iniciar-ca/",
        views.iniciar_ca_desde_cargo_view,
        name="iniciar_ca_desde_cargo",
    ),
    # API endpoints (para AJAX)
    path("api/cargo/<int:pk>/info/", views.cargo_info_api_view, name="cargo_info_api"),
    path("renovaciones/", views.cargos_renovacion_view, name="cargos_renovacion"),
    path(
        "renovaciones/cargo/<int:cargo_id>/renovar/",
        views.renovar_cargo_ajax,
        name="renovar_cargo_ajax",
    ),
    path(
        "ajax/crear-resolucion-csu/",
        views.crear_resolucion_csu_ajax,
        name="crear_resolucion_csu_ajax",
    ),
    path(
        "renovaciones/exportar/",
        views.exportar_renovaciones_excel,
        name="exportar_renovaciones_excel",
    ),
    path('cargo/nuevo/', views.crear_cargo_view, name='crear_cargo'),
    path('cargo/<int:pk>/editar/', views.editar_cargo_view, name='editar_cargo'),
    path('cargo/<int:pk>/resoluciones/',
         views.gestionar_resoluciones_cargo,
         name='gestionar_resoluciones_cargo'),

    path('cargo/<int:pk>/resoluciones/crear/',
         views.crear_resolucion_cargo,
         name='crear_resolucion_cargo'),

    path('cargo/<int:cargo_pk>/resoluciones/<int:resolucion_pk>/eliminar/',
         views.eliminar_resolucion_cargo,
         name='eliminar_resolucion_cargo'),
    path(
        "cargo/<int:pk>/editar-licencia-mj/",
        views.editar_licencia_mayor_jerarquia_view,
        name="editar_licencia_mj",
    ),
    
    path('cargo/<int:pk>/licencia/',
         views.gestionar_licencia_cargo,
         name='gestionar_licencia_cargo'),
    path('cargo/<int:pk>/continuidad/',
         views.gestionar_continuidad_cargo,
         name='gestionar_continuidad_cargo'),

    path('docente/<int:docente_pk>/historial-continuidad/',
         views.ver_historial_continuidad_docente,
         name='historial_continuidad_docente'),
    path('cargo/<int:pk>/mayor-jerarquia/',
         views.gestionar_mayor_jerarquia_cargo,
         name='gestionar_mayor_jerarquia_cargo'),
    
    # Estructura de Cátedra
    path('estructura-catedra/', views.dashboard_asignaturas, name='dashboard_asignaturas'),
    path('estructura-catedra/<int:asignatura_id>/formulario/', views.formulario_estructura, name='formulario_estructura'),
    path('estructura-catedra/<int:asignatura_id>/generar-pdf/',
         views.generar_pdf_estructura, name='generar_pdf_estructura'),
    # Funciones Sustantivas
    path('cargo/<int:cargo_pk>/funciones-sustantivas/',
         views.gestionar_funciones_sustantivas,
         name='gestionar_funciones_sustantivas'),
    path('cargo/<int:cargo_pk>/funciones-sustantivas/crear/',
         views.crear_funcion_sustantiva,
         name='crear_funcion_sustantiva'),
    path('funciones-sustantivas/<int:pk>/editar/',
         views.editar_funcion_sustantiva,
         name='editar_funcion_sustantiva'),
    path('funciones-sustantivas/<int:pk>/eliminar/',
         views.eliminar_funcion_sustantiva,
         name='eliminar_funcion_sustantiva'),
    path('funciones-sustantivas/<int:pk>/toggle/',
         views.toggle_activa_funcion_sustantiva,
         name='toggle_activa_funcion_sustantiva'),
    path('api/asignatura/<int:asignatura_id>/info/',
         views.asignatura_info_api,
         name='asignatura_info_api'),
    path('asignatura/<int:asignatura_id>/ficha/',
         views.ver_ficha_asignatura,
         name='ver_ficha_asignatura'),
    path('asignatura/<int:asignatura_id>/ficha/editar/',
         views.editar_ficha_asignatura,
         name='editar_ficha_asignatura'),
    path('planificaciones/', views.dashboard_planificaciones,
         name='dashboard_planificaciones'),
    path('planificaciones/subir/<int:asignatura_id>/',
         views.subir_planificacion, name='subir_planificacion'),
    path('planificaciones/<int:pk>/descargar/',
         views.descargar_planificacion, name='descargar_planificacion'),
    path('planificaciones/<int:pk>/eliminar/',
         views.eliminar_planificacion, name='eliminar_planificacion'),
    path('planificaciones/<int:pk>/preview/',
         views.vista_previa_notificacion, name='preview_notificacion'),
    path('planificaciones/<int:pk>/notificar/', views.notificar_planificacion_individual,
         name='notificar_planificacion_individual'),
    path('planificaciones/notificar-masivo/',
         views.notificar_masivo, name='notificar_masivo'),
    path('planificaciones/crear-y-notificar/',
         views.crear_y_notificar, name='crear_y_notificar'),
    path('planificaciones/gestionar-asignaturas/',
         views.gestionar_asignaturas_año, name='gestionar_asignaturas_año'),
    path('planificaciones/toggle-asignatura/',
         views.toggle_asignatura_año, name='toggle_asignatura_año'),
    # En planta_docente/urls.py
    path('planificaciones/cambiar-responsable/',
         views.cambiar_responsable_planificacion, name='cambiar_responsable_planificacion'),
    path('planificaciones/<int:pk>/aprobar-observar/',
         views.aprobar_observar_planificacion, name='aprobar_observar_planificacion'),
]
