# carrera_academica/managers.py
"""
Managers personalizados con queries optimizados.
"""
from django.db import models


class CarreraAcademicaQuerySet(models.QuerySet):
    """QuerySet optimizado para CarreraAcademica."""

    def with_related_data(self):
        """
        Precarga todas las relaciones necesarias para el dashboard.
        Reduce N+1 queries.
        """
        return self.select_related(
            "cargo",
            "cargo__docente",
            "cargo__asignatura",
            "resolucion_designacion",
            "resolucion_puesta_en_funcion",
        ).prefetch_related(
            "formularios",
            "evaluaciones",
            "cargo__resoluciones",
        )

    def with_full_detail(self):
        """
        Precarga todas las relaciones para la vista de detalle.
        Incluye el jurado y todos los formularios.
        """
        return self.select_related(
            "cargo",
            "cargo__docente",
            "cargo__asignatura",
            "jurado",
            "resolucion_designacion",
            "resolucion_puesta_en_funcion",
        ).prefetch_related(
            "formularios",
            "evaluaciones__formularios",
            "cargo__resoluciones",
        )

    def activas(self):
        """Filtra solo las CA activas."""
        return self.filter(estado="ACT")

    def finalizadas(self):
        """Filtra solo las CA finalizadas."""
        return self.filter(estado="FIN")

    def con_evaluaciones_pendientes(self):
        """Filtra CA que tienen años pendientes de evaluación."""
        from django.utils import timezone

        # Esta es una query compleja, mejor hacerla en la vista
        # pero dejamos el método para documentar la intención
        return self


class CarreraAcademicaManager(models.Manager):
    """Manager personalizado para CarreraAcademica."""

    def get_queryset(self):
        """Override del queryset base."""
        return CarreraAcademicaQuerySet(self.model, using=self._db)

    def with_related_data(self):
        """Proxy al método del QuerySet."""
        return self.get_queryset().with_related_data()

    def with_full_detail(self):
        """Proxy al método del QuerySet."""
        return self.get_queryset().with_full_detail()

    def activas(self):
        """Proxy al método del QuerySet."""
        return self.get_queryset().activas()


class EvaluacionQuerySet(models.QuerySet):
    """QuerySet optimizado para Evaluacion."""

    def with_related_data(self):
        """Precarga relaciones necesarias."""
        return self.select_related(
            "carrera_academica",
            "carrera_academica__cargo",
            "carrera_academica__cargo__docente",
        ).prefetch_related(
            "formularios",
        )


class EvaluacionManager(models.Manager):
    """Manager personalizado para Evaluacion."""

    def get_queryset(self):
        return EvaluacionQuerySet(self.model, using=self._db)

    def with_related_data(self):
        return self.get_queryset().with_related_data()
