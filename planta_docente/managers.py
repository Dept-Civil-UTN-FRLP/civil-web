# planta_docente/managers.py
"""
Managers personalizados para consultas optimizadas de planta docente.

Este módulo contiene QuerySets y Managers personalizados para los modelos
Cargo y Docente, proporcionando métodos de consulta reutilizables y optimizados.
"""
from datetime import timedelta

from django.db import models
from django.db.models import Q
from django.utils import timezone


class CargoQuerySet(models.QuerySet):
    """
    QuerySet personalizado para el modelo Cargo.

    Proporciona métodos de consulta optimizados para:
    - Filtrado por estado (activo, licencia, baja)
    - Filtrado por tipo de cargo (regular, ordinario, interino, ad-honorem)
    - Consultas de vencimiento
    - Relación con Carrera Académica
    """

    def with_related_data(self):
        """
        Precarga todas las relaciones necesarias para el dashboard.

        Optimiza las queries usando select_related y prefetch_related
        para evitar el problema N+1.

        Returns:
            QuerySet: QuerySet con relaciones precargadas
        """
        return self.select_related(
            "docente",
            "asignatura",
        ).prefetch_related(
            "resoluciones",
            "docente__correos",
        )

    def activos(self):
        """
        Filtra solo los cargos con estado 'activo'.

        Returns:
            QuerySet: Cargos activos
        """
        return self.filter(estado="activo")

    def en_licencia(self):
        """
        Filtra solo los cargos con estado 'licencia'.

        Returns:
            QuerySet: Cargos en licencia
        """
        return self.filter(estado="licencia")

    def dados_de_baja(self):
        """
        Filtra solo los cargos con estado 'baja'.

        Returns:
            QuerySet: Cargos dados de baja
        """
        return self.filter(estado="baja")

    def regulares_ordinarios(self):
        """
        Filtra solo los cargos Regulares u Ordinarios.

        Estos son los únicos tipos de cargo que pueden tener
        Carrera Académica asociada.

        Returns:
            QuerySet: Cargos regulares u ordinarios
        """
        return self.filter(caracter__in=["reg", "ord"])

    def con_carrera_academica(self):
        """
        Filtra cargos que tienen una Carrera Académica asociada.

        Returns:
            QuerySet: Cargos con CA
        """
        return self.filter(carrera_academica__isnull=False)

    def sin_carrera_academica(self):
        """
        Filtra cargos Regulares u Ordinarios que NO tienen CA.

        Útil para identificar cargos que deberían iniciar su CA.

        Returns:
            QuerySet: Cargos reg/ord sin CA
        """
        return self.filter(caracter__in=["reg", "ord"], carrera_academica__isnull=True)

    def proximos_a_vencer(self, dias=180):
        """
        Filtra cargos que vencen en los próximos N días.

        Args:
            dias (int): Cantidad de días hacia adelante para buscar.
                       Por defecto 180 días (6 meses)

        Returns:
            QuerySet: Cargos próximos a vencer

        Example:
            # Cargos que vencen en los próximos 90 días
            Cargo.objects.proximos_a_vencer(90)
        """
        fecha_limite = timezone.now().date() + timedelta(days=dias)
        return self.filter(
            estado="activo",
            fecha_vencimiento__isnull=False,
            fecha_vencimiento__lte=fecha_limite,
            fecha_vencimiento__gte=timezone.now().date(),
        )

    def vencidos(self):
        """
        Filtra cargos cuya fecha de vencimiento ya pasó.
        EXCLUYE cargos en licencia por mayor jerarquía (tienen vencimiento suspendido).
        """
        return self.filter(
            fecha_vencimiento__isnull=False,
            fecha_vencimiento__lt=timezone.now().date(),
            en_licencia_mayor_jerarquia=False 
        )

    def por_departamento(self, departamento):
        """
        Filtra cargos por departamento de la asignatura.

        Args:
            departamento (str): Código del departamento
                               ('civil', 'electrica', etc.)

        Returns:
            QuerySet: Cargos del departamento especificado
        """
        return self.filter(asignatura__departamento=departamento)

    def por_dedicacion(self, dedicacion):
        """
        Filtra cargos por tipo de dedicación.

        Args:
            dedicacion (str): Tipo de dedicación ('ds', 'se', 'de')

        Returns:
            QuerySet: Cargos con la dedicación especificada
        """
        return self.filter(dedicacion=dedicacion)

    def por_categoria(self, categoria):
        """
        Filtra cargos por categoría docente.

        Args:
            categoria (str): Categoría ('tit', 'aso', 'adj', 'jtp', etc.)

        Returns:
            QuerySet: Cargos con la categoría especificada
        """
        return self.filter(categoria=categoria)

    def sin_ca(self):
        """
        Filtra los cargos que NO tienen una carrera académica asociada.
        """
        # Asume que el campo se llama 'carrera_academica'
        return self.filter(carrera_academica__isnull=True)


