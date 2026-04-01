# carrera_academica/test/test_services.py
"""
Tests para CAService.
"""
from datetime import date, timedelta

from django.test import TestCase
from django.utils import timezone

from carrera_academica.models import CarreraAcademica
from carrera_academica.services.ca_service import CAService
from planta_docente.models import Asignatura, Cargo, Docente


class CAServiceTestMixin:
    """Mixin con setup común para tests de CAService."""

    def setUp(self):
        self.docente = Docente.objects.create(
            nombre="Juan",
            apellido="Perez",
            documento=12345678,
            legajo=1001,
            fecha_nacimiento=date(1980, 1, 1),
        )
        self.asignatura = Asignatura.objects.create(
            nombre="Análisis I",
            nivel="i",
            departamento="civil",
            especialidad="civil",
            hora_semanal=4,
            hora_total=96,
            dictado="a",
        )
        self.cargo = Cargo.objects.create(
            docente=self.docente,
            asignatura=self.asignatura,
            caracter="reg",
            categoria="adj",
            dedicacion="ds",
            cantidad_horas=10,
            fecha_inicio=date(2020, 1, 1),
            fecha_vencimiento=date(2025, 1, 1),
            estado="activo",
            estado_continuidad="activo",
        )
        self.ca = CarreraAcademica.objects.create(
            cargo=self.cargo,
            fecha_inicio=date(2020, 1, 1),
            fecha_vencimiento_original=date(2025, 1, 1),
            fecha_vencimiento_actual=date(2025, 1, 1),
            estado="ACT",
        )


class CAServiceArchivarTestCase(CAServiceTestMixin, TestCase):

    def test_archivar_ca_activa(self):
        exito, _ = CAService.archivar(
            self.ca, "jubilacion_cercana", "Observación test")
        self.assertTrue(exito)
        self.ca.refresh_from_db()
        self.assertEqual(self.ca.estado, "ARCH")
        self.assertEqual(self.ca.motivo_archivo, "jubilacion_cercana")
        self.assertEqual(self.ca.observaciones_archivo, "Observación test")
        self.assertIsNotNone(self.ca.fecha_archivo)

    def test_archivar_ca_ya_finalizada_falla(self):
        self.ca.estado = "FIN"
        self.ca.save()
        exito, mensaje = CAService.archivar(self.ca, "administrativo")
        self.assertFalse(exito)
        self.assertIn("activas o vencidas", mensaje)

    def test_archivar_ca_vencida(self):
        self.ca.estado = "VEN"
        self.ca.save()
        exito, _ = CAService.archivar(self.ca, "administrativo")
        self.assertTrue(exito)
        self.ca.refresh_from_db()
        self.assertEqual(self.ca.estado, "ARCH")


class CAServiceProrrogaTestCase(CAServiceTestMixin, TestCase):

    def test_prorroga_con_dias(self):
        fecha_original = self.ca.fecha_vencimiento_actual
        exito, mensaje = CAService.aplicar_prorroga(self.ca, dias=365)
        self.assertTrue(exito)
        self.ca.refresh_from_db()
        self.assertEqual(
            self.ca.fecha_vencimiento_actual,
            fecha_original + timedelta(days=365)
        )

    def test_prorroga_con_fecha_directa(self):
        nueva_fecha = date(2027, 1, 1)
        exito, _ = CAService.aplicar_prorroga(self.ca, nueva_fecha=nueva_fecha)
        self.assertTrue(exito)
        self.ca.refresh_from_db()
        self.assertEqual(self.ca.fecha_vencimiento_actual, nueva_fecha)

    def test_prorroga_fecha_anterior_falla(self):
        fecha_pasada = date(2024, 1, 1)  # Menor al vencimiento actual (2025)
        exito, mensaje = CAService.aplicar_prorroga(
            self.ca, nueva_fecha=fecha_pasada)
        self.assertFalse(exito)
        self.assertIn("posterior", mensaje)

    def test_prorroga_sin_fecha_ni_dias_falla(self):
        exito, mensaje = CAService.aplicar_prorroga(self.ca)
        self.assertFalse(exito)
        self.assertIn("Debe especificar", mensaje)

    def test_prorroga_crea_formularios_para_anios_nuevos(self):
        from carrera_academica.models import Formulario
        formularios_antes = Formulario.objects.filter(
            carrera_academica=self.ca,
            anio_correspondiente=2026
        ).count()
        self.assertEqual(formularios_antes, 0)

        CAService.aplicar_prorroga(self.ca, nueva_fecha=date(2027, 1, 1))

        formularios_despues = Formulario.objects.filter(
            carrera_academica=self.ca,
            anio_correspondiente=2026
        ).count()
        self.assertGreater(formularios_despues, 0)


class CAServiceFinalizarTestCase(CAServiceTestMixin, TestCase):

    def test_finalizar_aprobada_rechaza(self):
        exito, _ = CAService.finalizar(self.ca, "aprobada_rechaza")
        self.assertTrue(exito)
        self.ca.refresh_from_db()
        self.assertEqual(self.ca.estado, "FIN")
        self.assertEqual(self.ca.resultado_cierre, "aprobada_rechaza")
        self.cargo.refresh_from_db()
        self.assertEqual(self.cargo.caracter, "int")

    def test_finalizar_no_aprobada(self):
        exito, _ = CAService.finalizar(self.ca, "no_aprobada")
        self.assertTrue(exito)
        self.cargo.refresh_from_db()
        self.assertEqual(self.cargo.caracter, "int")

    def test_finalizar_redesignacion_sin_fecha_falla(self):
        exito, mensaje = CAService.finalizar(self.ca, "aprobada_redesigna")
        self.assertFalse(exito)
        self.assertIn("fecha", mensaje.lower())

    def test_finalizar_redesignacion_crea_nueva_ca(self):
        nueva_fecha = date(2030, 1, 1)
        exito, mensaje = CAService.finalizar(
            self.ca, "aprobada_redesigna", nueva_fecha_vencimiento=nueva_fecha
        )
        self.assertTrue(exito)
        self.assertTrue(mensaje.startswith("redesignacion:"))

        nueva_ca_pk = int(mensaje.split(":")[1])
        nueva_ca = CarreraAcademica.objects.get(pk=nueva_ca_pk)
        self.assertEqual(nueva_ca.estado, "ACT")
        self.assertEqual(nueva_ca.ca_anterior, self.ca)
        self.assertEqual(nueva_ca.fecha_vencimiento_original, nueva_fecha)

    def test_finalizar_seta_fecha_finalizacion(self):
        CAService.finalizar(self.ca, "aprobada_rechaza")
        self.ca.refresh_from_db()
        self.assertIsNotNone(self.ca.fecha_finalizacion)
