import json
import logging
from dataclasses import dataclass

from django.conf import settings

logger = logging.getLogger(__name__)

# Centinela que el LLM usa cuando un correo no necesita respuesta. telegram_webhook (paso 06)
# importa esta misma constante para saber cuándo "Aprobar" debe solo marcar como leído en vez
# de mandar una respuesta real — no cambies este string sin actualizar también 06_webhook_telegram.md.
SIN_RESPUESTA_NECESARIA = "(no requiere respuesta)"

PROMPT_SISTEMA = f"""Sos un asistente que ayuda a un director de departamento universitario a \
triar su correo institucional. Para cada correo nuevo:
1. Asignale una categoría corta (una o dos palabras: "Consulta alumno", "Administrativo", \
"Urgente", "Spam", "Reunión", etc.).
2. Escribí un resumen de una o dos frases.
3. Proponé un borrador de respuesta breve y formal en español rioplatense. Si el correo no \
requiere respuesta, escribí exactamente "{SIN_RESPUESTA_NECESARIA}" como acción propuesta.

Devolvé ÚNICAMENTE un JSON con esta forma exacta, sin texto antes ni después:
{{"categoria": "...", "resumen": "...", "accion_propuesta": "..."}}"""


@dataclass
class AnalisisCorreo:
    categoria: str
    resumen: str
    accion_propuesta: str


def _ejemplos_few_shot(limite=5):
    from ..models import HistorialDecisiones

    ejemplos = HistorialDecisiones.ejemplos_para_few_shot(limite=limite)
    if not ejemplos:
        return ""
    bloques = []
    for ej in ejemplos:
        bloque = (
            f"Correo:\nAsunto: {ej.correo_asunto}\nCuerpo: {ej.correo_cuerpo[:500]}\n"
            f"Categoría asignada antes: {ej.categoria_ia}\n"
            f"Acción propuesta antes: {ej.accion_propuesta_ia}\n"
            f"Decisión real del admin: {ej.get_estado_display()}"
        )
        if ej.texto_final and ej.texto_final != ej.accion_propuesta_ia:
            bloque += f"\nTexto final que el admin realmente usó: {ej.texto_final}"
        bloques.append(bloque)
    return "\n\n---\n\n".join(bloques)


def analizar_correo(asunto, cuerpo):
    """Punto de entrada usado por revisar_mails.py. Nunca lanza excepción: si el LLM falla,
    devuelve un AnalisisCorreo vacío/marcado como error para que el correo igual se registre y
    se notifique (sin propuesta), en vez de perderse la corrida entera del cron."""
    if not settings.GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY no configurada: se devuelve un análisis vacío.")
        return AnalisisCorreo(categoria="sin_configurar", resumen="", accion_propuesta="")

    from google import genai
    from google.genai import types

    cliente = genai.Client(api_key=settings.GEMINI_API_KEY)
    ejemplos = _ejemplos_few_shot()
    contenido = (
        (f"Ejemplos de decisiones previas del admin:\n\n{ejemplos}\n\n---\n\n" if ejemplos else "")
        + f"Correo nuevo a analizar:\nAsunto: {asunto}\nCuerpo:\n{cuerpo[:4000]}"
    )

    try:
        respuesta = cliente.models.generate_content(
            model="gemini-2.5-flash",
            contents=contenido,
            config=types.GenerateContentConfig(
                system_instruction=PROMPT_SISTEMA,
                response_mime_type="application/json",
            ),
        )
        datos = json.loads(respuesta.text)
        return AnalisisCorreo(
            categoria=datos.get("categoria", ""),
            resumen=datos.get("resumen", ""),
            accion_propuesta=datos.get("accion_propuesta", ""),
        )
    except Exception:
        logger.exception("Fallo al analizar el correo con el LLM (asunto=%r).", asunto)
        return AnalisisCorreo(categoria="error_llm", resumen="", accion_propuesta="")
