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
    JuntaEvaluadora,
    MiembroExterno,
)
from planta_docente.models import Docente

logger = logging.getLogger(__name__)


class EmailService:
    """Servicio centralizado para envío de emails de Carrera Académica."""

    @staticmethod
    def enviar_notificacion_junta(evaluacion: Evaluacion) -> tuple[int, List[str]]:
        """
        Envía notificación a todos los miembros activos de la junta evaluadora.

        Args:
            evaluacion: Instancia de Evaluacion

        Returns:
            tuple: (cantidad_enviados, lista_errores)
        """
        junta = getattr(evaluacion.carrera_academica, "junta_evaluadora", None)

        if not junta:
            logger.error(f"Evaluación {evaluacion.pk} no tiene junta asignada")
            return 0, ["No hay junta evaluadora asignada"]

        miembros = EmailService._obtener_miembros_activos(junta)

        if not miembros:
            logger.warning(
                f"No hay miembros activos en junta de evaluación {evaluacion.pk}"
            )
            return 0, ["No hay miembros activos en la junta"]

        documentos = EmailService._obtener_documentos_pertinentes(
            evaluacion.carrera_academica, evaluacion.anios_evaluados
        )

        if not documentos:
            logger.warning(
                f"No hay documentos para enviar en evaluación {evaluacion.pk}"
            )
            return 0, ["No hay documentos entregados para enviar"]

        emails_enviados = 0
        errores = []

        for miembro in miembros:
            try:
                email_destinatario = EmailService._obtener_email_miembro(miembro)

                if email_destinatario:
                    EmailService._enviar_email_individual(
                        destinatario=email_destinatario,
                        evaluacion=evaluacion,
                        documentos=documentos,
                    )
                    emails_enviados += 1
                else:
                    errores.append(f"No se encontró email para {miembro}")

            except Exception as e:
                logger.error(f"Error enviando email a {miembro}: {e}")
                errores.append(f"Error con {miembro}: {str(e)}")

        return emails_enviados, errores

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

            logger.info(f"Recordatorio enviado a {docente} para CA {ca.pk}")
            return True, f"Correo enviado exitosamente a {correo_principal.email}"

        except Exception as e:
            logger.error(f"Error enviando recordatorio para CA {ca.pk}: {e}")
            return False, f"Error al enviar: {str(e)}"

    @staticmethod
    def _obtener_miembros_activos(junta: JuntaEvaluadora) -> List:
        """Obtiene lista de miembros activos de la junta."""
        miembros = []

        # Miembro interno
        if junta.asistencia_status.get("miembro_interno_titular") == "ausente":
            if junta.miembro_interno_suplente:
                miembros.append(junta.miembro_interno_suplente)
        else:
            if junta.miembro_interno_titular:
                miembros.append(junta.miembro_interno_titular)

        # Miembros externos titulares
        miembros.extend(junta.miembros_externos_titulares.all())

        # Veedores titulares
        if junta.veedor_alumno_titular:
            miembros.append(junta.veedor_alumno_titular)
        if junta.veedor_graduado_titular:
            miembros.append(junta.veedor_graduado_titular)

        return miembros

    @staticmethod
    def _obtener_documentos_pertinentes(
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
    def _obtener_email_miembro(miembro) -> Optional[str]:
        """Obtiene el email de un miembro de la junta."""
        if isinstance(miembro, Docente):
            correo = miembro.correos.filter(principal=True).first()
            return correo.email if correo else None
        else:
            # MiembroExterno o Veedor
            return miembro.email

    @staticmethod
    def _enviar_email_individual(
        destinatario: str, evaluacion: Evaluacion, documentos: List[Formulario]
    ):
        """Envía email individual a un miembro de la junta."""
        ca = evaluacion.carrera_academica

        fecha_texto = (
            evaluacion.fecha_evaluacion.strftime("%d/%m/%Y a las %H:%Mhs")
            if evaluacion.fecha_evaluacion
            else "a confirmar"
        )

        email = EmailMessage(
            subject=f"Convocatoria y Documentación para Junta Evaluadora - {ca.cargo.docente}",
            body=f"""Estimado/a Miembro de la Junta Evaluadora,

Se le convoca a participar en la evaluación para la Carrera Académica de {ca.cargo.docente}. 
La misma está agendada para el {fecha_texto}.

Se adjunta toda la documentación relevante del expediente para su análisis.

Saludos cordiales,
Departamento de Ingeniería Civil""",
            from_email=None,
            to=[destinatario],
        )

        for doc in documentos:
            if doc.archivo:
                email.attach_file(doc.archivo.path)

        email.send()

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
