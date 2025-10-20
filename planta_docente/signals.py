# planta_docente/signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Resolucion
from carrera_academica.models import CarreraAcademica


@receiver(post_save, sender=Resolucion)
def procesar_prorroga_por_licencia(sender, instance, created, **kwargs):
    """
    Esta señal se activa cada vez que se guarda una Resolucion.
    Si es una 'Baja de Licencia', calcula y aplica la prórroga correspondiente.
    """
    # Solo actuamos si se crea una nueva resolución de "Baja de Licencia"
    if created and instance.objeto == 'licencia_baja':

        # 1. Obtenemos el cargo y su carrera académica asociada
        cargo = instance.cargo
        try:
            ca = cargo.carrera_academica
        except CarreraAcademica.DoesNotExist:
            return  # Si no hay CA para este cargo, no hacemos nada

        # 2. Buscamos la última "Alta de Licencia" para este mismo cargo
        alta_licencia_res = Resolucion.objects.filter(
            cargo=cargo,
            objeto='licencia_alta'
        ).order_by('-fecha_inicio_licencia').first()

        # 3. Verificamos que todo esté en orden para calcular
        if not alta_licencia_res:
            print(
                f"Alerta: Se creó una baja de licencia para {cargo} pero no se encontró un alta.")
            return

        if not alta_licencia_res.fecha_inicio_licencia or not instance.fecha_fin_licencia:
            print(
                f"Alerta: Faltan fechas en las resoluciones de licencia para {cargo}.")
            return

        # 4. Solo aplicamos la prórroga si la resolución de ALTA lo indicaba
        if alta_licencia_res.genera_prorroga_ca:

            # 5. Calculamos la duración de la licencia
            duracion_licencia = instance.fecha_fin_licencia - \
                alta_licencia_res.fecha_inicio_licencia

            # 6. Aplicamos la prórroga a la fecha de vencimiento actual de la CA
            if ca.fecha_vencimiento_actual:
                print(
                    f"Aplicando prórroga de {duracion_licencia.days} días a la CA de {ca.cargo.docente}.")
                ca.fecha_vencimiento_actual += duracion_licencia
                ca.save()