class CargoManager(models.Manager):
    """
    Manager personalizado para el modelo Cargo.

    Proporciona acceso a los métodos del QuerySet personalizado
    directamente desde Cargo.objects.
    """

    def get_queryset(self):
        """
        Override del queryset base para usar CargoQuerySet.

        Returns:
            CargoQuerySet: QuerySet personalizado
        """
        return CargoQuerySet(self.model, using=self._db)

    def with_related_data(self):
        """Proxy al método del QuerySet."""
        return self.get_queryset().with_related_data()

    def activos(self):
        """Proxy al método del QuerySet."""
        return self.get_queryset().activos()

    def en_licencia(self):
        """Proxy al método del QuerySet."""
        return self.get_queryset().en_licencia()

    def regulares_ordinarios(self):
        """Proxy al método del QuerySet."""
        return self.get_queryset().regulares_ordinarios()

    def proximos_a_vencer(self, dias=180):
        """Proxy al método del QuerySet."""
        return self.get_queryset().proximos_a_vencer(dias)

    def vencidos(self):
        """Proxy al método del QuerySet."""
        return self.get_queryset().vencidos()

    def con_ca(self):
        """Proxy al método del QuerySet."""
        return self.get_queryset().con_carrera_academica()

    def sin_ca(self):
        """Proxy al método del QuerySet."""
        return self.get_queryset().sin_carrera_academica()


class DocenteQuerySet(models.QuerySet):
    """
    QuerySet personalizado para el modelo Docente.

    Proporciona métodos de consulta optimizados para:
    - Filtrado por estado de cargos
    - Consultas relacionadas con jubilación
    - Cálculos de edad
    """

    def with_related_data(self):
        """
        Precarga todas las relaciones necesarias.

        Returns:
            QuerySet: QuerySet con relaciones precargadas
        """
        return self.prefetch_related(
            "correos",
            "cargo_docente",
            "cargo_docente__asignatura",
            "cargo_docente__carrera_academica",
        )

    def con_cargos_activos(self):
        """
        Filtra docentes que tienen al menos un cargo activo.

        Returns:
            QuerySet: Docentes con cargos activos
        """
        return self.filter(cargo_docente__estado="activo").distinct()

    def activos(self):
        """
        Filtra docentes que NO están jubilados.

        Útil para reportes de planta activa.

        Returns:
            QuerySet: Docentes activos (no jubilados)
        """
        return self.filter(jubilado=False)

    def jubilados(self):
        """
        Filtra docentes que están jubilados.

        Returns:
            QuerySet: Docentes jubilados
        """
        return self.filter(jubilado=True)

    def proximos_a_jubilarse(self, años=2):
        """
        Filtra docentes que cumplen edad de jubilación en los próximos N años.

        Considera dos edades de jubilación:
        - 65 años: Edad ordinaria de jubilación
        - 70 años: Edad límite con prórroga

        Args:
            años (int): Cantidad de años hacia adelante para buscar.
                       Por defecto 2 años

        Returns:
            QuerySet: Docentes próximos a jubilarse

        Example:
            # Docentes que se jubilan en el próximo año
            Docente.objects.proximos_a_jubilarse(1)
        """
        hoy = timezone.now().date()
        fecha_limite = hoy + timedelta(days=años * 365)

        # Rango de fechas de nacimiento para quienes cumplen 65 en el período
        nacimiento_65_min = hoy - timedelta(days=65 * 365)
        nacimiento_65_max = fecha_limite - timedelta(days=65 * 365)

        # Rango de fechas de nacimiento para quienes cumplen 70 en el período
        nacimiento_70_min = hoy - timedelta(days=70 * 365)
        nacimiento_70_max = fecha_limite - timedelta(days=70 * 365)

        return self.filter(
            Q(fecha_nacimiento__range=(nacimiento_70_min, nacimiento_70_max))
            | Q(fecha_nacimiento__range=(nacimiento_65_min, nacimiento_65_max))
        ).filter(jubilado=False)

    def mayores_de_65(self):
        """
        Filtra docentes que ya tienen 65 años o más.

        Returns:
            QuerySet: Docentes de 65 años o más
        """
        fecha_65_anios = timezone.now().date() - timedelta(days=65 * 365)
        return self.filter(fecha_nacimiento__lte=fecha_65_anios, jubilado=False)

    def mayores_de_70(self):
        """
        Filtra docentes que ya tienen 70 años o más.

        Returns:
            QuerySet: Docentes de 70 años o más
        """
        fecha_70_anios = timezone.now().date() - timedelta(days=70 * 365)
        return self.filter(fecha_nacimiento__lte=fecha_70_anios, jubilado=False)


class DocenteManager(models.Manager):
    """
    Manager personalizado para el modelo Docente.

    Proporciona acceso a los métodos del QuerySet personalizado
    directamente desde Docente.objects.
    """

    def get_queryset(self):
        """
        Override del queryset base para usar DocenteQuerySet.

        Returns:
            DocenteQuerySet: QuerySet personalizado
        """
        return DocenteQuerySet(self.model, using=self._db)

    def with_related_data(self):
        """Proxy al método del QuerySet."""
        return self.get_queryset().with_related_data()

    def con_cargos_activos(self):
        """Proxy al método del QuerySet."""
        return self.get_queryset().con_cargos_activos()

    def activos(self):
        """Proxy al método del QuerySet."""
        return self.get_queryset().activos()

    def jubilados(self):
        """Proxy al método del QuerySet."""
        return self.get_queryset().jubilados()

    def proximos_a_jubilarse(self, años=2):
        """Proxy al método del QuerySet."""
        return self.get_queryset().proximos_a_jubilarse(años)

    def mayores_de_65(self):
        """Proxy al método del QuerySet."""
        return self.get_queryset().mayores_de_65()

    def mayores_de_70(self):
        """Proxy al método del QuerySet."""
        return self.get_queryset().mayores_de_70()
