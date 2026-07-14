import logging

from django.conf import settings
from O365 import Account
from O365.utils import BaseTokenBackend, Token

logger = logging.getLogger(__name__)

CUENTA_ID_DEFAULT = "principal"

# Permisos delegados de Microsoft Graph. Requieren consentimiento del usuario dueño de la
# casilla (o de un admin del tenant) la primera vez, vía el flujo de 04_autenticacion_microsoft.md.
GRAPH_SCOPES = [
    "offline_access",  # imprescindible: es lo que habilita el refresh_token
    "https://graph.microsoft.com/Mail.ReadWrite",
    "https://graph.microsoft.com/Mail.Send",
    "https://graph.microsoft.com/User.Read",
]


class DjangoTokenBackend(BaseTokenBackend):
    """Persiste el token de O365 en el modelo MicrosoftToken (Postgres) en vez de en un
    archivo. Se instancia una por cuenta (cuenta_id), aunque hoy solo usamos "principal"."""

    def __init__(self, cuenta_id=CUENTA_ID_DEFAULT):
        super().__init__()
        self.cuenta_id = cuenta_id

    def _model(self):
        # Import diferido: evita el AppRegistryNotReady si este módulo se importa antes de
        # que Django termine de cargar las apps (p. ej. desde settings.py).
        from agente_mail.models import MicrosoftToken

        return MicrosoftToken

    def load_token(self):
        MicrosoftToken = self._model()
        try:
            registro = MicrosoftToken.objects.get(cuenta_id=self.cuenta_id)
        except MicrosoftToken.DoesNotExist:
            return None
        self.token = Token(registro.token_data)
        return self.token

    def save_token(self):
        if self.token is None:
            raise ValueError("No hay token en memoria para guardar (self.token es None).")
        MicrosoftToken = self._model()
        MicrosoftToken.objects.update_or_create(
            cuenta_id=self.cuenta_id,
            defaults={"token_data": dict(self.token)},
        )
        logger.info("Token de O365 guardado (cuenta_id=%s).", self.cuenta_id)
        return True

    def delete_token(self):
        MicrosoftToken = self._model()
        borrados, _ = MicrosoftToken.objects.filter(cuenta_id=self.cuenta_id).delete()
        return borrados > 0

    def check_token(self):
        MicrosoftToken = self._model()
        return MicrosoftToken.objects.filter(cuenta_id=self.cuenta_id).exists()


def _credentials():
    return (settings.O365_CLIENT_ID, settings.O365_CLIENT_SECRET)


def get_account(cuenta_id=CUENTA_ID_DEFAULT):
    """Devuelve un O365.Account listo para usar (con auto-refresh vía DjangoTokenBackend).

    No autentica: si no hay token guardado, `account.is_authenticated` da False y hace falta
    pasar por el flujo de 04_autenticacion_microsoft.md primero.
    """
    backend = DjangoTokenBackend(cuenta_id=cuenta_id)
    account = Account(
        _credentials(),
        auth_flow_type="authorization",
        tenant_id=settings.O365_TENANT_ID,
        token_backend=backend,
    )
    return account
