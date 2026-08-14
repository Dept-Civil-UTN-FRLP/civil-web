# carrera_academica/test/test_notificar_portal_jurado.py
"""
Tests de la vista staff-facing que envia los links del Portal de Jurados
(notificar_portal_jurado_view) -- el modal con checkboxes que reemplazo el
envio automatico a los 10 slots.
"""
from datetime import date

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from carrera_academica.models import (
    CarreraAcademica,
    Jurado,
    JuradoExterno,
    TokenPortalJurado,
    Universidad,
)
from planta_docente.models import Asignatura, Cargo, Docente


@override_settings(PORTAL_JURADOS_ENABLED=True)
class NotificarPortalJuradoViewTestCase(TestCase):
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
        self.jurado = Jurado.objects.create(
            departamento="civil", profesor_titular_1=docente,
            profesor_titular_2=self.titular, profesor_suplente_2=self.suplente_sin_dni,
            profesor_titular_3=self.titular,
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
