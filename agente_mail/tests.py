from django.test import TestCase
from django.utils import timezone

from .models import HistorialDecisiones, MicrosoftToken


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
