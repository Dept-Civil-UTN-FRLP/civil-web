# carrera_academica/test/test_portal_jurado_views.py
"""
Tests de las vistas públicas del Portal de Jurados: verificación de
token+DNI, expiración/revocación, kill switch, y sobre todo el chequeo
anti-IDOR (un jurado nunca puede acceder a documentos/expedientes de una
CA que no le corresponde, ni siquiera con una URL directa).
"""
import importlib
import io
import shutil
import tempfile
from datetime import date, timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import clear_url_caches, reverse
from django.utils import timezone
from pypdf import PdfWriter

import config.urls as root_urls
import carrera_academica.urls as ca_urls
from carrera_academica.models import (
    AccesoPortalJurado,
    CarreraAcademica,
    Formulario,
    Jurado,
    JuradoExterno,
    TokenPortalJurado,
    Universidad,
)
from carrera_academica.services.token_portal_service import crear_token
from planta_docente.models import Asignatura, Cargo, Docente


def _pdf_bytes():
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _reload_urlconf():
    """Fuerza que urls.py se re-evalúe con el settings actual (PORTAL_JURADOS_ENABLED
    se lee al importar el módulo, no en cada request)."""
    clear_url_caches()
    importlib.reload(ca_urls)
    importlib.reload(root_urls)


