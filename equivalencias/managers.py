# equivalencias/managers.py
"""
Managers personalizados para equivalencias.
"""
from django.db import models

class SolicitudEquivalenciaQuerySet(models.QuerySet):
    """QuerySet optimizado para SolicitudEquivalencia."""

    def with_related_data(self):
        """
        Precarga relaciones para el dashboard.
        """
        return self.select_related(
            'id_estudiante',
        ).prefetch_related(
            'detallesolicitud_set',
            'detallesolicitud_set__id_asignatura',
            'detallesolicitud_set__id_asignatura__asignatura',
            'documentoadjunto_set',
        )

    def with_full_detail(self):
        """
        Precarga todo para la vista de detalle.
        """
        
        from .models import DetalleSolicitud

        # 1. Creamos el QuerySet filtrado Y optimizado para los detalles
        # (Asumo que tu modelo se llama 'DetalleSolicitud')
        detalles_qs = DetalleSolicitud.objects.filter(
            id_asignatura__asignatura__isnull=False,
            id_asignatura__docente_responsable__isnull=False
        ).select_related(
            'id_asignatura__asignatura',
            'id_asignatura__docente_responsable'
        ).prefetch_related(
            'id_asignatura__docente_responsable__correos'
        )

        # 2. Creamos el objeto Prefetch
        prefetch_detalles = models.Prefetch(
            'detallesolicitud_set',
            queryset=detalles_qs
        )

        # 3. Lo usamos en el queryset principal
        return self.select_related(
            'id_estudiante',
        ).prefetch_related(
            prefetch_detalles,  # <-- El Prefetch corregido
            'documentoadjunto_set',
        )

    def en_proceso(self):
        """Filtra solo las solicitudes en proceso."""
        return self.filter(estado_general='En Proceso')

    def completadas(self):
        """Filtra solo las solicitudes completadas."""
        return self.filter(estado_general='Completada')


class SolicitudEquivalenciaManager(models.Manager):
    """Manager personalizado para SolicitudEquivalencia."""

    def get_queryset(self):
        return SolicitudEquivalenciaQuerySet(self.model, using=self._db)

    def with_related_data(self):
        return self.get_queryset().with_related_data()

    def with_full_detail(self):
        return self.get_queryset().with_full_detail()

    def en_proceso(self):
        return self.get_queryset().en_proceso()

    def completadas(self):
        return self.get_queryset().completadas()
