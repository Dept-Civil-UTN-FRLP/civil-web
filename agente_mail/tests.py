import json
from unittest.mock import patch

from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone

from . import views
from .models import HistorialDecisiones, MicrosoftToken
from .services import telegram_service
from .services.o365_service import DjangoTokenBackend

WEBHOOK_URL = "/agente-mail/telegram/webhook/"


class HistorialDecisionesTests(TestCase):
    def setUp(self):
        self.hist = HistorialDecisiones.objects.create(
            correo_message_id="AAMk...1",
            correo_remitente="alguien@frlp.utn.edu.ar",
            correo_asunto="Consulta sobre equivalencias",
            correo_cuerpo="Hola, quería consultar...",
            fecha_recepcion=timezone.now(),
            accion_propuesta_ia="Estimado/a, en respuesta a su consulta...",
        )

    def test_decidir_aprobado_usa_accion_propuesta_como_texto_final(self):
        self.hist.decidir(telegram_user_id=111, nuevo_estado=HistorialDecisiones.ESTADO_APROBADO)
        self.hist.refresh_from_db()
        self.assertEqual(self.hist.estado, HistorialDecisiones.ESTADO_APROBADO)
        self.assertEqual(self.hist.texto_final, self.hist.accion_propuesta_ia)
        self.assertEqual(self.hist.decidido_por_telegram_id, 111)
        self.assertIsNotNone(self.hist.fecha_decision)

    def test_decidir_modificado_usa_texto_final_explicito(self):
        self.hist.decidir(
            telegram_user_id=111,
            nuevo_estado=HistorialDecisiones.ESTADO_MODIFICADO,
            texto_final="Texto reescrito por el admin",
        )
        self.hist.refresh_from_db()
        self.assertEqual(self.hist.texto_final, "Texto reescrito por el admin")

    def test_decidir_con_estado_invalido_lanza_error(self):
        with self.assertRaises(ValueError):
            self.hist.decidir(telegram_user_id=111, nuevo_estado=HistorialDecisiones.ESTADO_PENDIENTE)

    def test_ejemplos_para_few_shot_excluye_pendientes(self):
        HistorialDecisiones.objects.create(
            correo_message_id="AAMk...2",
            correo_remitente="otro@frlp.utn.edu.ar",
            correo_asunto="Otro pendiente",
            correo_cuerpo="...",
            fecha_recepcion=timezone.now(),
        )
        self.hist.decidir(telegram_user_id=111, nuevo_estado=HistorialDecisiones.ESTADO_APROBADO)
        ejemplos = HistorialDecisiones.ejemplos_para_few_shot()
        self.assertEqual(len(ejemplos), 1)
        self.assertEqual(ejemplos[0].pk, self.hist.pk)


class MicrosoftTokenTests(TestCase):
    def test_esta_vencido_true_sin_expires_at(self):
        token = MicrosoftToken.objects.create(cuenta_id="test", token_data={})
        self.assertTrue(token.esta_vencido)

    def test_esta_vencido_false_con_expires_at_futuro(self):
        futuro = timezone.now().timestamp() + 3600
        token = MicrosoftToken.objects.create(
            cuenta_id="test2", token_data={"expires_at": futuro}
        )
        self.assertFalse(token.esta_vencido)


class DjangoTokenBackendTests(TestCase):
    def test_save_y_load_hacen_round_trip(self):
        backend = DjangoTokenBackend(cuenta_id="test")
        backend.token = {
            "access_token": "abc123",
            "refresh_token": "def456",
            "expires_at": 9999999999,
            "token_type": "Bearer",
        }
        backend.save_token()

        backend2 = DjangoTokenBackend(cuenta_id="test")
        token_cargado = backend2.load_token()
        self.assertEqual(token_cargado["access_token"], "abc123")
        self.assertEqual(token_cargado["refresh_token"], "def456")

    def test_check_token_false_si_no_existe(self):
        backend = DjangoTokenBackend(cuenta_id="inexistente")
        self.assertFalse(backend.check_token())

    def test_load_token_none_si_no_existe(self):
        backend = DjangoTokenBackend(cuenta_id="inexistente")
        self.assertIsNone(backend.load_token())

    def test_delete_token(self):
        backend = DjangoTokenBackend(cuenta_id="borrar")
        backend.token = {"access_token": "x"}
        backend.save_token()
        self.assertTrue(backend.delete_token())
        self.assertFalse(backend.check_token())


