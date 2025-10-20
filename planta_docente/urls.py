# planta_docente/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path(
        "asignatura/<int:pk>/", views.detalle_asignatura_view, name="detalle_asignatura"
    ),
]
