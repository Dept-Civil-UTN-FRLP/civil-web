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
    def enviar_solicitud_generica(planificacion, adjuntar_ficha=False, archivos_adicionales=None, usuario=None):
        """
        Envía email genérico solicitando planificación.

        Args:
            planificacion (PlanificacionAnual): Planificación a notificar
            adjuntar_ficha (bool): Si adjuntar ficha de asignatura
            archivos_adicionales (list): Lista de archivos UploadedFile
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
                    nombre_limpio = planificacion.asignatura.nombre.replace(
                        ' ', '_').replace('/', '-')
                    filename = f'Ficha_{nombre_limpio}.pdf'
                    email.attach(filename, pdf_ficha, 'application/pdf')
                    archivos_adjuntos.append(filename)
            except Exception as e:
                pass

        # ✅ NUEVO: Adjuntar archivos adicionales
        if archivos_adicionales:
            for archivo in archivos_adicionales:
                try:
                    # Leer contenido del archivo
                    contenido = archivo.read()

                    # Adjuntar al email
                    email.attach(archivo.name, contenido, archivo.content_type)
                    archivos_adjuntos.append(archivo.name)

                    print(
                        f"✅ Archivo adicional adjunto: {archivo.name} ({archivo.size} bytes)")
                except Exception as e:
                    print(f"⚠️ Error adjuntando {archivo.name}: {str(e)}")
                    # Continuar con otros archivos

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
                                       adjuntar_ficha=False, archivos_adicionales=None, usuario=None):
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
            
        # Adjuntar archivos adicionales
        if archivos_adicionales:
            for archivo in archivos_adicionales:
                try:
                    # Leer contenido del archivo
                    contenido = archivo.read()

                    # Adjuntar al email
                    email.attach(archivo.name, contenido, archivo.content_type)
                    archivos_adjuntos.append(archivo.name)

                    print(
                        f"✅ Archivo adicional adjunto: {archivo.name} ({archivo.size} bytes)")
                except Exception as e:
                    print(f"⚠️ Error adjuntando {archivo.name}: {str(e)}")
                    # Continuar con otros archivos

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
            from django.template.loader import render_to_string
            from weasyprint import HTML
            from planta_docente.models import Cargo
            from django.utils import timezone

            # Obtener cargos asociados
            cargos = Cargo.objects.filter(
                asignatura=asignatura,
                estado='activo'
            ).select_related('docente').order_by('categoria', 'docente__apellido')

            # Separar profesores y auxiliares
            profesores = []
            auxiliares = []

            TIPOS_PROFESORES = ['tit', 'aso', 'adj']
            TIPOS_AUXILIARES = ['jtp', 'atp1', 'atp2', 'ads']

            for cargo in cargos:
                tipo_nombre = cargo.categoria
                if any(tipo in tipo_nombre for tipo in TIPOS_PROFESORES):
                    profesores.append(cargo)
                elif any(tipo in tipo_nombre for tipo in TIPOS_AUXILIARES):
                    auxiliares.append(cargo)

            # Obtener áreas y bloques
            areas = asignatura.area.all()
            bloques = asignatura.bloque.all()

            # Parsear objetivos
            objetivos_lista = []
            if asignatura.objetivos:
                objetivos_lista = [
                    obj.strip().lstrip('•').lstrip('-').strip()
                    for obj in asignatura.objetivos.split('\n')
                    if obj.strip()
                ]

            # Parsear competencias
            competencias_lista = []
            if asignatura.competencias:
                competencias_lista = [
                    comp.strip()
                    for comp in asignatura.competencias.split('-')
                    if comp.strip()
                ]

            # Parsear contenidos
            contenidos_lista = []
            if asignatura.contenidos_minimos:
                contenidos_lista = [
                    obj.strip().lstrip('•').lstrip('-').strip()
                    for obj in asignatura.contenidos_minimos.split('\n')
                    if obj.strip()
                ]

            # Contexto para el template
            context = {
                'asignatura': asignatura,
                'año': timezone.now().year,
                'areas': areas,
                'bloques': bloques,
                'objetivos_lista': objetivos_lista,
                'competencias_lista': competencias_lista,
                'contenidos_lista': contenidos_lista,
                'profesores': profesores,
                'auxiliares': auxiliares,
            }

            # Renderizar template
            html_string = render_to_string(
                'planta_docente/asignatura/ver_ficha_pdf.html',
                context
            )

            # Generar PDF
            pdf = HTML(string=html_string).write_pdf()

            return pdf

        except Exception as e:
            # Log del error (opcional)
            print(f"Error generando PDF de ficha: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
