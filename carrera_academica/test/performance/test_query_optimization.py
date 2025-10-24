# carrera_academica/tests/performance/test_query_optimization.py
"""
Tests de performance para verificar optimizaciones.
"""
from django.test import TestCase, override_settings
from django.db import connection, reset_queries

from carrera_academica.models import CarreraAcademica
from planta_docente.models import Cargo, Docente, Asignatura
from datetime import date


@override_settings(DEBUG=True)
class QueryOptimizationTestCase(TestCase):
    """Tests para verificar la optimización de queries."""

    @classmethod
    def setUpTestData(cls):
        """Crear datos de prueba una sola vez."""
        # Crear 10 docentes
        for i in range(10):
            Docente.objects.create(
                nombre=f"docente{i}",
                apellido=f"apellido{i}",
                documento=10000000 + i,
                legajo=1000 + i,
                fecha_nacimiento=date(1980, 1, 1)
            )

        # Crear 5 asignaturas
        for i in range(5):
            Asignatura.objects.create(
                nombre=f"asignatura{i}",
                nivel="i",
                departamento="civil",
                especialidad="civil",
                hora_semanal=4,
                hora_total=96,
                dictado="a"
            )

        # Crear 20 cargos
        docentes = list(Docente.objects.all())
        asignaturas = list(Asignatura.objects.all())

        for i in range(10):
            Cargo.objects.create(
                docente=docentes[i % 10],
                asignatura=asignaturas[i % 5],
                caracter="reg",
                categoria="adj",
                dedicacion="ds",
                cantidad_horas=8,
                fecha_inicio=date(2020, 1, 1),
                fecha_vencimiento=date(2025, 1, 1)
            )

        # Crear 10 CA
        cargos = list(Cargo.objects.all()[:10])
        for cargo in cargos:
            CarreraAcademica.objects.create(
                cargo=cargo,
                fecha_inicio=date(2020, 1, 1),
                fecha_vencimiento_original=date(2025, 1, 1),
                fecha_vencimiento_actual=date(2025, 1, 1)
            )

    def test_dashboard_query_count_without_optimization(self):
        """Test que dashboard sin optimización hace muchas queries."""
        reset_queries()

        # Simular dashboard sin optimización
        carreras = list(CarreraAcademica.objects.all())
        for ca in carreras:
            _ = ca.cargo.docente.nombre
            _ = ca.cargo.asignatura.nombre

        query_count = len(connection.queries)

        # Sin optimización, esperamos al menos 1 + 10 + 10 = 21 queries
        self.assertGreaterEqual(
            query_count,
            20,
            f"Sin optimización deberían ser más queries. Actual: {query_count}"
        )

    def test_dashboard_query_count_with_optimization(self):
        """Test que dashboard optimizado hace pocas queries."""
        reset_queries()

        # Simular dashboard con optimización
        carreras = list(CarreraAcademica.objects.with_related_data())
        for ca in carreras:
            _ = ca.cargo.docente.nombre
            _ = ca.cargo.asignatura.nombre

        query_count = len(connection.queries)

        # Con optimización, esperamos máximo 5 queries
        self.assertLessEqual(
            query_count,
            5,
            f"Con optimización deberían ser menos de 5 queries. Actual: {query_count}"
        )

    def test_detail_query_count_without_optimization(self):
        """Test que detalle sin optimización hace muchas queries."""
        ca = CarreraAcademica.objects.first()
        reset_queries()

        # Simular acceso a relaciones
        _ = ca.cargo.docente
        _ = ca.cargo.asignatura
        _ = list(ca.formularios.all())
        _ = list(ca.evaluaciones.all())
        _ = list(ca.cargo.resoluciones.all())

        query_count = len(connection.queries)

        # Sin optimización, esperamos al menos 5 queries
        self.assertGreaterEqual(
            query_count,
            5,
            f"Sin optimización deberían ser más queries. Actual: {query_count}"
        )

    def test_detail_query_count_with_optimization(self):
        """Test que detalle optimizado hace pocas queries."""
        reset_queries()

        # Obtener con optimización
        ca = CarreraAcademica.objects.with_full_detail().first()

        # Simular acceso a relaciones
        _ = ca.cargo.docente
        _ = ca.cargo.asignatura
        _ = list(ca.formularios.all())
        _ = list(ca.evaluaciones.all())
        _ = list(ca.cargo.resoluciones.all())

        query_count = len(connection.queries)

        # Con optimización, esperamos máximo 8 queries
        self.assertLessEqual(
            query_count,
            8,
            f"Con optimización deberían ser menos de 8 queries. Actual: {query_count}"
        )