def _crear_ca(documento, nombre_asignatura, apellido="Test"):
    docente = Docente.objects.create(
        nombre="Ana", apellido=apellido, documento=documento, legajo=documento,
        fecha_nacimiento=date(1980, 1, 1),
    )
    asignatura = Asignatura.objects.create(
        nombre=nombre_asignatura, nivel="i", departamento="civil",
        especialidad="civil", hora_semanal=4, hora_total=96, dictado="a",
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
    return docente, ca


@override_settings(PORTAL_JURADOS_ENABLED=False)
class PortalJuradoKillSwitchTestCase(TestCase):
    """Con el flag apagado, las rutas del portal no deben existir."""

    def setUp(self):
        _reload_urlconf()

    def tearDown(self):
        # Restaurar el urlconf real (con el flag default/True según settings
        # de test) para no filtrar estado a otros TestCase de este archivo.
        _reload_urlconf()

    def test_rutas_no_registradas(self):
        with self.assertRaises(Exception):
            reverse("carrera_academica:portal_jurado_dashboard")


@override_settings(PORTAL_JURADOS_ENABLED=True)
class PortalJuradoViewsTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        # Aislar los archivos subidos en los tests del media/ real.
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
        _reload_urlconf()
        self.addCleanup(_reload_urlconf)

        self.universidad = Universidad.objects.create(
            sigla="UNLP", nombre_completo="Universidad Nacional de La Plata",
            es_utn=False,
        )

        # Jurado A / CA A
        self.docente_a, self.ca_a = _crear_ca(11111111, "Analisis I", apellido="Alfa")
        self.ext_a = JuradoExterno.objects.create(
            apellido="Ext", nombre="A", email="exta@test.com",
            universidad=self.universidad, categoria="titular", dni=22222222,
        )
        self.ext_a2 = JuradoExterno.objects.create(
            apellido="Ext", nombre="A2", email="exta2@test.com",
            universidad=self.universidad, categoria="titular", dni=22222223,
        )
        self.jurado_a = Jurado.objects.create(
            departamento="civil", profesor_titular_1=self.docente_a,
            profesor_titular_2=self.ext_a, profesor_titular_3=self.ext_a2,
        )
        self.ca_a.jurado = self.jurado_a
        self.ca_a.save()

        # Jurado B / CA B — persona totalmente distinta
        self.docente_b, self.ca_b = _crear_ca(33333333, "Analisis II", apellido="Beta")
        self.ext_b = JuradoExterno.objects.create(
            apellido="Ext", nombre="B", email="extb@test.com",
            universidad=self.universidad, categoria="titular", dni=44444444,
        )
        self.ext_b2 = JuradoExterno.objects.create(
            apellido="Ext", nombre="B2", email="extb2@test.com",
            universidad=self.universidad, categoria="titular", dni=44444445,
        )
        self.jurado_b = Jurado.objects.create(
            departamento="civil", profesor_titular_1=self.docente_b,
            profesor_titular_2=self.ext_b, profesor_titular_3=self.ext_b2,
        )
        self.ca_b.jurado = self.jurado_b
        self.ca_b.save()

        self.formulario_a = Formulario.objects.create(
            carrera_academica=self.ca_a, tipo_formulario="CV", estado="ENT",
            archivo=SimpleUploadedFile("cv_a.pdf", _pdf_bytes(), content_type="application/pdf"),
        )
        self.formulario_b = Formulario.objects.create(
            carrera_academica=self.ca_b, tipo_formulario="CV", estado="ENT",
            archivo=SimpleUploadedFile("cv_b.pdf", _pdf_bytes(), content_type="application/pdf"),
        )

        self.token_a, self.raw_a = crear_token("docente", self.docente_a.pk)

    def _landing_url(self, raw_token):
        return reverse("carrera_academica:portal_jurado_landing", args=[raw_token])

    def test_token_invalido_no_abre_sesion(self):
        resp = self.client.post(self._landing_url("token-que-no-existe"), {"dni": "11111111"})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "inválido")
        self.assertNotIn("portal_jurado", self.client.session)
        self.assertEqual(
            AccesoPortalJurado.objects.filter(accion="link_fail_token").count(), 1
        )

    def test_token_expirado_no_abre_sesion(self):
        self.token_a.expira = timezone.now() - timedelta(days=1)
        self.token_a.save()
        resp = self.client.post(self._landing_url(self.raw_a), {"dni": "11111111"})
        self.assertNotIn("portal_jurado", self.client.session)
        self.assertContains(resp, "inválido")

    def test_token_revocado_no_abre_sesion(self):
        self.token_a.revocado = True
        self.token_a.save()
        resp = self.client.post(self._landing_url(self.raw_a), {"dni": "11111111"})
        self.assertNotIn("portal_jurado", self.client.session)
        self.assertContains(resp, "inválido")

    def test_dni_incorrecto_no_abre_sesion(self):
        resp = self.client.post(self._landing_url(self.raw_a), {"dni": "99999999"})
        self.assertNotIn("portal_jurado", self.client.session)
        self.assertContains(resp, "inválido")
        self.assertEqual(
            AccesoPortalJurado.objects.filter(accion="link_fail_dni").count(), 1
        )

    def test_dni_correcto_abre_sesion_y_cambia_session_key(self):
        session_key_previo = self.client.session.session_key
        resp = self.client.post(self._landing_url(self.raw_a), {"dni": "11111111"})
        self.assertRedirects(resp, reverse("carrera_academica:portal_jurado_dashboard"))
        self.assertEqual(self.client.session["portal_jurado"]["persona_id"], self.docente_a.pk)
        self.assertNotEqual(self.client.session.session_key, session_key_previo)
        self.assertEqual(AccesoPortalJurado.objects.filter(accion="link_ok").count(), 1)

    def test_dashboard_sin_sesion_redirige_a_expirada(self):
        resp = self.client.get(reverse("carrera_academica:portal_jurado_dashboard"))
        self.assertRedirects(resp, reverse("carrera_academica:portal_jurado_sesion_expirada"))

    def test_dashboard_lista_solo_las_cas_propias(self):
        self.client.post(self._landing_url(self.raw_a), {"dni": "11111111"})
        resp = self.client.get(reverse("carrera_academica:portal_jurado_dashboard"))
        self.assertContains(resp, self.docente_a.apellido.upper())
        self.assertNotContains(resp, self.docente_b.apellido.upper() + ", " + self.docente_b.nombre)

    def test_idor_detalle_de_otra_ca_da_404(self):
        self.client.post(self._landing_url(self.raw_a), {"dni": "11111111"})
        resp = self.client.get(
            reverse("carrera_academica:portal_jurado_detalle", args=[self.ca_b.pk])
        )
        self.assertEqual(resp.status_code, 404)

    def test_detalle_de_ca_propia_muestra_documentos(self):
        self.client.post(self._landing_url(self.raw_a), {"dni": "11111111"})
        resp = self.client.get(
            reverse("carrera_academica:portal_jurado_detalle", args=[self.ca_a.pk])
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.docente_a.apellido.upper())

    def test_idor_expediente_de_otra_ca_da_404(self):
        """El caso central: jurado A no puede bajar el expediente de la CA de B
        ni siquiera pegando la URL directamente, con su propia sesión válida."""
        self.client.post(self._landing_url(self.raw_a), {"dni": "11111111"})
        resp = self.client.get(
            reverse("carrera_academica:portal_jurado_expediente_completo", args=[self.ca_b.pk])
        )
        self.assertEqual(resp.status_code, 404)

    def test_expediente_de_ca_propia_no_da_404(self):
        self.client.post(self._landing_url(self.raw_a), {"dni": "11111111"})
        resp = self.client.get(
            reverse("carrera_academica:portal_jurado_expediente_completo", args=[self.ca_a.pk])
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "application/pdf")

    def test_idor_documento_de_otra_ca_da_404(self):
        self.client.post(self._landing_url(self.raw_a), {"dni": "11111111"})
        resp = self.client.get(
            reverse("carrera_academica:portal_jurado_documento", args=[self.formulario_b.pk])
        )
        self.assertEqual(resp.status_code, 404)

    def test_documento_propio_no_da_404_y_usa_x_accel_redirect(self):
        self.client.post(self._landing_url(self.raw_a), {"dni": "11111111"})
        resp = self.client.get(
            reverse("carrera_academica:portal_jurado_documento", args=[self.formulario_a.pk])
        )
        self.assertNotEqual(resp.status_code, 404)
        self.assertIn("X-Accel-Redirect", resp)

    def test_logout_limpia_sesion(self):
        self.client.post(self._landing_url(self.raw_a), {"dni": "11111111"})
        self.client.get(reverse("carrera_academica:portal_jurado_logout"))
        resp = self.client.get(reverse("carrera_academica:portal_jurado_dashboard"))
        self.assertRedirects(resp, reverse("carrera_academica:portal_jurado_sesion_expirada"))
