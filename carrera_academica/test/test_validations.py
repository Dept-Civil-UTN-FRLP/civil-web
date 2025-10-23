# carrera_academica/tests/test_validations.py
"""
Tests para validaciones de modelos.
"""
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import date, timedelta

from carrera_academica.models import CarreraAcademica, Evaluacion, Formulario
from planta_docente.models import Cargo, Docente, Asignatura


class CarreraAcademicaValidationTestCase(TestCase):
    """Tests de validación para el modelo CarreraAcademica."""

    def setUp(self):
        """Configurar datos de prueba."""
        self.docente = Docente.objects.create(
            nombre="juan",
            apellido="perez",
            documento=12345678,
            legajo=1001,
            fecha_nacimiento=date(1980, 1, 1)
        )

        self.asignatura = Asignatura.objects.create(
            nombre="test asignatura",
            nivel="i",
            departamento="civil",
            especialidad="civil",
            hora_semanal=4,
            hora_total=96,
            dictado="a"
        )

        self.cargo = Cargo.objects.create(
            docente=self.docente,
            asignatura=self.asignatura,
            caracter="reg",
            categoria="adj",
            dedicacion="ds",
            fecha_inicio=date(2020, 1, 1),
            fecha_vencimiento=date(2025, 1, 1)
        )

    def test_caracter_invalido_para_ca(self):
        """Test que solo reg/ord pueden tener CA."""
        cargo_interino = Cargo.objects.create(
            docente=self.docente,
            asignatura=self.asignatura,
            caracter="int",
            categoria="adj",
            dedicacion="ds",
            fecha_inicio=date(2020, 1, 1)
        )

        ca = CarreraAcademica(
            cargo=cargo_interino,
            fecha_inicio=date(2020, 1, 1),
            fecha_vencimiento_original=date(2025, 1, 1)
        )

        with self.assertRaises(ValidationError) as context:
            ca.full_clean()

        self.assertIn('cargo', context.exception.message_dict)

    def test_fecha_vencimiento_antes_de_inicio(self):
        """Test que vencimiento debe ser posterior al inicio."""
        ca = CarreraAcademica(
            cargo=self.cargo,
            fecha_inicio=date(2020, 1, 1),
            fecha_vencimiento_original=date(2019, 12, 31)  # Antes del inicio
        )

        with self.assertRaises(ValidationError):
            ca.full_clean()

    def test_duracion_minima_2_anios(self):
        """Test que la CA debe durar al menos 2 años."""
        ca = CarreraAcademica(
            cargo=self.cargo,
            fecha_inicio=date(2020, 1, 1),
            fecha_vencimiento_original=date(2021, 1, 1)  # Solo 1 año
        )

        with self.assertRaises(ValidationError):
            ca.full_clean()

    def test_ca_valida(self):
        """Test que una CA válida se crea sin errores."""
        ca = CarreraAcademica(
            cargo=self.cargo,
            fecha_inicio=date(2020, 1, 1),
            fecha_vencimiento_original=date(2025, 1, 1)
        )

        try:
            ca.full_clean()
            ca.save()
            self.assertIsNotNone(ca.pk)
        except ValidationError:
            self.fail("Una CA válida no debería lanzar ValidationError")

    def test_no_puede_haber_dos_ca_activas_mismo_cargo(self):
        """Test que no pueden haber dos CA activas para el mismo cargo."""
        # Crear primera CA
        ca1 = CarreraAcademica.objects.create(
            cargo=self.cargo,
            fecha_inicio=date(2020, 1, 1),
            fecha_vencimiento_original=date(2025, 1, 1),
            estado='ACT'
        )

        # Intentar crear segunda CA activa
        ca2 = CarreraAcademica(
            cargo=self.cargo,
            fecha_inicio=date(2021, 1, 1),
            fecha_vencimiento_original=date(2026, 1, 1),
            estado='ACT'
        )

        with self.assertRaises(ValidationError):
            ca2.full_clean()


