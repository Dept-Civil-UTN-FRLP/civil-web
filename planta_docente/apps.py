from django.apps import AppConfig


class PlantaDocenteConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "planta_docente"

    def ready(self):
        import planta_docente.signals
