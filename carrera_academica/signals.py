# carrera_academica/signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import CarreraAcademica, Formulario


@receiver(post_save, sender=CarreraAcademica)
def crear_formularios_iniciales(sender, instance, created, **kwargs):
    """
    Esta función se ejecuta automáticamente después de guardar una CarreraAcademica.
    Si la CarreraAcademica es nueva (created=True), crea su checklist de formularios.
    """
    if created:
        # 1. Crear Formularios Únicos (esto no cambia)
        for tipo in ["F01", "F02", "F03", "CV"]:
            Formulario.objects.create(carrera_academica=instance, tipo_formulario=tipo)

        # 2. Crear Formularios Anuales (con la nueva lógica)

        # Primero, definimos los formularios que son siempre anuales
        tipos_anuales_base = ["F04", "F05", "F06", "F07", "ENC"]

        # Hacemos una copia para poder modificarla
        formularios_a_crear = list(tipos_anuales_base)

        # Verificamos la dedicación del cargo asociado a la Carrera Académica
        # Los valores 'de' y 'se' corresponden a Dedicación Exclusiva y Semi-Exclusiva
        if instance.cargo.dedicacion in ["de", "se"]:
            formularios_a_crear.append("F13")

        # Obtenemos los años del período
        start_year = instance.fecha_inicio.year
        end_year = instance.fecha_vencimiento_original.year

        # Creamos los formularios correspondientes para cada año
        for anio in range(start_year, end_year + 1):
            for tipo in formularios_a_crear:
                Formulario.objects.create(
                    carrera_academica=instance,
                    tipo_formulario=tipo,
                    anio_correspondiente=anio,
                )
