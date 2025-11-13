# planta_docente/urls.py
from django.urls import path

from . import views

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
    
    path('cargo/<int:pk>/licencia/',
         views.gestionar_licencia_cargo,
         name='gestionar_licencia_cargo'),
    path('cargo/<int:pk>/continuidad/',
         views.gestionar_continuidad_cargo,
         name='gestionar_continuidad_cargo'),

    path('docente/<int:docente_pk>/historial-continuidad/',
         views.ver_historial_continuidad_docente,
         name='historial_continuidad_docente'),
]
