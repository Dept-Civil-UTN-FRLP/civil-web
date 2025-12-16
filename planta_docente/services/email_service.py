"""
Servicio de envío de emails para planificaciones anuales.
"""
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone

from planta_docente.models import PlanificacionAnual, HistorialNotificacionPlanificacion
from planta_docente.utils import obtener_responsable_planificacion


class PlanificacionEmailService:
    """
    Servicio para enviar notificaciones de planificaciones por email.
    """

    @staticmethod
    def enviar_solicitud_generica(planificacion, adjuntar_ficha=False, usuario=None):
        """
        Envía email genérico solicitando planificación.
        
        Args:
            planificacion (PlanificacionAnual): Planificación a notificar
            adjuntar_ficha (bool): Si adjuntar ficha de asignatura
            usuario (User): Usuario que envía la notificación
        
        Returns:
            tuple: (bool exito, str mensaje)
        """
        responsable_cargo = obtener_responsable_planificacion(
            planificacion.asignatura)

        if not responsable_cargo:
            return False, "No se encontró docente responsable para esta asignatura"

        if not responsable_cargo.docente.email:
            return False, f"El docente {responsable_cargo.docente.get_full_name()} no tiene email configurado"

        # Contexto para el template
        contexto = {
            'docente': responsable_cargo.docente,
            'asignatura': planificacion.asignatura,
            'año': planificacion.año,
            'cargo': responsable_cargo,
        }

        # Renderizar HTML
        asunto = f"Solicitud de Planificación Anual {planificacion.año} - {planificacion.asignatura.nombre}"
        cuerpo_html = render_to_string(
            'planta_docente/emails/solicitud_planificacion_generica.html',
            contexto
        )

        # Crear email
        email = EmailMessage(
            subject=asunto,
            body=cuerpo_html,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[responsable_cargo.docente.email],
            reply_to=[settings.PLANTA_DOCENTE_EMAIL],
        )
        email.content_subtype = "html"

        # Adjuntar ficha si se solicita
        archivos_adjuntos = []
        if adjuntar_ficha:
            try:
                pdf_ficha = PlanificacionEmailService._generar_pdf_ficha(
                    planificacion.asignatura)
                if pdf_ficha:
                    filename = f'Ficha_{planificacion.asignatura.nombre.replace(" ", "_")}.pdf'
                    email.attach(filename, pdf_ficha, 'application/pdf')
                    archivos_adjuntos.append(filename)
            except Exception as e:
                # Continuar sin adjunto si falla
                pass

        # Intentar enviar
        try:
            email.send()
            exito = True
            error = ""
        except Exception as e:
            exito = False
            error = str(e)

        # Registrar en historial
        HistorialNotificacionPlanificacion.objects.create(
            planificacion=planificacion,
            destinatario=responsable_cargo.docente,
            email_destinatario=responsable_cargo.docente.email,
            asunto=asunto,
            cuerpo=cuerpo_html,
            tipo_mensaje='generico',
            archivos_adjuntos=archivos_adjuntos,
            ficha_adjunta=adjuntar_ficha,
            enviado_por=usuario,
            enviado_exitosamente=exito,
            error_envio=error
        )

        # Actualizar planificación
        if exito:
            planificacion.estado = 'enviada'
            planificacion.fecha_ultima_notificacion = timezone.now()
            planificacion.cantidad_notificaciones += 1
            if not planificacion.docente_responsable:
                planificacion.docente_responsable = responsable_cargo.docente
            planificacion.save()

            return True, "Email enviado exitosamente"
        else:
            return False, f"Error al enviar email: {error}"

    @staticmethod
    def enviar_solicitud_personalizada(planificacion, cuerpo_personalizado,
                                       adjuntar_ficha=False, usuario=None):
        """
        Envía email personalizado.
        
        Args:
            planificacion (PlanificacionAnual): Planificación a notificar
            cuerpo_personalizado (str): Texto personalizado del mensaje
            adjuntar_ficha (bool): Si adjuntar ficha de asignatura
            usuario (User): Usuario que envía la notificación
        
        Returns:
            tuple: (bool exito, str mensaje)
        """
        responsable_cargo = obtener_responsable_planificacion(
            planificacion.asignatura)

        if not responsable_cargo:
            return False, "No se encontró docente responsable para esta asignatura"

        if not responsable_cargo.docente.email:
            return False, f"El docente {responsable_cargo.docente.get_full_name()} no tiene email configurado"

        # Contexto para el template
        contexto = {
            'docente': responsable_cargo.docente,
            'asignatura': planificacion.asignatura,
            'año': planificacion.año,
            'cargo': responsable_cargo,
            'mensaje_personalizado': cuerpo_personalizado,
        }

        # Renderizar HTML
        asunto = f"Solicitud de Planificación Anual {planificacion.año} - {planificacion.asignatura.nombre}"
        cuerpo_html = render_to_string(
            'planta_docente/emails/solicitud_planificacion_personalizada.html',
            contexto
        )

        # Crear email
        email = EmailMessage(
            subject=asunto,
            body=cuerpo_html,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[responsable_cargo.docente.email],
            reply_to=[settings.PLANTA_DOCENTE_EMAIL],
        )
        email.content_subtype = "html"

        # Adjuntar ficha si se solicita
        archivos_adjuntos = []
        if adjuntar_ficha:
            try:
                pdf_ficha = PlanificacionEmailService._generar_pdf_ficha(
                    planificacion.asignatura)
                if pdf_ficha:
                    filename = f'Ficha_{planificacion.asignatura.nombre.replace(" ", "_")}.pdf'
                    email.attach(filename, pdf_ficha, 'application/pdf')
                    archivos_adjuntos.append(filename)
            except Exception as e:
                pass

        # Intentar enviar
        try:
            email.send()
            exito = True
            error = ""
        except Exception as e:
            exito = False
            error = str(e)

        # Registrar en historial
        HistorialNotificacionPlanificacion.objects.create(
            planificacion=planificacion,
            destinatario=responsable_cargo.docente,
            email_destinatario=responsable_cargo.docente.email,
            asunto=asunto,
            cuerpo=cuerpo_html,
            tipo_mensaje='personalizado',
            archivos_adjuntos=archivos_adjuntos,
            ficha_adjunta=adjuntar_ficha,
            enviado_por=usuario,
            enviado_exitosamente=exito,
            error_envio=error
        )

        # Actualizar planificación
        if exito:
            planificacion.estado = 'enviada'
            planificacion.fecha_ultima_notificacion = timezone.now()
            planificacion.cantidad_notificaciones += 1
            if not planificacion.docente_responsable:
                planificacion.docente_responsable = responsable_cargo.docente
            planificacion.save()

            return True, "Email enviado exitosamente"
        else:
            return False, f"Error al enviar email: {error}"

    @staticmethod
    def _generar_pdf_ficha(asignatura):
        """
        Genera PDF de la ficha de asignatura.
        
        Args:
            asignatura (Asignatura): Asignatura para generar ficha
        
        Returns:
            bytes: PDF generado o None si falla
        """
        try:
            from django.http import HttpRequest
            from planta_docente.views.estructura_catedra import ver_ficha_asignatura
            from weasyprint import HTML

            # Crear request fake
            request = HttpRequest()
            request.method = 'GET'

            # Renderizar template de ficha
            from django.template.loader import render_to_string

            # Obtener datos necesarios
            areas = asignatura.area.all()
            bloques = asignatura.bloque.all()

            objetivos_lista = []
            if asignatura.objetivos:
                objetivos_lista = [
                    obj.strip().lstrip('•').lstrip('-').strip()
                    for obj in asignatura.objetivos.split('\n')
                    if obj.strip()
                ]

            competencias_lista = []
            if asignatura.competencias:
                competencias_lista = [
                    comp.strip()
                    for comp in asignatura.competencias.split('-')
                    if comp.strip()
                ]

            contenidos_lista = []
            if asignatura.contenidos_minimos:
                contenidos_lista = [
                    obj.strip().lstrip('•').lstrip('-').strip()
                    for obj in asignatura.contenidos_minimos.split('\n')
                    if obj.strip()
                ]

            context = {
                'asignatura': asignatura,
                'areas': areas,
                'bloques': bloques,
                'objetivos_lista': objetivos_lista,
                'competencias_lista': competencias_lista,
                'contenidos_lista': contenidos_lista,
            }

            html_string = render_to_string(
                'planta_docente/asignatura/ver_ficha.html', context)
            pdf = HTML(string=html_string).write_pdf()

            return pdf
        except Exception as e:
            # Si falla, retornar None
            return None
