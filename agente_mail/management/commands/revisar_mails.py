import logging

from django.core.management.base import BaseCommand

from agente_mail.models import HistorialDecisiones
from agente_mail.services import llm_service, o365_service, telegram_service

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Busca correos sin leer en la casilla institucional, los analiza con el LLM y " \
           "notifica al admin por Telegram para que decida qué hacer con cada uno."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limite",
            type=int,
            default=10,
            help="Máximo de correos nuevos a procesar en esta corrida (default: 10).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="No manda nada a Telegram ni al LLM: solo lista los correos sin leer que "
                 "encontraría y si ya están registrados en HistorialDecisiones.",
        )

    def handle(self, *args, **options):
        limite = options["limite"]
        dry_run = options["dry_run"]

        try:
            account = o365_service.obtener_cuenta_autenticada()
        except RuntimeError as exc:
            self.stderr.write(self.style.ERROR(str(exc)))
            return

        inbox = account.mailbox().inbox_folder()
        query = inbox.new_query().on_attribute("isRead").equals(False)
        mensajes = inbox.get_messages(limit=limite, query=query, order_by="receivedDateTime asc")

        procesados = 0
        for mensaje in mensajes:
            if HistorialDecisiones.objects.filter(correo_message_id=mensaje.object_id).exists():
                logger.debug("Correo %s ya estaba registrado, se omite.", mensaje.object_id)
                continue

            if dry_run:
                self.stdout.write(f"[dry-run] {mensaje.subject} — {mensaje.sender.address}")
                continue

            self._procesar_mensaje(mensaje)
            procesados += 1

        self.stdout.write(self.style.SUCCESS(f"Revisión completada. {procesados} correo(s) nuevo(s) procesado(s)."))

    def _procesar_mensaje(self, mensaje):
        cuerpo_texto = mensaje.get_body_text() or ""
        analisis = llm_service.analizar_correo(mensaje.subject, cuerpo_texto)

        historial = HistorialDecisiones.objects.create(
            correo_message_id=mensaje.object_id,
            correo_remitente=mensaje.sender.address,
            correo_asunto=mensaje.subject or "(sin asunto)",
            correo_cuerpo=cuerpo_texto,
            fecha_recepcion=mensaje.received,
            categoria_ia=analisis.categoria,
            resumen_ia=analisis.resumen,
            accion_propuesta_ia=analisis.accion_propuesta,
        )

        enviado = telegram_service.enviar_notificacion_decision(historial)
        if not enviado:
            logger.error(
                "No se pudo notificar por Telegram el correo #%s (%s). Queda pendiente en la "
                "base, se puede revisar manualmente desde el admin.",
                historial.pk,
                historial.correo_asunto,
            )
