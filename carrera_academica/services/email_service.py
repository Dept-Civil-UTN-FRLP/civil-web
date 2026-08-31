# carrera_academica/services/email_service.py
"""
Servicio para manejo de envío de emails relacionados con Carrera Académica.
"""
import logging
from typing import List, Optional
from django.db.models import Q

from django.core.mail import EmailMessage
from django.template.loader import render_to_string

from carrera_academica.models import (
    CarreraAcademica,
    Evaluacion,
    Formulario,
)
from planta_docente.models import Docente

logger = logging.getLogger(__name__)

CONCURSOS_EMAIL = "concursosspa@frlp.utn.edu.ar"


class EmailService:
    """Servicio centralizado para envío de emails de Carrera Académica."""

    @staticmethod
    def enviar_link_portal_jurado(
        persona,
        tipo_persona: str,
        ca: CarreraAcademica,
        request,
        creado_por=None,
    ) -> tuple[bool, str]:
        """
        Envía a un ocupante de un slot de Jurado su link personal al Portal
        de Jurados (reemplaza el envío de PDFs adjuntos por un link).

        Args:
            persona: instancia de Docente/JuradoExterno/VeedorGraduado/VeedorEstudiante
            tipo_persona: uno de TokenPortalJurado.TIPO_PERSONA_CHOICES
            ca: CarreraAcademica que motiva el envío (solo para el asunto/cuerpo del mail)
            request: HttpRequest actual, para armar la URL absoluta
            creado_por: usuario que dispara el envío (para auditoría del token)
        """
        from django.conf import settings
        from django.urls import reverse
        from carrera_academica.services.token_portal_service import crear_token

        destinatario = EmailService.obtener_email_miembro(persona)
        if not destinatario:
            return False, f"{persona} no tiene email registrado"

        _token_obj, raw_token = crear_token(tipo_persona, persona.pk, creado_por)
        url_portal = request.build_absolute_uri(
            reverse("carrera_academica:portal_jurado_landing", args=[raw_token])
        )

        html_body = render_to_string(
            "emails/ca_portal_jurado_link.html",
            {
                "persona": persona,
                "ca": ca,
                "url_portal": url_portal,
                "dias_validez": settings.PORTAL_JURADO_TOKEN_DIAS_VALIDEZ,
            },
        )

        email = EmailMessage(
            subject=f"Portal de Jurados - Documentación de {ca.cargo.docente}",
            body=html_body,
            from_email=None,
            to=[destinatario],
        )
        email.content_subtype = "html"

        try:
            email.send()
            logger.info(
                f"Link de portal de jurado enviado a {destinatario} ({tipo_persona}#{persona.pk})"
            )
            return True, f"Enlace enviado a {destinatario}"
        except Exception as e:
            logger.error(f"Error enviando link de portal de jurado a {destinatario}: {e}")
            return False, f"Error al enviar: {str(e)}"

    @staticmethod
    def enviar_link_concursos(
        ca: CarreraAcademica, password: str, request, creado_por=None
    ) -> tuple[bool, str]:
        """
        Manda a la casilla institucional de Concursos un link personal (no un
        PDF adjunto, para no pesar el mail) para descargar el expediente
        completo de ESTA CA puntual. Como no es una persona con DNI, la
        verificación es con una contraseña que elige quien genera el link acá
        mismo -- esa contraseña NO se incluye en el mail, se comunica por
        otro medio (el mail solo explica que hace falta pedirla).
        """
        from carrera_academica.services import token_portal_service
        from django.conf import settings
        from django.urls import reverse

        token, raw = token_portal_service.crear_token_concursos(ca, password, creado_por)
        url_portal = request.build_absolute_uri(
            reverse("carrera_academica:portal_concursos_landing", args=[raw])
        )

        html_body = render_to_string(
            "emails/ca_portal_concursos_link.html",
            {
                "ca": ca,
                "url_portal": url_portal,
                "dias_validez": settings.PORTAL_JURADO_TOKEN_DIAS_VALIDEZ,
            },
        )

        email = EmailMessage(
            subject=f"Expediente de Carrera Académica - {ca.cargo.docente}",
            body=html_body,
            from_email=None,
            to=[CONCURSOS_EMAIL],
        )
        email.content_subtype = "html"

        try:
            email.send()
            logger.info(f"Link de portal de concursos enviado para CA {ca.pk}")
            return True, f"Enlace enviado a {CONCURSOS_EMAIL}"
        except Exception as e:
            logger.error(f"Error enviando link de concursos para CA {ca.pk}: {e}")
            return False, f"Error al enviar: {str(e)}"

    @staticmethod
    def enviar_primera_notificacion(
        ca: CarreraAcademica,
        fecha_limite: str = None,
    ) -> tuple[bool, str]:
        """
        Envía la primera notificación formal al docente al abrir el expediente de CA.
        Usa el template HTML ca_primera_notificacion.html con el diseño institucional.

        Args:
            ca: Instancia de CarreraAcademica
            fecha_limite: Fecha límite de presentación (texto, ej: "30 de agosto de 2026")

        Returns:
            tuple: (exito, mensaje)
        """
        from django.utils import timezone
        from carrera_academica.services.document_service import DocumentService
        from collections import defaultdict

        docente = ca.cargo.docente
        correo_principal = docente.correos.filter(principal=True).first()

        if not correo_principal:
            return False, f"El docente {docente} no tiene correo principal registrado"

        anio_actual = timezone.now().year
        tipos_a_notificar = ["F02", "F04", "F05"]

        formularios_pendientes = Formulario.objects.filter(
            carrera_academica=ca,
            estado="PEN",
            tipo_formulario__in=tipos_a_notificar,
        ).filter(
            Q(anio_correspondiente__isnull=True) | Q(anio_correspondiente__lte=anio_actual)
        )

        if not formularios_pendientes.exists():
            return False, "No hay formularios pendientes para notificar"

        formularios_por_tipo = defaultdict(list)
        for f in formularios_pendientes:
            formularios_por_tipo[f.tipo_formulario].append(f)

        def _anios_texto(tipo):
            anios = sorted(
                f.anio_correspondiente
                for f in formularios_por_tipo.get(tipo, [])
                if f.anio_correspondiente
            )
            return ", ".join(str(a) for a in anios) if anios else ""

        cargo_info = (
            f"{ca.cargo.get_categoria_display()} {ca.cargo.get_caracter_display()} "
            f"en la asignatura {ca.cargo.asignatura.nombre.title()}"
        )

        context = {
            "docente": docente,
            "asignatura": ca.cargo.asignatura.nombre.title(),
            "cargo_info": cargo_info,
            "fecha_limite": fecha_limite,
            "tiene_f02": "F02" in formularios_por_tipo,
            "tiene_f04": "F04" in formularios_por_tipo,
            "tiene_f05": "F05" in formularios_por_tipo,
            "anios_f04": _anios_texto("F04"),
            "anios_f05": _anios_texto("F05"),
        }

        html_body = render_to_string("emails/ca_primera_notificacion.html", context)

        email = EmailMessage(
            subject=f"Apertura de Expediente de Carrera Académica – {ca.cargo.asignatura.nombre.title()}",
            body=html_body,
            from_email=None,
            to=[correo_principal.email],
        )
        email.content_subtype = "html"

        tipos_dinamicos = ["F04", "F05"]
        for tipo in tipos_dinamicos:
            for formulario in formularios_por_tipo.get(tipo, []):
                buffer, filename = DocumentService.generar_documento_dinamico(formulario)
                if buffer:
                    email.attach(
                        filename,
                        buffer.read(),
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    )
                else:
                    logger.warning(f"No se pudo generar documento para {tipo} al enviar primera notificación CA {ca.pk}")

        try:
            email.send()
            from django.utils import timezone as tz
            ca.fecha_ultima_notificacion = tz.now()
            ca.cantidad_notificaciones += 1
            ca.save(update_fields=["fecha_ultima_notificacion", "cantidad_notificaciones"])
            logger.info(f"Primera notificación CA enviada a {docente} para CA {ca.pk}")
            return True, f"Correo enviado exitosamente a {correo_principal.email}"
        except Exception as e:
            logger.error(f"Error enviando primera notificación CA {ca.pk}: {e}")
            return False, f"Error al enviar: {str(e)}"

    @staticmethod
    def enviar_recordatorio_formularios_pendientes(
        ca: CarreraAcademica,
    ) -> tuple[bool, str]:
        """
        Envía recordatorio de formularios pendientes al docente.
        Solo incluye formularios de años anteriores o del año actual.

        Args:
            ca: Instancia de CarreraAcademica

        Returns:
            tuple: (exito, mensaje)
        """
        from django.utils import timezone

        docente = ca.cargo.docente
        correo_principal = docente.correos.filter(principal=True).first()

        if not correo_principal:
            return False, f"El docente {docente} no tiene correo principal"

        # ✅ FILTRO: Solo formularios hasta el año actual
        anio_actual = timezone.now().year
        tipos_a_notificar = ["F02", "F04", "F05"]

        formularios_pendientes = Formulario.objects.filter(
            carrera_academica=ca,
            estado="PEN",
            tipo_formulario__in=tipos_a_notificar
        ).filter(
            # Sin año (formularios únicos como F02) O año <= actual
            Q(anio_correspondiente__isnull=True) | Q(
                anio_correspondiente__lte=anio_actual)
        )

        if not formularios_pendientes.exists():
            return False, "No hay formularios pendientes para notificar"

        try:
            email = EmailService._preparar_email_recordatorio(
                ca, correo_principal.email, formularios_pendientes
            )
            email.send()

            from django.utils import timezone as tz
            ca.fecha_ultima_notificacion = tz.now()
            ca.cantidad_notificaciones += 1
            ca.save(update_fields=["fecha_ultima_notificacion", "cantidad_notificaciones"])

            logger.info(f"Recordatorio enviado a {docente} para CA {ca.pk}")
            return True, f"Correo enviado exitosamente a {correo_principal.email}"

        except Exception as e:
            logger.error(f"Error enviando recordatorio para CA {ca.pk}: {e}")
            return False, f"Error al enviar: {str(e)}"

    @staticmethod
    def obtener_documentos_pertinentes(
        ca: CarreraAcademica, anios_evaluados: List[int]
    ) -> List[Formulario]:
        """Obtiene documentos pertinentes para una evaluación."""
        # Formularios generales
        docs_generales = (
            ca.formularios.filter(estado="ENT", anio_correspondiente__isnull=True)
            .exclude(archivo__isnull=True)
            .exclude(archivo="")
        )

        # Formularios anuales de los años evaluados
        docs_anuales = (
            ca.formularios.filter(
                estado="ENT", anio_correspondiente__in=anios_evaluados
            )
            .exclude(archivo__isnull=True)
            .exclude(archivo="")
        )

        return list(docs_generales) + list(docs_anuales)

    @staticmethod
    def obtener_email_miembro(miembro) -> Optional[str]:
        """Obtiene el email de un miembro (Docente interno, o externo/veedor)."""
        if isinstance(miembro, Docente):
            correo = miembro.correos.filter(principal=True).first()
            return correo.email if correo else None
        else:
            # JuradoExterno, VeedorGraduado o VeedorEstudiante
            return miembro.email

    @staticmethod
    def _preparar_email_recordatorio(
        ca: CarreraAcademica, destinatario: str, formularios_pendientes
    ) -> EmailMessage:
        """Prepara el email de recordatorio de formularios pendientes."""
        from carrera_academica.services.document_service import DocumentService
        from collections import defaultdict

        info_cargo = (
            f"{ca.cargo.get_categoria_display()} {ca.cargo.get_caracter_display()} "
            f"en la asignatura {ca.cargo.asignatura.nombre.title()}"
        )

        email_body_lines = [
            "Estimado/a Docente,",
            f"\nLe recordamos que tiene documentación pendiente para su expediente de Carrera Académica "
            f"correspondiente a su cargo de {info_cargo}.",
            "\nA continuación, se detallan los formularios pendientes de entrega:",
            "",
        ]

        email = EmailMessage(
            subject="Recordatorio de Documentación Pendiente - Carrera Académica",
            from_email=None,
            to=[destinatario],
        )

        # ✅ AGRUPAR FORMULARIOS POR TIPO
        formularios_por_tipo = defaultdict(list)
        for f in formularios_pendientes:
            formularios_por_tipo[f.tipo_formulario].append(f)

        # ✅ PROCESAR POR TIPO
        tipos_dinamicos = ["F06", "F07", "F13", "ENC", "F04", "F05"]

        for tipo, formularios_grupo in sorted(formularios_por_tipo.items()):
            # Obtener años si aplica
            anios = [
                f.anio_correspondiente for f in formularios_grupo if f.anio_correspondiente]
            anios_texto = "-".join(str(a) for a in sorted(anios)) if anios else ""

            # Nombre descriptivo
            if tipo == 'F02':
                nombre_display = "Planificación de Cátedra"
            elif tipo == 'F04':
                nombre_display = f"Plan Anual de Actividades años {anios_texto}" if anios_texto else "Plan Anual de Actividades"
            elif tipo == 'F05':
                nombre_display = f"Informe Anual de Actividades años {anios_texto}" if anios_texto else "Informe Anual de Actividades"
            else:
                nombre_display = formularios_grupo[0].get_tipo_formulario_display()

            # Adjuntar documentos
            adjuntos_ok = 0
            for formulario in formularios_grupo:
                if tipo in tipos_dinamicos:
                    buffer, filename = DocumentService.generar_documento_dinamico(
                        formulario)

                    if buffer:
                        email.attach(
                            filename,
                            buffer.read(),
                            'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
                        )
                        adjuntos_ok += 1
                    else:
                        logger.warning(f"No se pudo generar documento para {tipo}")
                else:
                    # Para formularios estáticos
                    from carrera_academica.models import PlantillaDocumento

                    plantilla = PlantillaDocumento.objects.filter(
                        tipo_formulario=tipo).first()

                    if plantilla and plantilla.archivo:
                        email.attach_file(plantilla.archivo.path)
                        adjuntos_ok += 1
                    else:
                        logger.warning(f"No se encontró plantilla para {tipo}")

            # Agregar línea al cuerpo
            if adjuntos_ok > 0:
                email_body_lines.append(f"  • {tipo} - {nombre_display} (adjunto)")
            else:
                email_body_lines.append(
                    f"  • {tipo} - {nombre_display} (sin plantilla disponible)")

        email_body_lines.extend([
            "\nPor favor, complete los formularios y envíelos por correo adjuntando los archivos.",
            "\nSaludos cordiales,",
            "Departamento de Ingeniería Civil",
            "UTN - Facultad Regional La Plata"
        ])

        email.body = "\n".join(email_body_lines)

        return email
