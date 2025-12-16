"""
Vistas para gestión de planificaciones anuales.
"""
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from planta_docente.forms import PlanificacionUploadForm, NotificacionForm
from planta_docente.models import Asignatura, PlanificacionAnual
from planta_docente.utils import (
    obtener_estadisticas_planificaciones,
    obtener_planificaciones_faltantes,
    obtener_responsable_planificacion,
)
from planta_docente.services.email_service import PlanificacionEmailService

@login_required
@staff_member_required
def dashboard_planificaciones(request):
    """
    Dashboard principal de planificaciones anuales.
    Muestra estadísticas y lista de asignaturas pendientes.
    """
    # Año seleccionado (por defecto el actual)
    año_actual = timezone.now().year
    año_seleccionado = request.GET.get('año', año_actual)

    try:
        año_seleccionado = int(año_seleccionado)
    except (ValueError, TypeError):
        año_seleccionado = año_actual

    # Obtener estadísticas
    stats = obtener_estadisticas_planificaciones(año_seleccionado)

    # Obtener asignaturas faltantes
    faltantes_queryset = obtener_planificaciones_faltantes(año_seleccionado)

    faltantes_data = []
    for asignatura in faltantes_queryset:
        responsable_cargo = obtener_responsable_planificacion(asignatura)

        try:
            planificacion = PlanificacionAnual.objects.get(
                asignatura=asignatura,
                año=año_seleccionado
            )
        except PlanificacionAnual.DoesNotExist:
            # Si no existe, crear objeto temporal sin guardar
            planificacion = PlanificacionAnual(
                asignatura=asignatura,
                año=año_seleccionado,
                estado='pendiente',
                docente_responsable=responsable_cargo.docente if responsable_cargo else None
            )

        faltantes_data.append({
            'asignatura': asignatura,
            'planificacion': planificacion,
            'responsable_cargo': responsable_cargo,
            'responsable_nombre': responsable_cargo.docente.get_full_name() if responsable_cargo else 'Sin responsable',
            'responsable_email': responsable_cargo.docente.email if responsable_cargo else None,
        })

    # Paginación
    paginator = Paginator(faltantes_data, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Lista de años disponibles (5 años: anterior, actual, 3 próximos)
    años_disponibles = range(año_actual - 1, año_actual + 4)

    # Obtener planificaciones recibidas recientes
    recientes = PlanificacionAnual.objects.filter(
        año=año_seleccionado,
        estado__in=['recibida', 'aprobada']
    ).select_related('asignatura', 'docente_responsable').order_by('-fecha_subida')[:5]

    context = {
        'año_seleccionado': año_seleccionado,
        'años_disponibles': años_disponibles,
        'stats': stats,
        'page_obj': page_obj,
        'recientes': recientes,
    }

    return render(request, 'planta_docente/planificaciones/dashboard.html', context)


@login_required
@staff_member_required
def subir_planificacion(request, asignatura_id):
    """
    Vista para subir una planificación manualmente.
    """
    asignatura = get_object_or_404(Asignatura, pk=asignatura_id)

    # Año por defecto
    año_default = timezone.now().year
    año = request.GET.get('año', año_default)

    try:
        año = int(año)
    except (ValueError, TypeError):
        año = año_default

    # Obtener o crear planificación
    planificacion, created = PlanificacionAnual.objects.get_or_create(
        asignatura=asignatura,
        año=año,
        defaults={
            'estado': 'pendiente',
            'docente_responsable': obtener_responsable_planificacion(asignatura).docente
            if obtener_responsable_planificacion(asignatura) else None
        }
    )

    if request.method == 'POST':
        form = PlanificacionUploadForm(
            request.POST, request.FILES, instance=planificacion)

        if form.is_valid():
            planificacion = form.save(commit=False)
            planificacion.subido_por = request.user
            planificacion.estado = 'recibida'
            planificacion.save()

            messages.success(
                request,
                f'✓ Planificación de "{asignatura.nombre}" subida correctamente.'
            )
            return redirect('planta_docente:dashboard_planificaciones')
        else:
            messages.error(
                request, 'Por favor corrige los errores del formulario.')
    else:
        form = PlanificacionUploadForm(instance=planificacion)

    context = {
        'form': form,
        'asignatura': asignatura,
        'año': año,
        'planificacion': planificacion,
    }

    return render(request, 'planta_docente/planificaciones/subir.html', context)


@login_required
def descargar_planificacion(request, pk):
    """
    Descarga el archivo de una planificación.
    """
    planificacion = get_object_or_404(PlanificacionAnual, pk=pk)

    if not planificacion.archivo:
        raise Http404("No hay archivo disponible")

    # Servir archivo
    response = FileResponse(
        planificacion.archivo.open('rb'),
        as_attachment=True,
        filename=planificacion.archivo_nombre_original or planificacion.archivo.name
    )

    return response


@login_required
@staff_member_required
def eliminar_planificacion(request, pk):
    """
    Elimina una planificación (soft delete - solo borra el archivo).
    """
    planificacion = get_object_or_404(PlanificacionAnual, pk=pk)

    if request.method == 'POST':
        # Eliminar archivo pero mantener registro
        if planificacion.archivo:
            planificacion.archivo.delete()

        planificacion.estado = 'pendiente'
        planificacion.observaciones += f"\n[{timezone.now().strftime('%d/%m/%Y %H:%M')}] Archivo eliminado por {request.user.username}"
        planificacion.save()

        messages.success(
            request,
            f'✓ Planificación de "{planificacion.asignatura.nombre}" eliminada.'
        )

    return redirect('planta_docente:dashboard_planificaciones')


@login_required
@staff_member_required
def vista_previa_notificacion(request, pk):
    """
    Vista previa del email que se enviará (AJAX).
    """
    planificacion = get_object_or_404(PlanificacionAnual, pk=pk)
    responsable_cargo = obtener_responsable_planificacion(
        planificacion.asignatura)

    if not responsable_cargo:
        return JsonResponse({
            'error': 'No se encontró docente responsable para esta asignatura'
        }, status=400)

    # Renderizar template de email
    from django.template.loader import render_to_string

    contexto = {
        'docente': responsable_cargo.docente,
        'asignatura': planificacion.asignatura,
        'año': planificacion.año,
        'cargo': responsable_cargo,
    }

    html_preview = render_to_string(
        'planta_docente/emails/solicitud_planificacion_generica.html',
        contexto
    )

    return JsonResponse({
        'html': html_preview,
        'destinatario': responsable_cargo.docente.email,
        'nombre': responsable_cargo.docente.get_full_name(),
    })


@login_required
@staff_member_required
def notificar_planificacion_individual(request, pk):
    """
    Envía notificación para una planificación específica.
    """
    planificacion = get_object_or_404(PlanificacionAnual, pk=pk)

    if request.method == 'POST':
        tipo_mensaje = request.POST.get('tipo_mensaje', 'generico')
        adjuntar_ficha = request.POST.get('adjuntar_ficha') == 'on'

        if tipo_mensaje == 'generico':
            exito, mensaje = PlanificacionEmailService.enviar_solicitud_generica(
                planificacion,
                adjuntar_ficha=adjuntar_ficha,
                usuario=request.user
            )
        else:
            cuerpo_personalizado = request.POST.get('cuerpo_personalizado', '')
            if not cuerpo_personalizado:
                messages.error(
                    request, 'Debe escribir un mensaje personalizado.')
                return redirect('planta_docente:dashboard_planificaciones')

            exito, mensaje = PlanificacionEmailService.enviar_solicitud_personalizada(
                planificacion,
                cuerpo_personalizado,
                adjuntar_ficha=adjuntar_ficha,
                usuario=request.user
            )

        if exito:
            messages.success(request, f'✉️ {mensaje}')
        else:
            messages.error(request, f'❌ {mensaje}')

        return redirect('planta_docente:dashboard_planificaciones')

    # GET: Mostrar formulario
    responsable_cargo = obtener_responsable_planificacion(
        planificacion.asignatura)

    context = {
        'planificacion': planificacion,
        'responsable_cargo': responsable_cargo,
    }

    return render(request, 'planta_docente/planificaciones/notificar.html', context)


@login_required
@staff_member_required
def notificar_masivo(request):
    """
    Envía notificaciones masivas a todas las asignaturas pendientes.
    """
    if request.method != 'POST':
        return redirect('planta_docente:dashboard_planificaciones')

    año = request.POST.get('año', timezone.now().year)
    try:
        año = int(año)
    except (ValueError, TypeError):
        año = timezone.now().year

    tipo_mensaje = request.POST.get('tipo_mensaje', 'generico')
    adjuntar_ficha = request.POST.get('adjuntar_ficha') == 'on'

    # Obtener asignaturas pendientes
    faltantes = obtener_planificaciones_faltantes(año)

    resultados = {
        'exitosos': 0,
        'fallidos': 0,
        'errores': []
    }

    for asignatura in faltantes:
        responsable_cargo = obtener_responsable_planificacion(asignatura)

        if not responsable_cargo:
            resultados['fallidos'] += 1
            resultados['errores'].append(
                f"{asignatura.nombre}: Sin responsable")
            continue

        # Crear o recuperar PlanificacionAnual
        planificacion, created = PlanificacionAnual.objects.get_or_create(
            asignatura=asignatura,
            año=año,
            defaults={
                'estado': 'pendiente',
                'docente_responsable': responsable_cargo.docente
            }
        )

        # Enviar notificación
        if tipo_mensaje == 'generico':
            exito, mensaje = PlanificacionEmailService.enviar_solicitud_generica(
                planificacion,
                adjuntar_ficha=adjuntar_ficha,
                usuario=request.user
            )
        else:
            cuerpo_personalizado = request.POST.get('cuerpo_personalizado', '')
            exito, mensaje = PlanificacionEmailService.enviar_solicitud_personalizada(
                planificacion,
                cuerpo_personalizado,
                adjuntar_ficha=adjuntar_ficha,
                usuario=request.user
            )

        if exito:
            resultados['exitosos'] += 1
        else:
            resultados['fallidos'] += 1
            resultados['errores'].append(f"{asignatura.nombre}: {mensaje}")

    # Mensaje de resultado
    if resultados['exitosos'] > 0:
        messages.success(
            request,
            f'✅ Notificaciones enviadas: {resultados["exitosos"]} exitosas'
        )

    if resultados['fallidos'] > 0:
        messages.warning(
            request,
            f'⚠️ Fallos: {resultados["fallidos"]} (ver detalles en consola)'
        )
        for error in resultados['errores'][:5]:  # Mostrar solo primeros 5
            messages.error(request, error)

    return redirect('planta_docente:dashboard_planificaciones')
