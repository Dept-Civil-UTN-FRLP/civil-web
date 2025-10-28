# planta_docente/tests/test_managers.py
"""
Tests para los managers personalizados de planta docente.
"""
from django.test import TestCase
from django.utils import timezone
from datetime import date, timedelta

from planta_docente.models import Docente, Cargo, Asignatura


class CargoManagerTestCase(TestCase):
    """Tests para CargoManager."""

    @classmethod
    def setUpTestData(cls):
        """Crear datos de prueba."""
        # Crear docentes
        cls.docente1 = Docente.objects.create(
            nombre="Juan",
            apellido="Pérez",
            documento=12345678,
            legajo=1001,
            fecha_nacimiento=date(1980, 1, 1),
        )

        cls.docente2 = Docente.objects.create(
            nombre="María",
            apellido="García",
            documento=87654321,
            legajo=1002,
            fecha_nacimiento=date(1955, 6, 15),  # 69 años
        )

        # Crear asignatura
        cls.asignatura1 = Asignatura.objects.create(
            nombre="Test Asignatura",
            nivel="i",
            departamento="civil",
            especialidad="civil",
            hora_semanal=4,
            hora_total=96,
            dictado="a",
        )

        cls.asignatura2 = Asignatura.objects.create(
            nombre="Test Asignatura",
            nivel="iI",
            departamento="civil",
            especialidad="civil",
            hora_semanal=4,
            hora_total=96,
            dictado="a",
        )

        # Crear cargo activo que vence pronto
        cls.cargo_activo = Cargo.objects.create(
            docente=cls.docente1,
            asignatura=cls.asignatura1,
            caracter="reg",
            categoria="adj",
            dedicacion="ds",
            cantidad_horas=10,
            fecha_inicio=date(2020, 1, 1),
            fecha_vencimiento=timezone.now().date() + timedelta(days=90),
            estado="activo",
        )

        # Crear cargo en licencia
        cls.cargo_licencia = Cargo.objects.create(
            docente=cls.docente2,
            asignatura=cls.asignatura1,
            caracter="reg",
            categoria="adj",
            dedicacion="ds",
            cantidad_horas=10,
            fecha_inicio=date(2018, 1, 1),
            fecha_vencimiento=date(2025, 12, 31),
            estado="licencia",
        )

        # Crear cargo vencido
        cls.cargo_vencido = Cargo.objects.create(
            docente=cls.docente1,
            asignatura=cls.asignatura2,
            caracter="int",
            categoria="jtp",
            dedicacion="ds",
            cantidad_horas=10,
            fecha_inicio=date(2019, 1, 1),
            fecha_vencimiento=timezone.now().date() - timedelta(days=30),
            estado="activo",
        )

    def test_activos(self):
        """Test que filtra solo cargos activos."""
        cargos = Cargo.objects.activos()
        self.assertEqual(cargos.count(), 2)
        self.assertIn(self.cargo_activo, cargos)
        self.assertIn(self.cargo_vencido, cargos)

    def test_en_licencia(self):
        """Test que filtra cargos en licencia."""
        cargos = Cargo.objects.en_licencia()
        self.assertEqual(cargos.count(), 1)
        self.assertEqual(cargos.first(), self.cargo_licencia)

    def test_regulares_ordinarios(self):
        """Test que filtra solo cargos regulares u ordinarios."""
        cargos = Cargo.objects.regulares_ordinarios()
        self.assertEqual(cargos.count(), 2)

    def test_proximos_a_vencer(self):
        """Test que filtra cargos próximos a vencer."""
        cargos = Cargo.objects.proximos_a_vencer(180)
        self.assertEqual(cargos.count(), 1)
        self.assertEqual(cargos.first(), self.cargo_activo)

    def test_vencidos(self):
        """Test que filtra cargos vencidos."""
        cargos = Cargo.objects.vencidos()
        self.assertEqual(cargos.count(), 1)
        self.assertEqual(cargos.first(), self.cargo_vencido)


class DocenteManagerTestCase(TestCase):
    """Tests para DocenteManager."""

    @classmethod
    def setUpTestData(cls):
        """Crear datos de prueba."""
        # Docente joven
        cls.docente_joven = Docente.objects.create(
            nombre="Ana",
            apellido="López",
            documento=11111111,
            legajo=2001,
            fecha_nacimiento=date(1990, 3, 15),
        )

        # Docente próximo a 65
        hoy = timezone.now().date()
        fecha_nac_64 = date(hoy.year - 64, hoy.month, hoy.day)
        cls.docente_proximo_65 = Docente.objects.create(
            nombre="Carlos",
            apellido="Martínez",
            documento=22222222,
            legajo=2002,
            fecha_nacimiento=fecha_nac_64,
        )

        # Docente mayor de 65
        cls.docente_mayor_65 = Docente.objects.create(
            nombre="Roberto",
            apellido="Sánchez",
            documento=33333333,
            legajo=2003,
            fecha_nacimiento=date(1955, 1, 1),
        )

    def test_proximos_a_jubilarse(self):
        """Test que filtra docentes próximos a jubilarse."""
        docentes = Docente.objects.proximos_a_jubilarse(2)
        self.assertIn(self.docente_proximo_65, docentes)
        self.assertNotIn(self.docente_joven, docentes)

    def test_mayores_de_65(self):
        """Test que filtra docentes mayores de 65."""
        docentes = Docente.objects.mayores_de_65()
        self.assertIn(self.docente_mayor_65, docentes)
        self.assertNotIn(self.docente_joven, docentes)
