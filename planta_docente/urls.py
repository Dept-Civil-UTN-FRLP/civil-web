# planta_docente/urls.py
from django.urls import path
from . import views

app_name = 'planta_docente'

urlpatterns = [
    # Dashboard principal
    path('', views.dashboard_planta_view, name='dashboard'),

    # Vista de detalle de cargo
    path('cargo/<int:pk>/', views.detalle_cargo_view, name='detalle_cargo'),

    # Vista de detalle de docente
    path('docente/<int:pk>/', views.detalle_docente_view, name='detalle_docente'),

    # Reportes y filtros
    path('vencimientos/', views.vencimientos_view, name='vencimientos'),
    path('jubilaciones/', views.jubilaciones_view, name='jubilaciones'),
    path('sin-ca/', views.cargos_sin_ca_view, name='sin_ca'),

    # Acciones
    path('cargo/<int:pk>/iniciar-ca/', views.iniciar_ca_desde_cargo_view,
         name='iniciar_ca_desde_cargo'),

    # API endpoints (para AJAX)
    path('api/cargo/<int:pk>/info/',
         views.cargo_info_api_view, name='cargo_info_api'),
]
