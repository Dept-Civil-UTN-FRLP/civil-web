# carrera_academica/signals.py

from django.db.models.signals import post_save, pre_save
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


@receiver(post_save, sender=CarreraAcademica)
def sincronizar_vencimiento_cargo_desde_ca(sender, instance, created, **kwargs):
    """
    Cuando se modifica el vencimiento de una CA activa,
    sincroniza el vencimiento del cargo asociado.
    """
    # No sincronizar en creación (ya se hace en la vista)
    if created:
        return

    # Solo sincronizar si la CA está activa
    if instance.estado != 'ACT':
        return

    # Solo si hay cargo asociado
    if not instance.cargo:
        return

    # Si la CA se prorrogó, prorrogar el cargo también
    if instance.cargo.fecha_vencimiento:
        if instance.fecha_vencimiento_actual > instance.cargo.fecha_vencimiento:
            # Evitar loop infinito: desconectar el signal del cargo temporalmente
            from planta_docente.signals import sincronizar_ca_desde_cargo
            from django.db.models.signals import post_save as cargo_post_save
            from planta_docente.models import Cargo

            cargo_post_save.disconnect(
                sincronizar_ca_desde_cargo, sender=Cargo)

            # Actualizar vencimiento del cargo
            instance.cargo.fecha_vencimiento = instance.fecha_vencimiento_actual
            instance.cargo.save()

            # Reconectar el signal
            cargo_post_save.connect(sincronizar_ca_desde_cargo, sender=Cargo)