class TelegramServiceTests(TestCase):
    def setUp(self):
        self.hist = HistorialDecisiones.objects.create(
            correo_message_id="AAMk...telegram",
            correo_remitente="alguien@frlp.utn.edu.ar",
            correo_asunto="Prueba",
            correo_cuerpo="cuerpo",
            fecha_recepcion=timezone.now(),
            accion_propuesta_ia="Borrador de respuesta",
        )

    @patch("agente_mail.services.telegram_service.requests.post")
    def test_enviar_notificacion_decision_guarda_chat_y_message_id(self, mock_post):
        mock_post.return_value.raise_for_status.return_value = None
        mock_post.return_value.json.return_value = {
            "ok": True,
            "result": {"chat": {"id": 555}, "message_id": 42},
        }

        ok = telegram_service.enviar_notificacion_decision(self.hist)

        self.assertTrue(ok)
        self.hist.refresh_from_db()
        self.assertEqual(self.hist.telegram_chat_id, 555)
        self.assertEqual(self.hist.telegram_message_id, 42)

    @patch("agente_mail.services.telegram_service.requests.post")
    def test_enviar_notificacion_decision_devuelve_false_si_telegram_falla(self, mock_post):
        mock_post.return_value.raise_for_status.return_value = None
        mock_post.return_value.json.return_value = {"ok": False, "description": "bot bloqueado"}

        ok = telegram_service.enviar_notificacion_decision(self.hist)

        self.assertFalse(ok)
        self.hist.refresh_from_db()
        self.assertIsNone(self.hist.telegram_message_id)

    @patch("agente_mail.services.telegram_service.requests.post")
    def test_editar_mensaje_sin_ids_previos_no_llama_a_telegram(self, mock_post):
        ok = telegram_service.editar_mensaje_tras_decision(self.hist)
        self.assertFalse(ok)
        mock_post.assert_not_called()


