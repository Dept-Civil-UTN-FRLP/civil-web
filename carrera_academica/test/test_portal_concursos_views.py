# carrera_academica/test/test_portal_concursos_views.py
"""
Tests de la vista pública del Portal de Concursos: link + contraseña que
abre una sesión (igual que el portal de jurados) para ver todos los
formularios de UNA CA y descargarlos, individualmente o consolidados.
"""
import io
import shutil
import tempfile
from datetime import date

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from pypdf import PdfWriter

from carrera_academica.models import CarreraAcademica
from carrera_academica.services.token_portal_service import crear_token_concursos
from planta_docente.models import Asignatura, Cargo, Docente


def _pdf_bytes():
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _crear_ca(sufijo=""):
    docente = Docente.objects.create(
        nombre=f"Ana{sufijo}", apellido="Test", documento=11111111 + len(sufijo),
        legajo=11111111 + len(sufijo), fecha_nacimiento=date(1980, 1, 1),
    )
    asignatura = Asignatura.objects.create(
        nombre=f"Analisis{sufijo}", nivel="i", departamento="civil", especialidad="civil",
        hora_semanal=4, hora_total=96, dictado="a",
    )
    cargo = Cargo.objects.create(
        docente=docente, asignatura=asignatura, caracter="reg", categoria="adj",
        dedicacion="ds", cantidad_horas=10, fecha_inicio=date(2020, 1, 1),
        fecha_vencimiento=date(2025, 1, 1), estado="activo",
        estado_continuidad="activo",
    )
    ca = CarreraAcademica.objects.create(
        cargo=cargo, fecha_inicio=date(2020, 1, 1),
        fecha_vencimiento_original=date(2025, 1, 1),
        fecha_vencimiento_actual=date(2025, 1, 1), estado="ACT",
    )
    cv = ca.formularios.get(tipo_formulario="CV")
    cv.archivo = SimpleUploadedFile("cv.pdf", _pdf_bytes(), content_type="application/pdf")
    cv.estado = "ENT"
    cv.save()
    return ca


@override_settings(PORTAL_JURADOS_ENABLED=True)
class PortalConcursosViewsTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        cls._media_root_temp = tempfile.mkdtemp()
        cls._media_override = override_settings(MEDIA_ROOT=cls._media_root_temp)
        cls._media_override.enable()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls._media_override.disable()
        shutil.rmtree(cls._media_root_temp, ignore_errors=True)

    def setUp(self):
        self.ca = _crear_ca()
        self.token_obj, self.raw_token = crear_token_concursos(self.ca, "clave123")
        self.url = reverse("carrera_academica:portal_concursos_landing", args=[self.raw_token])
        self.dashboard_url = reverse("carrera_academica:portal_concursos_dashboard")

    def _login(self):
        return self.client.post(self.url, {"password": "clave123"})

    def test_get_muestra_formulario(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Contraseña")

    def test_password_correcta_abre_sesion_y_redirige_al_dashboard(self):
        resp = self._login()
        self.assertRedirects(resp, self.dashboard_url)
        self.token_obj.refresh_from_db()
        self.assertIsNotNone(self.token_obj.ultimo_uso)

    def test_password_incorrecta_no_abre_sesion(self):
        resp = self.client.post(self.url, {"password": "noesesta"})
        self.assertContains(resp, "inválido")
        dash = self.client.get(self.dashboard_url)
        self.assertRedirects(
            dash, reverse("carrera_academica:portal_concursos_sesion_expirada")
        )

    def test_token_invalido_da_error_generico(self):
        url = reverse("carrera_academica:portal_concursos_landing", args=["token-trucho"])
        resp = self.client.post(url, {"password": "clave123"})
        self.assertContains(resp, "inválido")

    def test_token_revocado_no_funciona(self):
        self.token_obj.revocado = True
        self.token_obj.save()
        resp = self.client.post(self.url, {"password": "clave123"})
        self.assertContains(resp, "inválido")

    def test_dashboard_sin_sesion_redirige_a_expirada(self):
        resp = self.client.get(self.dashboard_url)
        self.assertRedirects(
            resp, reverse("carrera_academica:portal_concursos_sesion_expirada")
        )

    def test_dashboard_con_sesion_muestra_formularios(self):
        self._login()
        resp = self.client.get(self.dashboard_url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Curriculum Vitae")

    def test_dashboard_revalida_token_revocado_despues_de_abrir_sesion(self):
        self._login()
        self.token_obj.revocado = True
        self.token_obj.save()
        resp = self.client.get(self.dashboard_url)
        self.assertRedirects(
            resp, reverse("carrera_academica:portal_concursos_sesion_expirada")
        )

    def test_descarga_documento_individual(self):
        self._login()
        cv = self.ca.formularios.get(tipo_formulario="CV")
        with override_settings(DEBUG=True):
            resp = self.client.get(
                reverse("carrera_academica:portal_concursos_documento", args=[cv.pk])
            )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "application/pdf")

    def test_documento_de_otra_ca_da_404_idor(self):
        """La sesión de la CA A no puede usarse para bajar un formulario de la CA B."""
        otra_ca = _crear_ca(sufijo="B")
        otro_cv = otra_ca.formularios.get(tipo_formulario="CV")
        self._login()
        resp = self.client.get(
            reverse("carrera_academica:portal_concursos_documento", args=[otro_cv.pk])
        )
        self.assertEqual(resp.status_code, 404)

    def test_descarga_expediente_completo_con_sesion(self):
        self._login()
        resp = self.client.get(
            reverse("carrera_academica:portal_concursos_expediente_completo")
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "application/pdf")

    def test_expediente_completo_sin_sesion_redirige_a_expirada(self):
        resp = self.client.get(
            reverse("carrera_academica:portal_concursos_expediente_completo")
        )
        self.assertRedirects(
            resp, reverse("carrera_academica:portal_concursos_sesion_expirada")
        )

    def test_logout_cierra_sesion(self):
        self._login()
        self.client.get(reverse("carrera_academica:portal_concursos_logout"))
        resp = self.client.get(self.dashboard_url)
        self.assertRedirects(
            resp, reverse("carrera_academica:portal_concursos_sesion_expirada")
        )