class EvaluacionValidationTestCase(TestCase):
    """Tests de validación para el modelo Evaluacion."""

    def setUp(self):
        """Configurar datos de prueba."""
        self.docente = Docente.objects.create(
            nombre="juan",
            apellido="perez",
            documento=12345678,
            legajo=1001,
            fecha_nacimiento=date(1980, 1, 1)
        )

        self.asignatura = Asignatura.objects.create(
            nombre="test",
            nivel="i",
            departamento="civil",
            especialidad="civil",
            hora_semanal=4,
            hora_total=96,
            dictado="a"
        )

        self.cargo = Cargo.objects.create(
            docente=self.docente,
            asignatura=self.asignatura,
            caracter="reg",
            categoria="adj",
            dedicacion="ds",
            fecha_inicio=date(2020, 1, 1),
            fecha_vencimiento=date(2025, 1, 1)
        )

        self.ca = CarreraAcademica.objects.create(
            cargo=self.cargo,
            fecha_inicio=date(2020, 1, 1),
            fecha_vencimiento_original=date(2025, 1, 1)
        )

    def test_anio_anterior_a_inicio_ca(self):
        """Test que no se puede evaluar año anterior al inicio de la CA."""
        evaluacion = Evaluacion(
            carrera_academica=self.ca,
            numero_evaluacion=1,
            anios_evaluados=[2019]  # Antes del inicio (2020)
        )

        with self.assertRaises(ValidationError):
            evaluacion.full_clean()

    def test_anio_futuro(self):
        """Test que no se puede evaluar año futuro."""
        anio_futuro = timezone.now().year + 1

        evaluacion = Evaluacion(
            carrera_academica=self.ca,
            numero_evaluacion=1,
            anios_evaluados=[anio_futuro]
        )

        with self.assertRaises(ValidationError):
            evaluacion.full_clean()

    def test_solapamiento_anios(self):
        """Test que no puede haber solapamiento de años entre evaluaciones."""
        # Crear primera evaluación
        eval1 = Evaluacion.objects.create(
            carrera_academica=self.ca,
            numero_evaluacion=1,
            anios_evaluados=[2020, 2021]
        )

        # Intentar crear segunda con años solapados
        eval2 = Evaluacion(
            carrera_academica=self.ca,
            numero_evaluacion=2,
            anios_evaluados=[2021, 2022]  # 2021 ya está en eval1
        )

        with self.assertRaises(ValidationError):
            eval2.full_clean()

    def test_evaluacion_valida(self):
        """Test que una evaluación válida se crea sin errores."""
        evaluacion = Evaluacion(
            carrera_academica=self.ca,
            numero_evaluacion=1,
            anios_evaluados=[2020, 2021, 2022]
        )

        try:
            evaluacion.full_clean()
            evaluacion.save()
            self.assertIsNotNone(evaluacion.pk)
        except ValidationError:
            self.fail("Una evaluación válida no debería lanzar ValidationError")


class FormularioValidationTestCase(TestCase):
    """Tests de validación para el modelo Formulario."""

    def setUp(self):
        """Configurar datos de prueba."""
        self.docente = Docente.objects.create(
            nombre="juan",
            apellido="perez",
            documento=12345678,
            legajo=1001,
            fecha_nacimiento=date(1980, 1, 1)
        )

        self.asignatura = Asignatura.objects.create(
            nombre="test",
            nivel="i",
            departamento="civil",
            especialidad="civil",
            hora_semanal=4,
            hora_total=96,
            dictado="a"
        )

        self.cargo = Cargo.objects.create(
            docente=self.docente,
            asignatura=self.asignatura,
            caracter="reg",
            categoria="adj",
            dedicacion="ds",
            fecha_inicio=date(2020, 1, 1),
            fecha_vencimiento=date(2025, 1, 1)
        )

        self.ca = CarreraAcademica.objects.create(
            cargo=self.cargo,
            fecha_inicio=date(2020, 1, 1),
            fecha_vencimiento_original=date(2025, 1, 1)
        )

    def test_formulario_anual_sin_anio(self):
        """Test que formularios anuales deben tener año."""
        formulario = Formulario(
            carrera_academica=self.ca,
            tipo_formulario="F04",
            anio_correspondiente=None  # Falta el año
        )

        with self.assertRaises(ValidationError):
            formulario.full_clean()

    def test_anio_fuera_de_rango_ca(self):
        """Test que el año debe estar en el rango de la CA."""
        formulario = Formulario(
            carrera_academica=self.ca,
            tipo_formulario="F04",
            anio_correspondiente=2030  # Fuera del rango 2020-2025
        )

        with self.assertRaises(ValidationError):
            formulario.full_clean()

    def test_formulario_entregado_sin_archivo(self):
        """Test que formulario entregado debe tener archivo."""
        formulario = Formulario(
            carrera_academica=self.ca,
            tipo_formulario="F04",
            anio_correspondiente=2020,
            estado="ENT",
            archivo=None  # Sin archivo
        )

        with self.assertRaises(ValidationError):
            formulario.full_clean()
