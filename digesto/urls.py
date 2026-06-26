from django.urls import path
from . import views

app_name = "digesto"

urlpatterns = [
    path("", views.lista_actas_view, name="lista_actas"),
    path("buscar/", views.buscar_view, name="buscar"),
    path("disposiciones/", views.lista_disposiciones_view, name="lista_disposiciones"),
    path("acta/<int:pk>/", views.detalle_acta_view, name="detalle_acta"),
    path("disposicion/<int:pk>/", views.detalle_disposicion_view, name="detalle_disposicion"),
]
