# carrera_academica/services/jurado_portal_service.py
"""
Resolución de identidad para el Portal de Jurados: dado un tipo de persona + id
(o un DNI), encuentra a qué Jurado(s) pertenece y qué CarreraAcademica(s) tiene
asignadas. Jurado es reutilizable: una misma persona puede estar en varias CA
a la vez.
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

# (tipo_persona, atributo en Jurado, etiqueta legible, es_titular, numero de profesor)
# Los veedores quedan afuera a propósito: no reciben documentación por el portal.
ROLES_JURADO = [
    ("docente", "profesor_titular_1", "Profesor Titular 1", True, 1),
    ("docente", "profesor_suplente_1", "Profesor Suplente 1", False, 1),
    ("jurado_externo", "profesor_titular_2", "Profesor Titular 2", True, 2),
    ("jurado_externo", "profesor_suplente_2", "Profesor Suplente 2", False, 2),
    ("jurado_externo", "profesor_titular_3", "Profesor Titular 3", True, 3),
    ("jurado_externo", "profesor_suplente_3", "Profesor Suplente 3", False, 3),
]


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


def obtener_checklist_documentos(ca: CarreraAcademica, evaluacion: Optional[Evaluacion]) -> List:
    """
    Checklist completo de documentación académica pertinente para el jurado,
    entregada o no:

    - Generales de la CA (CV, F01, F02, F03): se crean una sola vez al abrir la CA.
    - Anuales de los años evaluados (F04, F05, F06, F07, ENC, F13): se crean por año
      al abrir la CA.

    Deliberadamente NO se incluyen F08-F12 (nómina de junta, notificaciones, acta
    dictamen) -- son notificaciones/actas administrativas dirigidas al jurado mismo
    o generadas después de su decisión, no documentación académica para revisar.

    A diferencia de EmailService.obtener_documentos_pertinentes (que solo trae lo ya
    entregado, porque no se puede adjuntar un archivo inexistente a un mail), acá se
    traen también los pendientes -- el jurado tiene que poder ver qué falta, no solo
    lo que ya está.
    """
    filtro = Q(anio_correspondiente__isnull=True, evaluacion__isnull=True)
    if evaluacion:
        filtro |= Q(anio_correspondiente__in=evaluacion.anios_evaluados, evaluacion__isnull=True)

    return list(
        ca.formularios.filter(filtro).order_by("tipo_formulario", "anio_correspondiente")
    )


def listar_miembros_jurado(jurado: Jurado) -> List[dict]:
    """
    Enumera los hasta 6 ocupantes de los slots "profesor" de un Jurado (titular +
    suplente de cada uno de los 3 profesores -- los veedores no entran acá, no
    reciben documentación), con lo necesario para armar el modal de "a quién
    notificar": si tiene DNI cargado, su email, y cuándo se le mandó el último link
    (para poder reenviar a uno solo sin volver a molestar al resto).
    """
    from carrera_academica.models import TokenPortalJurado
    from carrera_academica.services.email_service import EmailService

    miembros = []
    for tipo_persona, atributo, rol_label, es_titular, numero in ROLES_JURADO:
        persona = getattr(jurado, atributo)
        if not persona:
            continue

        ultimo_token = (
            TokenPortalJurado.objects.filter(
                tipo_persona=tipo_persona, persona_id=persona.pk
            )
            .order_by("-creado")
            .first()
        )

        miembros.append(
            {
                "tipo_persona": tipo_persona,
                "persona_id": persona.pk,
                "valor": f"{tipo_persona}:{persona.pk}",
                "persona": persona,
                "rol_label": rol_label,
                "es_titular": es_titular,
                "numero": numero,
                "email": EmailService.obtener_email_miembro(persona),
                "tiene_dni": obtener_dni(persona) is not None,
                "ultimo_token": ultimo_token,
            }
        )
    return miembros


def listar_filas_jurado(jurado: Jurado) -> List[dict]:
    """
    Igual que listar_miembros_jurado, pero agrupado en 3 filas (una por cada
    profesor) con las columnas titular/suplente ya emparejadas -- para el modal
    de notificación, que se muestra como tabla Titular | Suplente.
    """
    miembros = listar_miembros_jurado(jurado)
    por_numero = {1: {}, 2: {}, 3: {}}
    for m in miembros:
        por_numero[m["numero"]]["titular" if m["es_titular"] else "suplente"] = m

    etiquetas = {1: "Profesor 1 (Interno)", 2: "Profesor 2 (Externo)", 3: "Profesor 3 (Externo)"}
    return [
        {
            "etiqueta": etiquetas[n],
            "titular": por_numero[n].get("titular"),
            "suplente": por_numero[n].get("suplente"),
        }
        for n in (1, 2, 3)
    ]
