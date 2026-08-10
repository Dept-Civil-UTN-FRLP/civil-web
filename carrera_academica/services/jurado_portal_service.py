# carrera_academica/services/jurado_portal_service.py
"""
Resolución de identidad para el Portal de Jurados: dado un tipo de persona + id
(o un DNI), encuentra a qué Jurado(s) pertenece y qué CarreraAcademica(s) tiene
asignadas. No usa el modelo JuntaEvaluadora (viejo, 1 por CA) — solo Jurado,
que soporta que una misma persona esté en varias CA a la vez.
"""
from typing import List, Optional

from django.db.models import Q, QuerySet

from carrera_academica.models import CarreraAcademica, Evaluacion, Jurado
from carrera_academica.models import JuradoExterno, VeedorGraduado, VeedorEstudiante
from planta_docente.models import Docente

MODELOS_PERSONA = {
    "docente": Docente,
    "jurado_externo": JuradoExterno,
    "veedor_graduado": VeedorGraduado,
    "veedor_estudiante": VeedorEstudiante,
}


def resolver_persona(tipo_persona: str, persona_id: int):
    """Devuelve la instancia del modelo correspondiente, o None si no existe."""
    modelo = MODELOS_PERSONA.get(tipo_persona)
    if not modelo:
        return None
    return modelo.objects.filter(pk=persona_id).first()


def obtener_dni(persona) -> Optional[int]:
    """Abstrae la diferencia de nombre de campo: Docente.documento vs .dni en el resto."""
    if isinstance(persona, Docente):
        return persona.documento
    return getattr(persona, "dni", None)


def buscar_jurados_por_persona(tipo_persona: str, persona_id: int) -> QuerySet:
    """Jurado(s) donde esta persona ocupa alguno de los 6 slots (titular o suplente)."""
    if tipo_persona == "docente":
        q = Q(profesor_titular_1_id=persona_id) | Q(profesor_suplente_1_id=persona_id)
    elif tipo_persona == "jurado_externo":
        q = (
            Q(profesor_titular_2_id=persona_id)
            | Q(profesor_suplente_2_id=persona_id)
            | Q(profesor_titular_3_id=persona_id)
            | Q(profesor_suplente_3_id=persona_id)
        )
    elif tipo_persona == "veedor_graduado":
        q = Q(veedor_graduado_titular_id=persona_id) | Q(
            veedor_graduado_suplente_id=persona_id
        )
    elif tipo_persona == "veedor_estudiante":
        q = Q(veedor_estudiante_titular_id=persona_id) | Q(
            veedor_estudiante_suplente_id=persona_id
        )
    else:
        return Jurado.objects.none()

    return Jurado.objects.filter(q).distinct()


def obtener_cas_para_persona(tipo_persona: str, persona_id: int) -> QuerySet:
    """
    Todas las CarreraAcademica vinculadas a esta persona vía Jurado.
    Se consulta en vivo en cada request — nunca se cachea en sesión.
    """
    jurados = buscar_jurados_por_persona(tipo_persona, persona_id)
    return (
        CarreraAcademica.objects.filter(jurado__in=jurados)
        .distinct()
        .select_related("cargo__docente", "cargo__asignatura")
    )


def obtener_evaluacion_relevante(ca: CarreraAcademica) -> Optional[Evaluacion]:
    """
    La evaluación que corresponde mostrar por defecto: la Programada más reciente,
    o si no hay ninguna, la más reciente en general.
    """
    evaluacion = ca.evaluaciones.filter(estado="PRO").order_by("-numero_evaluacion").first()
    if evaluacion:
        return evaluacion
    return ca.evaluaciones.order_by("-numero_evaluacion").first()


def obtener_documentos_pertinentes(ca: CarreraAcademica) -> List:
    """Mismos documentos que hoy se adjuntan por mail (EmailService), para la evaluación relevante."""
    from carrera_academica.services.email_service import EmailService

    evaluacion = obtener_evaluacion_relevante(ca)
    if not evaluacion:
        return []
    return EmailService.obtener_documentos_pertinentes(ca, evaluacion.anios_evaluados)
