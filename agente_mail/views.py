import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import HttpResponseServerError
from django.shortcuts import redirect
from django.urls import reverse

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
