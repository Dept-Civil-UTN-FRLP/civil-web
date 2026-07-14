import hmac
import json
import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import HttpResponseForbidden, HttpResponseServerError, JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import HistorialDecisiones
from .services import o365_service, telegram_service
from .services.llm_service import SIN_RESPUESTA_NECESARIA
from .services.o365_service import GRAPH_SCOPES, get_account

logger = logging.getLogger(__name__)

SESSION_KEY_OAUTH_STATE = "agente_mail_oauth_state"


def _es_superusuario(user):
    return user.is_active and user.is_superuser


superusuario_requerido = user_passes_test(_es_superusuario, login_url="admin:login")


@login_required
@superusuario_requerido
def iniciar_autenticacion(request):
    """Redirige al login oficial de Microsoft para iniciar el Authorization Code Flow."""
    account = get_account()
    url, state = account.con.get_authorization_url(
        requested_scopes=GRAPH_SCOPES,
        redirect_uri=settings.O365_REDIRECT_URI,
    )
    # El "state" hay que conservarlo para validarlo cuando Microsoft redirija de vuelta.
    # Va en la sesión del propio admin que inició el flujo, no en la BD: es de un solo uso
    # y de vida muy corta (dura lo que tarda el admin en loguearse en Microsoft).
    request.session[SESSION_KEY_OAUTH_STATE] = state
    return redirect(url)


@login_required
@superusuario_requerido
def microsoft_callback(request):
    """Redirect URI configurada en Azure AD. Recibe ?code=...&state=..., intercambia el
    código por un token y lo persiste vía DjangoTokenBackend."""
    state_guardado = request.session.pop(SESSION_KEY_OAUTH_STATE, None)
    if not state_guardado:
        messages.error(
            request, "La sesión de autenticación expiró o es inválida. Reintentá desde el inicio."
        )
        return redirect("agente_mail:iniciar_autenticacion")

    if request.GET.get("error"):
        descripcion = request.GET.get("error_description", request.GET["error"])
        logger.error("Microsoft devolvió un error en el callback OAuth: %s", descripcion)
        messages.error(request, f"Microsoft rechazó la autenticación: {descripcion}")
        return redirect("agente_mail:iniciar_autenticacion")

    account = get_account()
    url_completa = request.build_absolute_uri()

    try:
        resultado = account.con.request_token(
            authorization_url=url_completa,
            state=state_guardado,
            redirect_uri=settings.O365_REDIRECT_URI,
        )
    except Exception:
        logger.exception("Fallo al intercambiar el código de autorización por un token.")
        return HttpResponseServerError("No se pudo completar la autenticación con Microsoft.")

    if not resultado:
        messages.error(request, "Microsoft no devolvió un token válido.")
        return redirect("agente_mail:iniciar_autenticacion")

    logger.info("Autenticación con Microsoft Graph completada correctamente.")
    messages.success(request, "Cuenta de Office 365 conectada correctamente.")
    return redirect(reverse("admin:agente_mail_microsofttoken_changelist"))


def _origen_valido(request):
    recibido = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    return hmac.compare_digest(recibido, settings.TELEGRAM_WEBHOOK_SECRET)


def _usuario_autorizado(telegram_user_id):
    return telegram_user_id in settings.TELEGRAM_ADMIN_IDS


@csrf_exempt
@require_POST
def telegram_webhook(request):
    if not settings.TELEGRAM_WEBHOOK_SECRET or not _origen_valido(request):
        logger.warning("telegram_webhook: secret token ausente o inválido.")
        return HttpResponseForbidden("forbidden")

    try:
        update = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        logger.warning("telegram_webhook: body no es JSON válido.")
        return JsonResponse({"ok": False}, status=400)

    if "callback_query" in update:
        _procesar_callback_query(update["callback_query"])
    elif "message" in update:
        _procesar_mensaje_texto(update["message"])
    # Cualquier otro tipo de update (edited_message, etc.) se ignora silenciosamente.

    # Siempre 200: si le devolvés un error a Telegram, reintenta el mismo update varias veces.
    return JsonResponse({"ok": True})


