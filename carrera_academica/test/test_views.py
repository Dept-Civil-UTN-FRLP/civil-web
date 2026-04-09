# carrera_academica/test/test_views.py
"""
Tests de integración para views críticas de Carrera Académica.
"""
from datetime import date

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from carrera_academica.models import CarreraAcademica, Formulario
from planta_docente.models import Asignatura, Cargo, Docente


class CAViewTestMixin:
    """Mixin con setup común para tests de views."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )
        self.client.login(username="testuser", password="testpass123")

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


class DashboardViewTestCase(CAViewTestMixin, TestCase):

    def test_dashboard_requiere_login(self):
        self.client.logout()
        url = reverse("carrera_academica:dashboard_ca")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response.url)

    def test_dashboard_carga_correctamente(self):
        response = self.client.get(reverse("carrera_academica:dashboard_ca"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "PEREZ")

    def test_dashboard_filtro_por_estado(self):
        response = self.client.get(
            reverse("carrera_academica:dashboard_ca"), {"estado": "ACT"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "PEREZ")

    def test_dashboard_filtro_por_busqueda(self):
        response = self.client.get(
            reverse("carrera_academica:dashboard_ca"), {"q": "Perez"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "PEREZ")

    def test_dashboard_busqueda_sin_resultados(self):
        response = self.client.get(
            reverse("carrera_academica:dashboard_ca"), {"q": "zzznoencontrado"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "PEREZ")


class DetalleCAViewTestCase(CAViewTestMixin, TestCase):

    def test_detalle_carga_correctamente(self):
        response = self.client.get(
            reverse("carrera_academica:detalle_ca", kwargs={"pk": self.ca.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "PEREZ")

    def test_detalle_ca_inexistente_retorna_404(self):
        response = self.client.get(
            reverse("carrera_academica:detalle_ca", kwargs={"pk": 99999})
        )
        self.assertEqual(response.status_code, 404)

    def test_subir_archivo_formulario(self):
        formulario = self.ca.formularios.filter(tipo_formulario="F01").first()
        self.assertIsNotNone(formulario)

        import io
        archivo = io.BytesIO(b"contenido de prueba")
        archivo.name = "test.pdf"

        response = self.client.post(
            reverse("carrera_academica:detalle_ca", kwargs={"pk": self.ca.pk}),
            {"formulario_id": formulario.pk, "archivo": archivo},
        )
        self.assertRedirects(
            response,
            reverse("carrera_academica:detalle_ca", kwargs={"pk": self.ca.pk}),
        )
        formulario.refresh_from_db()
        self.assertEqual(formulario.estado, "ENT")


class ArchivarCAViewTestCase(CAViewTestMixin, TestCase):

    def test_archivar_ca_get(self):
        response = self.client.get(
            reverse("carrera_academica:archivar_ca", kwargs={"pk": self.ca.pk})
        )
        self.assertEqual(response.status_code, 200)

    def test_archivar_ca_post_exitoso(self):
        response = self.client.post(
            reverse("carrera_academica:archivar_ca",
                    kwargs={"pk": self.ca.pk}),
            {"motivo_archivo": "jubilacion_cercana",
                "observaciones_archivo": "Test"},
        )
        self.assertRedirects(
            response,
            reverse("carrera_academica:detalle_ca", kwargs={"pk": self.ca.pk}),
        )
        self.ca.refresh_from_db()
        self.assertEqual(self.ca.estado, "ARCH")

    def test_archivar_ca_sin_motivo_no_archiva(self):
        response = self.client.post(
            reverse("carrera_academica:archivar_ca",
                    kwargs={"pk": self.ca.pk}),
            {"motivo_archivo": "", "observaciones_archivo": ""},
        )
        self.ca.refresh_from_db()
        self.assertEqual(self.ca.estado, "ACT")


class FinalizarCAViewTestCase(CAViewTestMixin, TestCase):

    def test_finalizar_ca_get(self):
        response = self.client.get(
            reverse("carrera_academica:finalizar_ca",
                    kwargs={"pk": self.ca.pk})
        )
        self.assertEqual(response.status_code, 200)

    def test_finalizar_ca_aprobada_rechaza(self):
        response = self.client.post(
            reverse("carrera_academica:finalizar_ca",
                    kwargs={"pk": self.ca.pk}),
            {"resultado_cierre": "aprobada_rechaza", "observaciones_cierre": ""},
        )
        self.assertRedirects(
            response,
            reverse("carrera_academica:detalle_ca", kwargs={"pk": self.ca.pk}),
        )
        self.ca.refresh_from_db()
        self.assertEqual(self.ca.estado, "FIN")
        self.cargo.refresh_from_db()
        self.assertEqual(self.cargo.caracter, "int")

    def test_finalizar_ca_redesignacion_redirige_a_nueva_ca(self):
        response = self.client.post(
            reverse("carrera_academica:finalizar_ca",
                    kwargs={"pk": self.ca.pk}),
            {
                "resultado_cierre": "aprobada_redesigna",
                "nueva_fecha_vencimiento": "2030-01-01",
                "observaciones_cierre": "",
            },
        )
        # Debe redirigir a la nueva CA, no a la original
        self.assertEqual(response.status_code, 302)
        nueva_ca = CarreraAcademica.objects.filter(ca_anterior=self.ca).first()
        self.assertIsNotNone(nueva_ca)
        self.assertRedirects(
            response,
            reverse("carrera_academica:detalle_ca",
                    kwargs={"pk": nueva_ca.pk}),
        )

    def test_finalizar_ca_sin_resultado_no_finaliza(self):
        self.client.post(
            reverse("carrera_academica:finalizar_ca",
                    kwargs={"pk": self.ca.pk}),
            {"resultado_cierre": "", "observaciones_cierre": ""},
        )
        self.ca.refresh_from_db()
        self.assertEqual(self.ca.estado, "ACT")


class ProrrogaViewTestCase(CAViewTestMixin, TestCase):

    def _registrar_resolucion(self, extra_data):
        from planta_docente.models import Resolucion
        data = {
            "objeto": "prorroga_ca",
            "numero": 123,
            "año": 2025,
            "origen": "cd",
            **extra_data,
        }
        return self.client.post(
            reverse("carrera_academica:registrar_resolucion",
                    kwargs={"pk": self.ca.pk}),
            data,
        )

    def test_prorroga_con_dias_actualiza_vencimiento(self):
        fecha_original = self.ca.fecha_vencimiento_actual
        self._registrar_resolucion({"prorroga_dias": 365})
        self.ca.refresh_from_db()
        from datetime import timedelta
        self.assertEqual(
            self.ca.fecha_vencimiento_actual,
            fecha_original + timedelta(days=365)
        )

    def test_prorroga_con_fecha_directa(self):
        self._registrar_resolucion({"nueva_fecha_vencimiento": "2027-06-01"})
        self.ca.refresh_from_db()
        self.assertEqual(self.ca.fecha_vencimiento_actual, date(2027, 6, 1))

    def test_prorroga_fecha_anterior_no_actualiza(self):
        fecha_original = self.ca.fecha_vencimiento_actual
        self._registrar_resolucion({"nueva_fecha_vencimiento": "2023-01-01"})
        self.ca.refresh_from_db()
        self.assertEqual(self.ca.fecha_vencimiento_actual, fecha_original)
