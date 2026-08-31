# carrera_academica/services/token_portal_service.py
"""
Generación y verificación de tokens del Portal de Jurados.
Se guarda solo el hash (sha256) del secreto — el valor crudo se devuelve una
única vez, en el momento de creación, para armar el link del email, y nunca
se persiste.
"""
import hashlib
import secrets
from datetime import timedelta
from typing import Optional, Tuple

from django.conf import settings
from django.contrib.auth.models import User
from django.utils import timezone

from carrera_academica.models import CarreraAcademica, TokenPortalConcursos, TokenPortalJurado


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def crear_token(
    tipo_persona: str, persona_id: int, creado_por: Optional[User] = None
) -> Tuple[TokenPortalJurado, str]:
    """
    Crea un token nuevo para esta persona, revocando cualquier token activo
    previo (un solo link activo por persona a la vez).
    """
    TokenPortalJurado.objects.filter(
        tipo_persona=tipo_persona,
        persona_id=persona_id,
        revocado=False,
    ).update(revocado=True, fecha_revocado=timezone.now())

    raw = secrets.token_urlsafe(32)
    token = TokenPortalJurado.objects.create(
        tipo_persona=tipo_persona,
        persona_id=persona_id,
        token_hash=_hash(raw),
        creado_por=creado_por,
        expira=timezone.now()
        + timedelta(days=settings.PORTAL_JURADO_TOKEN_DIAS_VALIDEZ),
    )
    return token, raw


def verificar_token(raw_secret: str) -> Optional[TokenPortalJurado]:
    """Devuelve el token si es válido (existe, no revocado, no vencido); None si no."""
    if not raw_secret:
        return None
    return TokenPortalJurado.objects.filter(
        token_hash=_hash(raw_secret),
        revocado=False,
        expira__gt=timezone.now(),
    ).first()


def crear_token_concursos(
    ca: CarreraAcademica, password: str, creado_por: Optional[User] = None
) -> Tuple[TokenPortalConcursos, str]:
    """
    Crea un link + contraseña para compartir el expediente de esta CA con una
    casilla institucional (no una persona con DNI). Revoca cualquier link
    activo previo de esa misma CA -- uno solo a la vez, igual que con los
    jurados.
    """
    TokenPortalConcursos.objects.filter(
        carrera_academica=ca, revocado=False
    ).update(revocado=True)

    raw = secrets.token_urlsafe(32)
    token = TokenPortalConcursos.objects.create(
        carrera_academica=ca,
        token_hash=_hash(raw),
        password_hash=_hash(password),
        creado_por=creado_por,
        expira=timezone.now()
        + timedelta(days=settings.PORTAL_JURADO_TOKEN_DIAS_VALIDEZ),
    )
    return token, raw


def verificar_token_concursos(raw_secret: str) -> Optional[TokenPortalConcursos]:
    """Devuelve el token si es válido (existe, no revocado, no vencido); None si no."""
    if not raw_secret:
        return None
    return TokenPortalConcursos.objects.filter(
        token_hash=_hash(raw_secret),
        revocado=False,
        expira__gt=timezone.now(),
    ).first()


def verificar_password_concursos(token: TokenPortalConcursos, password: str) -> bool:
    if not password:
        return False
    return _hash(password) == token.password_hash
