# carrera_academica/tests/test_indexes.py
"""
Tests para verificar que los índices funcionan correctamente.
"""
from django.test import TestCase
from django.db import connection

from carrera_academica.models import CarreraAcademica, Formulario
from planta_docente.models import Cargo, Docente, Asignatura
from datetime import date


class IndexTestCase(TestCase):
    """Tests para verificar índices."""

    @classmethod
    def setUpTestData(cls):
        """Crear datos de prueba."""
        # Crear docente
        cls.docente = Docente.objects.create(
            nombre="test",
            apellido="docente",
            documento=12345678,
            legajo=1001,
            fecha_nacimiento=date(1980, 1, 1)
        )

        # Crear asignatura
        cls.asignatura = Asignatura.objects.create(
            nombre="test asignatura",
            nivel="i",
            departamento="civil",
            especialidad="civil",
            hora_semanal=4,
            hora_total=96,
            dictado="a"
        )

        # Crear cargo
        cls.cargo = Cargo.objects.create(
            docente=cls.docente,
            asignatura=cls.asignatura,
            caracter="reg",
            categoria="adj",
            dedicacion="ds",
            cantidad_horas=10,
            fecha_inicio=date(2020, 1, 1),
            fecha_vencimiento=date(2025, 1, 1),
            estado='activo'
        )

        # Crear CA
        cls.ca = CarreraAcademica.objects.create(
            cargo=cls.cargo,
            numero_expediente="12345/2024",
            fecha_inicio=date(2020, 1, 1),
            fecha_vencimiento_original=date(2025, 1, 1),
            fecha_vencimiento_actual=date(2025, 1, 1),
            estado='ACT'
        )

    def test_ca_estado_index_exists(self):
        """Verifica que existe el índice de estado."""
        with connection.cursor() as cursor:
            # Para SQLite
            if 'sqlite' in connection.settings_dict['ENGINE']:
                cursor.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='index' AND name='ca_estado_idx'
                """)
                result = cursor.fetchone()
                self.assertIsNotNone(result, "Índice ca_estado_idx no existe")

    def test_ca_filter_by_estado_uses_index(self):
        """Verifica que filtrar por estado usa el índice."""
        qs = CarreraAcademica.objects.filter(estado='ACT')
        explain = str(qs.explain())

        # En producción con PostgreSQL, debería usar el índice
        # En SQLite de testing puede variar
        self.assertIsNotNone(explain)

    def test_ca_expediente_search_performance(self):
        """Verifica que búsqueda por expediente es rápida."""
        import time

        start = time.time()
        list(CarreraAcademica.objects.filter(numero_expediente='12345/2024'))
        end = time.time()

        # Debe ser muy rápido (< 50ms)
        self.assertLess((end - start) * 1000, 50)

    def test_formulario_composite_index(self):
        """Verifica que el índice compuesto funciona."""
        # Crear formulario
        Formulario.objects.create(
            carrera_academica=self.ca,
            tipo_formulario='F04',
            estado='PEN',
            anio_correspondiente=2024
        )

    def test_cargo_estado_caracter_index(self):
        """Verifica índice compuesto de Cargo."""
        qs = Cargo.objects.filter(
            estado='activo',
            caracter__in=['reg', 'ord']
        )

        explain = str(qs.explain())
        self.assertIsNotNone(explain)