@override_settings(
    TELEGRAM_WEBHOOK_SECRET="secreto-de-test",
    TELEGRAM_ADMIN_IDS={999},
)
class TelegramWebhookTests(TestCase):
    """Invoca views.telegram_webhook directamente con RequestFactory, sin pasar por la
    resolución de URLs: config/urls.py registra agente_mail.urls condicionalmente, a nivel de
    módulo, según settings.AGENTE_MAIL_ENABLED en el momento en que Django importa el
    urlconf — @override_settings no puede forzar esa reimportación (el módulo ya quedó en
    sys.modules), así que un test que dependa de esa URL real fallaría con 404 aunque
    AGENTE_MAIL_ENABLED esté en True durante el test. Llamar a la vista directamente evita el
    problema por completo y sigue ejercitando toda la lógica real del webhook."""

    def setUp(self):
        self.factory = RequestFactory()
        self.hist = HistorialDecisiones.objects.create(
            correo_message_id="AAMk...webhook",
            correo_remitente="alguien@frlp.utn.edu.ar",
            correo_asunto="Prueba webhook",
            correo_cuerpo="cuerpo",
            fecha_recepcion=timezone.now(),
            accion_propuesta_ia="Borrador",
        )

    def _post(self, payload, secret="secreto-de-test"):
        request = self.factory.post(
            WEBHOOK_URL,
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN=secret,
        )
        return views.telegram_webhook(request)

    def test_sin_secret_token_devuelve_403(self):
        request = self.factory.post(
            WEBHOOK_URL, data=json.dumps({}), content_type="application/json"
        )
        respuesta = views.telegram_webhook(request)
        self.assertEqual(respuesta.status_code, 403)

    def test_secret_token_incorrecto_devuelve_403(self):
        respuesta = self._post({}, secret="otro")
        self.assertEqual(respuesta.status_code, 403)

    @patch("agente_mail.services.telegram_service.requests.post")
    def test_usuario_no_autorizado_no_modifica_el_historial(self, mock_post):
        mock_post.return_value.raise_for_status.return_value = None
        mock_post.return_value.json.return_value = {"ok": True, "result": {}}

        respuesta = self._post({
            "callback_query": {
                "id": "cbq1",
                "from": {"id": 111},  # no está en TELEGRAM_ADMIN_IDS={999}
                "data": f"dec_{self.hist.pk}_aprobar",
            }
        })

        self.assertEqual(respuesta.status_code, 200)
        self.hist.refresh_from_db()
        self.assertEqual(self.hist.estado, HistorialDecisiones.ESTADO_PENDIENTE)

    @patch("agente_mail.services.o365_service.marcar_como_leido")
    @patch("agente_mail.services.o365_service.responder_correo")
    @patch("agente_mail.services.telegram_service.requests.post")
    def test_aprobar_ejecuta_la_accion_y_marca_enviado(
        self, mock_post, mock_responder, mock_marcar_leido
    ):
        mock_post.return_value.raise_for_status.return_value = None
        mock_post.return_value.json.return_value = {"ok": True, "result": {}}

        respuesta = self._post({
            "callback_query": {
                "id": "cbq2",
                "from": {"id": 999},
                "data": f"dec_{self.hist.pk}_aprobar",
            }
        })

        self.assertEqual(respuesta.status_code, 200)
        self.hist.refresh_from_db()
        self.assertEqual(self.hist.estado, HistorialDecisiones.ESTADO_ENVIADO)
        self.assertEqual(self.hist.decidido_por_telegram_id, 999)
        mock_responder.assert_called_once_with(self.hist.correo_message_id, self.hist.texto_final)
        mock_marcar_leido.assert_called_once()

    @patch("agente_mail.services.o365_service.marcar_como_leido")
    @patch("agente_mail.services.o365_service.responder_correo")
    @patch("agente_mail.services.telegram_service.requests.post")
    def test_aprobar_sin_respuesta_necesaria_no_envia_nada(
        self, mock_post, mock_responder, mock_marcar_leido
    ):
        mock_post.return_value.raise_for_status.return_value = None
        mock_post.return_value.json.return_value = {"ok": True, "result": {}}
        self.hist.accion_propuesta_ia = "(no requiere respuesta)"
        self.hist.save(update_fields=["accion_propuesta_ia"])

        respuesta = self._post({
            "callback_query": {
                "id": "cbq4",
                "from": {"id": 999},
                "data": f"dec_{self.hist.pk}_aprobar",
            }
        })

        self.assertEqual(respuesta.status_code, 200)
        self.hist.refresh_from_db()
        self.assertEqual(self.hist.estado, HistorialDecisiones.ESTADO_ENVIADO)
        mock_responder.assert_not_called()
        mock_marcar_leido.assert_called_once()

    @patch("agente_mail.services.telegram_service.requests.post")
    def test_doble_click_en_decision_ya_tomada_no_reprocesa(self, mock_post):
        mock_post.return_value.raise_for_status.return_value = None
        mock_post.return_value.json.return_value = {"ok": True, "result": {}}
        self.hist.decidir(999, HistorialDecisiones.ESTADO_DESCARTADO)

        respuesta = self._post({
            "callback_query": {
                "id": "cbq3",
                "from": {"id": 999},
                "data": f"dec_{self.hist.pk}_aprobar",
            }
        })

        self.assertEqual(respuesta.status_code, 200)
        self.hist.refresh_from_db()
        self.assertEqual(self.hist.estado, HistorialDecisiones.ESTADO_DESCARTADO)
