# carrera_academica/test/test_portal_concursos_views.py
"""
Tests de la vista pública del Portal de Concursos: link + contraseña para
descargar el expediente completo de UNA CA, sin pasar por DNI/persona.
"""
import io
import shutil
import tempfile
from datetime import date

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from pypdf import PdfWriter

from carrera_academica.models import CarreraAcademica, TokenPortalConcursos
from carrera_academica.services.token_portal_service import crear_token_concursos
from planta_docente.models import Asignatura, Cargo, Docente


def _pdf_bytes():
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


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
        docente = Docente.objects.create(
            nombre="Ana", apellido="Test", documento=11111111, legajo=11111111,
            fecha_nacimiento=date(1980, 1, 1),
        )
        asignatura = Asignatura.objects.create(
            nombre="Analisis I", nivel="i", departamento="civil", especialidad="civil",
            hora_semanal=4, hora_total=96, dictado="a",
        )
        cargo = Cargo.objects.create(
            docente=docente, asignatura=asignatura, caracter="reg", categoria="adj",
            dedicacion="ds", cantidad_horas=10, fecha_inicio=date(2020, 1, 1),
            fecha_vencimiento=date(2025, 1, 1), estado="activo",
            estado_continuidad="activo",
        )
        self.ca = CarreraAcademica.objects.create(
            cargo=cargo, fecha_inicio=date(2020, 1, 1),
            fecha_vencimiento_original=date(2025, 1, 1),
            fecha_vencimiento_actual=date(2025, 1, 1), estado="ACT",
        )
        cv = self.ca.formularios.get(tipo_formulario="CV")
        cv.archivo = SimpleUploadedFile("cv.pdf", _pdf_bytes(), content_type="application/pdf")
        cv.estado = "ENT"
        cv.save()

        self.token_obj, self.raw_token = crear_token_concursos(self.ca, "clave123")
        self.url = reverse("carrera_academica:portal_concursos_landing", args=[self.raw_token])

    def test_password_correcta_descarga_el_pdf(self):
        resp = self.client.post(self.url, {"password": "clave123"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "application/pdf")

        self.token_obj.refresh_from_db()
        self.assertIsNotNone(self.token_obj.ultimo_uso)

    def test_password_incorrecta_no_descarga_nada(self):
        resp = self.client.post(self.url, {"password": "noesesta"})
        self.assertNotEqual(resp.get("Content-Type"), "application/pdf")
        self.assertContains(resp, "inválido")

    def test_token_invalido_da_error_generico(self):
        url = reverse("carrera_academica:portal_concursos_landing", args=["token-trucho"])
        resp = self.client.post(url, {"password": "clave123"})
        self.assertContains(resp, "inválido")

    def test_token_revocado_no_funciona(self):
        self.token_obj.revocado = True
        self.token_obj.save()
        resp = self.client.post(self.url, {"password": "clave123"})
        self.assertContains(resp, "inválido")

    def test_password_no_se_filtra_a_otra_ca(self):
        """Generar un token nuevo para la misma CA revoca el anterior -- el
        link viejo deja de funcionar."""
        crear_token_concursos(self.ca, "otraclave")
        resp = self.client.post(self.url, {"password": "clave123"})
        self.assertContains(resp, "inválido")

    def test_get_muestra_formulario(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Contraseña")
