# carrera_academica/test/test_notificar_portal_jurado.py
"""
Tests de la vista staff-facing que envia los links del Portal de Jurados
(notificar_portal_jurado_view) -- el modal con checkboxes que reemplazo el
envio automatico a los 10 slots.
"""
import io
from datetime import date

from django.contrib.auth.models import User
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from pypdf import PdfWriter

from carrera_academica.models import (
    CarreraAcademica,
    Formulario,
    Jurado,
    JuradoExterno,
    TokenPortalJurado,
    Universidad,
    VeedorEstudiante,
    VeedorGraduado,
)
from planta_docente.models import Asignatura, Cargo, Docente


def _pdf_bytes():
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


@override_settings(PORTAL_JURADOS_ENABLED=True)
class NotificarPortalJuradoViewTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        # Aislar los archivos subidos en los tests del media/ real.
        import shutil
        import tempfile

        cls._media_root_temp = tempfile.mkdtemp()
        cls._media_override = override_settings(MEDIA_ROOT=cls._media_root_temp)
        cls._media_override.enable()
        cls._shutil = shutil
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls._media_override.disable()
        cls._shutil.rmtree(cls._media_root_temp, ignore_errors=True)

    def setUp(self):
        self.user = User.objects.create_user(username="staff", password="testpass123")
        self.client.login(username="staff", password="testpass123")

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

        # Formulario con archivo real, para que consolidar_expediente (usado
        # por "enviar copia a concursos") tenga algo para consolidar.
        cv = self.ca.formularios.get(tipo_formulario="CV")
        cv.archivo = SimpleUploadedFile("cv.pdf", _pdf_bytes(), content_type="application/pdf")
        cv.estado = "ENT"
        cv.save()

        universidad = Universidad.objects.create(
            sigla="UNLP", nombre_completo="Universidad Nacional de La Plata", es_utn=False,
        )
        self.titular = JuradoExterno.objects.create(
            apellido="Titular", nombre="Con DNI", email="titular@test.com",
            universidad=universidad, categoria="titular", dni=22222222,
        )
        self.suplente_sin_dni = JuradoExterno.objects.create(
            apellido="Suplente", nombre="Sin DNI", email="suplente@test.com",
            universidad=universidad, categoria="titular",
        )
        self.otro_jurado_externo = JuradoExterno.objects.create(
            apellido="Ajeno", nombre="OtroJurado", email="ajeno@test.com",
            universidad=universidad, categoria="titular", dni=33333333,
        )
        self.veedor_graduado = VeedorGraduado.objects.create(
            apellido="Veedor", nombre="Graduado", email="veedorgrad@test.com",
            titulo="Ingeniero Civil", dni=44444444,
        )
        self.veedor_estudiante = VeedorEstudiante.objects.create(
            apellido="Veedor", nombre="Estudiante", email="veedorest@test.com",
            legajo="9999", dni=55555555,
        )
        self.jurado = Jurado.objects.create(
            departamento="civil", profesor_titular_1=docente,
            profesor_titular_2=self.titular, profesor_suplente_2=self.suplente_sin_dni,
            profesor_titular_3=self.titular,
            veedor_graduado_titular=self.veedor_graduado,
            veedor_estudiante_titular=self.veedor_estudiante,
        )
        self.ca.jurado = self.jurado
        self.ca.save()

        self.url = reverse("carrera_academica:notificar_portal_jurado", args=[self.ca.pk])

    def test_sin_seleccion_no_envia_nada(self):
        resp = self.client.post(self.url, {})
        self.assertRedirects(resp, reverse("carrera_academica:detalle_ca", args=[self.ca.pk]))
        self.assertEqual(len(mail.outbox), 0)

    def test_envia_solo_al_seleccionado(self):
        resp = self.client.post(self.url, {"destinatarios": [f"jurado_externo:{self.titular.pk}"]})
        self.assertRedirects(resp, reverse("carrera_academica:detalle_ca", args=[self.ca.pk]))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["titular@test.com"])
        self.assertEqual(
            TokenPortalJurado.objects.filter(
                tipo_persona="jurado_externo", persona_id=self.titular.pk
            ).count(),
            1,
        )

    def test_sin_dni_no_se_envia_aunque_lo_manden_tildado(self):
        """El checkbox viene disabled en el HTML para estos casos, pero igual
        se valida server-side por si alguien arma el POST a mano."""
        resp = self.client.post(
            self.url, {"destinatarios": [f"jurado_externo:{self.suplente_sin_dni.pk}"]}
        )
        self.assertEqual(len(mail.outbox), 0)
        msgs = [m.message for m in resp.wsgi_request._messages]
        self.assertTrue(any("no tiene DNI" in str(m) for m in msgs))

    def test_valor_de_persona_ajena_al_jurado_se_ignora(self):
        """Un POST manipulado no puede hacer que se le mande el link a alguien
        que no integra este Jurado."""
        resp = self.client.post(
            self.url, {"destinatarios": [f"jurado_externo:{self.otro_jurado_externo.pk}"]}
        )
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(
            TokenPortalJurado.objects.filter(
                tipo_persona="jurado_externo", persona_id=self.otro_jurado_externo.pk
            ).count(),
            0,
        )

    def test_requiere_login(self):
        self.client.logout()
        resp = self.client.post(self.url, {"destinatarios": [f"jurado_externo:{self.titular.pk}"]})
        self.assertEqual(resp.status_code, 302)
        self.assertIn("login", resp.url)

    def test_get_no_permitido(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 405)

    def test_veedores_no_reciben_link_aunque_los_manden_tildados(self):
        """Los veedores no son parte del checklist de destinatarios -- ni
        siquiera un POST manipulado con su tipo_persona:id les manda algo,
        porque listar_miembros_jurado ya no los incluye."""
        resp = self.client.post(
            self.url,
            {"destinatarios": [f"veedor_graduado:{self.veedor_graduado.pk}"]},
        )
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(
            TokenPortalJurado.objects.filter(tipo_persona="veedor_graduado").count(), 0
        )

    def test_enviar_concursos_solo_manda_link_sin_password_en_el_mail(self):
        """Tildar solo 'enviar_concursos' con contraseña, sin ningún
        destinatario del portal, tiene que mandar el link igual (no debe
        bloquearse por "sin selección"), y no es un PDF adjunto."""
        resp = self.client.post(
            self.url, {"enviar_concursos": "1", "concursos_password": "clave123"}
        )
        self.assertRedirects(resp, reverse("carrera_academica:detalle_ca", args=[self.ca.pk]))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["concursosspa@frlp.utn.edu.ar"])
        self.assertEqual(len(mail.outbox[0].attachments), 0)
        self.assertNotIn("clave123", mail.outbox[0].body)

    def test_enviar_concursos_sin_password_no_manda_nada(self):
        resp = self.client.post(self.url, {"enviar_concursos": "1", "concursos_password": ""})
        self.assertEqual(len(mail.outbox), 0)
        msgs = [str(m.message) for m in resp.wsgi_request._messages]
        self.assertTrue(any("contraseña" in m for m in msgs))

    def test_enviar_concursos_junto_con_destinatarios(self):
        resp = self.client.post(
            self.url,
            {
                "destinatarios": [f"jurado_externo:{self.titular.pk}"],
                "enviar_concursos": "1",
                "concursos_password": "clave123",
            },
        )
        self.assertRedirects(resp, reverse("carrera_academica:detalle_ca", args=[self.ca.pk]))
        self.assertEqual(len(mail.outbox), 2)
        destinatarios = {m.to[0] for m in mail.outbox}
        self.assertEqual(destinatarios, {"titular@test.com", "concursosspa@frlp.utn.edu.ar"})
