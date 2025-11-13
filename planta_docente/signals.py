from carrera_academica.models import CarreraAcademica
from django.db.models.signals import post_save
from django.dispatch import receiver
from planta_docente.models import Cargo


@receiver(post_save, sender=Cargo)
def sincronizar_vencimiento_ca(sender, instance, **kwargs):
    """
    Cuando se modifica el CARGO, sincroniza la CA.
    Cargo → CA
    """
    # Solo si el cargo tiene CA
    if hasattr(instance, 'carrera_academica') and instance.carrera_academica:
        ca = instance.carrera_academica

        # Si el cargo tiene fecha de vencimiento, sincronizar
        if instance.fecha_vencimiento:
            # Solo actualizar si es diferente (evitar loop infinito)
            if ca.fecha_vencimiento_actual != instance.fecha_vencimiento:
                ca.fecha_vencimiento_actual = instance.fecha_vencimiento
                ca.save(update_fields=['fecha_vencimiento_actual'])


@receiver(post_save, sender=CarreraAcademica)
def sincronizar_vencimiento_cargo(sender, instance, **kwargs):
    """
    Cuando se modifica la CA, sincroniza el CARGO.
    CA → Cargo
    """
    # Obtener el cargo asociado
    cargo = instance.cargo

    # Si la CA tiene fecha de vencimiento, sincronizar
    if instance.fecha_vencimiento_actual:
        # Solo actualizar si es diferente (evitar loop infinito)
        if cargo.fecha_vencimiento != instance.fecha_vencimiento_actual:
            cargo.fecha_vencimiento = instance.fecha_vencimiento_actual
            cargo.save(update_fields=['fecha_vencimiento'])