def _procesar_callback_query(callback_query):
    callback_id = callback_query["id"]
    telegram_user_id = callback_query["from"]["id"]

    if not _usuario_autorizado(telegram_user_id):
        logger.warning(
            "telegram_webhook: callback_query de usuario no autorizado (id=%s).", telegram_user_id
        )
        telegram_service.responder_callback(callback_id, "No autorizado.", alerta=True)
        return

    data = callback_query.get("data", "")
    partes = data.split("_", 2)
    if len(partes) != 3 or partes[0] != "dec":
        logger.warning("telegram_webhook: callback_data con formato inesperado: %r", data)
        telegram_service.responder_callback(callback_id)
        return

    _, historial_id, accion = partes
    try:
        historial = HistorialDecisiones.objects.get(pk=int(historial_id))
    except (HistorialDecisiones.DoesNotExist, ValueError):
        telegram_service.responder_callback(callback_id, "Ese correo ya no existe.", alerta=True)
        return

    if historial.estado not in (
        HistorialDecisiones.ESTADO_PENDIENTE,
        HistorialDecisiones.ESTADO_ESPERANDO_TEXTO,
    ):
        # Ya fue decidido antes (doble click, o dos admins). No se reprocesa.
        telegram_service.responder_callback(
            callback_id, f"Ya estaba: {historial.get_estado_display()}.", alerta=True
        )
        return

    if accion == "aprobar":
        historial.decidir(telegram_user_id, HistorialDecisiones.ESTADO_APROBADO)
        _ejecutar_accion_en_correo(historial)
        telegram_service.responder_callback(callback_id, "Aprobado.")
    elif accion == "descartar":
        historial.decidir(telegram_user_id, HistorialDecisiones.ESTADO_DESCARTADO)
        _marcar_correo_como_triado(historial)
        telegram_service.responder_callback(callback_id, "Descartado.")
    elif accion == "modificar":
        historial.marcar_esperando_texto()
        telegram_service.pedir_texto_modificado(historial)
        telegram_service.responder_callback(callback_id, "Esperando el texto…")
        return  # el mensaje original no se edita todavía: sigue "esperando_texto"
    else:
        logger.warning("telegram_webhook: acción desconocida en callback_data: %r", accion)
        telegram_service.responder_callback(callback_id)
        return

    telegram_service.editar_mensaje_tras_decision(historial)


def _procesar_mensaje_texto(message):
    telegram_user_id = message.get("from", {}).get("id")
    if telegram_user_id is None or not _usuario_autorizado(telegram_user_id):
        return

    reply_to = message.get("reply_to_message")
    texto = message.get("text")
    if not reply_to or not texto:
        return

    try:
        historial = HistorialDecisiones.objects.get(
            estado=HistorialDecisiones.ESTADO_ESPERANDO_TEXTO,
            telegram_chat_id=message["chat"]["id"],
            telegram_prompt_message_id=reply_to["message_id"],
        )
    except HistorialDecisiones.DoesNotExist:
        return

    historial.decidir(
        telegram_user_id, HistorialDecisiones.ESTADO_MODIFICADO, texto_final=texto
    )
    _ejecutar_accion_en_correo(historial)
    telegram_service.editar_mensaje_tras_decision(historial)


def _ejecutar_accion_en_correo(historial):
    """Ejecuta en O365 lo que el admin decidió (aprobar/modificar): responde el correo y lo
    marca como leído — salvo que el texto final sea literalmente el centinela
    SIN_RESPUESTA_NECESARIA ("(no requiere respuesta)"), en cuyo caso solo se marca como
    leído, sin enviar nada. Esto cubre el caso de tocar "Aprobar" sobre un correo que el LLM
    catalogó como que no necesita respuesta — sin este chequeo, se mandaría ese texto literal
    como si fuera la respuesta real. Si algo falla acá, la decisión humana ya quedó guardada en
    HistorialDecisiones — lo que se pierde es solo el envío, no el registro ni la trazabilidad
    para few-shot (queda en estado 'error', visible en el admin para reintentar a mano)."""
    try:
        if historial.texto_final.strip() == SIN_RESPUESTA_NECESARIA:
            o365_service.marcar_como_leido(historial.correo_message_id)
        else:
            o365_service.responder_correo(historial.correo_message_id, historial.texto_final)
            o365_service.marcar_como_leido(historial.correo_message_id)
        historial.marcar_enviado()
    except Exception as exc:
        logger.exception(
            "Fallo al ejecutar la acción en O365 para HistorialDecisiones #%s", historial.pk
        )
        historial.marcar_error(str(exc))


def _marcar_correo_como_triado(historial):
    """Para 'descartar': no se responde nada, pero el correo ya fue visto y decidido por el
    admin, así que no debería seguir figurando como no leído en el buzón real."""
    try:
        o365_service.marcar_como_leido(historial.correo_message_id)
    except Exception:
        logger.exception(
            "Fallo al marcar como leído el correo de HistorialDecisiones #%s", historial.pk
        )
