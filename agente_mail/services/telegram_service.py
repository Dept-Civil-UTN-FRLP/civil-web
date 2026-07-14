import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

TIMEOUT_SEGUNDOS = 10


def _url(metodo):
    return f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/{metodo}"


def _post(metodo, payload):
    try:
        respuesta = requests.post(_url(metodo), json=payload, timeout=TIMEOUT_SEGUNDOS)
        respuesta.raise_for_status()
    except requests.RequestException:
        logger.exception("Fallo al llamar a Telegram (%s) con payload=%s", metodo, payload)
        return None

    data = respuesta.json()
    if not data.get("ok"):
        logger.error("Telegram respondió ok=False en %s: %s", metodo, data)
        return None
    return data["result"]


def _teclado_decision(historial_id):
    return {
        "inline_keyboard": [[
            {"text": "✅ Aprobar", "callback_data": f"dec_{historial_id}_aprobar"},
            {"text": "✏️ Modificar", "callback_data": f"dec_{historial_id}_modificar"},
            {"text": "🗑 Descartar", "callback_data": f"dec_{historial_id}_descartar"},
        ]]
    }


def _texto_notificacion(historial):
    categoria = historial.categoria_ia or "sin categoría"
    resumen = historial.resumen_ia or "(sin resumen)"
    accion = historial.accion_propuesta_ia or "(el LLM no propuso nada)"
    return (
        f"📨 <b>{historial.correo_asunto}</b>\n"
        f"De: {historial.correo_remitente}\n"
        f"Categoría: {categoria}\n\n"
        f"<b>Resumen:</b> {resumen}\n\n"
        f"<b>Acción propuesta:</b>\n{accion}"
    )


def enviar_notificacion_decision(historial):
    """Manda el mensaje inicial con los 3 botones a TELEGRAM_ADMIN_CHAT y guarda
    chat_id/message_id en `historial` para poder editarlo más tarde. Devuelve True/False."""
    resultado = _post(
        "sendMessage",
        {
            "chat_id": settings.TELEGRAM_ADMIN_CHAT,
            "text": _texto_notificacion(historial),
            "parse_mode": "HTML",
            "reply_markup": _teclado_decision(historial.pk),
        },
    )
    if resultado is None:
        return False

    historial.telegram_chat_id = resultado["chat"]["id"]
    historial.telegram_message_id = resultado["message_id"]
    historial.save(update_fields=["telegram_chat_id", "telegram_message_id"])
    return True


def editar_mensaje_tras_decision(historial):
    """Reemplaza el mensaje original (ya sin botones activos) mostrando qué se decidió, para
    que un segundo click sobre una decisión ya tomada no dispare una segunda ejecución."""
    if not historial.telegram_chat_id or not historial.telegram_message_id:
        logger.warning(
            "HistorialDecisiones #%s no tiene telegram_chat_id/message_id: no se puede editar.",
            historial.pk,
        )
        return False
    texto = _texto_notificacion(historial) + f"\n\n— <i>{historial.get_estado_display()}</i> —"
    resultado = _post(
        "editMessageText",
        {
            "chat_id": historial.telegram_chat_id,
            "message_id": historial.telegram_message_id,
            "text": texto,
            "parse_mode": "HTML",
        },
    )
    return resultado is not None


def pedir_texto_modificado(historial):
    """Se usa cuando el admin toca "✏️ Modificar": pide el texto nuevo con ForceReply y guarda
    el message_id de ESE pedido en `telegram_prompt_message_id`. telegram_webhook (paso 06)
    matchea la respuesta contra ese id puntual — así, si hay dos correos en estado
    "esperando_texto" al mismo tiempo, la respuesta de texto no se le asigna al que no
    corresponde."""
    resultado = _post(
        "sendMessage",
        {
            "chat_id": historial.telegram_chat_id,
            "text": f"Escribí el texto final para «{historial.correo_asunto}»:",
            "reply_markup": {"force_reply": True, "selective": True},
        },
    )
    if resultado is None:
        return False
    historial.telegram_prompt_message_id = resultado["message_id"]
    historial.save(update_fields=["telegram_prompt_message_id"])
    return True


def responder_callback(callback_query_id, texto=None, alerta=False):
    """Apaga el ícono de "cargando" del botón en el cliente de Telegram. Es obligatorio
    llamarlo por cada callback_query recibido, incluso si no hacés nada más — si no, el botón
    queda girando indefinidamente en la app del usuario aunque el webhook ya respondió 200."""
    payload = {"callback_query_id": callback_query_id}
    if texto:
        payload["text"] = texto
        payload["show_alert"] = alerta
    return _post("answerCallbackQuery", payload) is not None


def configurar_webhook(url_webhook):
    """Registra la URL del webhook en Telegram, con el secret token que el webhook va a
    validar en cada request entrante. Se ejecuta una sola vez por deploy/dominio, no en cada
    request — ver 09_checklist_puesta_en_marcha.md para cuándo correrlo."""
    return _post(
        "setWebhook",
        {
            "url": url_webhook,
            "secret_token": settings.TELEGRAM_WEBHOOK_SECRET,
            "allowed_updates": ["callback_query", "message"],
        },
    )
