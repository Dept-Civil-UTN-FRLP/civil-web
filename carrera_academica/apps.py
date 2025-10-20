# carrera_academica/apps.py
from django.apps import AppConfig


class CarreraAcademicaConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "carrera_academica"

    def ready(self):
        import carrera_academica.signals  # <-- AÑADE ESTA LÍNEA
