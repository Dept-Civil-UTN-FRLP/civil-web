from django.urls import path
from . import views

app_name = "digesto"

urlpatterns = [
    # Listados y búsqueda
    path("", views.lista_actas_view, name="lista_actas"),
    path("buscar/", views.buscar_view, name="buscar"),
    path("disposiciones/", views.lista_disposiciones_view, name="lista_disposiciones"),

    # Ciclo Lectivo
    path("ciclo/nuevo/", views.crear_ciclo_view, name="crear_ciclo"),

    # Actas
    path("acta/nueva/", views.crear_acta_view, name="crear_acta"),
    path("acta/<int:pk>/", views.detalle_acta_view, name="detalle_acta"),
    path("acta/<int:pk>/editar/", views.editar_acta_view, name="editar_acta"),

    # Disposiciones
    path("acta/<int:acta_pk>/disposicion/nueva/", views.crear_disposicion_view, name="crear_disposicion"),
    path("disposicion/<int:pk>/", views.detalle_disposicion_view, name="detalle_disposicion"),
    path("disposicion/<int:pk>/editar/", views.editar_disposicion_view, name="editar_disposicion"),

    # Certificaciones
    path("acta/<int:acta_pk>/certificacion/nueva/", views.crear_certificacion_view, name="crear_certificacion"),
    path("certificacion/<int:pk>/editar/", views.editar_certificacion_view, name="editar_certificacion"),
]
