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
import json

from planta_docente.forms import PlanificacionUploadForm, NotificacionForm
from planta_docente.models import Asignatura, PlanificacionAnual, Cargo
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

        cargos_activos = Cargo.objects.filter(
            asignatura=asignatura,
            estado='activo'
        ).select_related('docente')

        # Serializar cargos a JSON
        cargos_json = json.dumps([{
            'id': cargo.id,
            'docente': cargo.docente.get_full_name(),
            'categoria': cargo.get_categoria_display(),
            'es_responsable': cargo.es_responsable_planificacion
        } for cargo in cargos_activos])

        faltantes_data.append({
            'asignatura': asignatura,
            'planificacion': planificacion,
            'responsable_cargo': responsable_cargo,
            'responsable_nombre': responsable_cargo.docente.get_full_name() if responsable_cargo else 'Sin responsable',
            'responsable_email': responsable_cargo.docente.email if responsable_cargo else None,
            'cargos_json': cargos_json,  # ✅ NUEVO
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
        
        # Obtener archivos adicionales
        archivos_adicionales = request.FILES.getlist('archivos_adicionales')
        
        # Validar tamaño de archivos
        max_size = 10 * 1024 * 1024  # 10MB por archivo
        max_total = 25 * 1024 * 1024  # 25MB total
        total_size = sum(f.size for f in archivos_adicionales)

        if any(f.size > max_size for f in archivos_adicionales):
            messages.error(
                request, 'Uno o más archivos superan el tamaño máximo de 10 MB.')
            return redirect('planta_docente:notificar_planificacion_individual', pk=pk)

        if total_size > max_total:
            messages.error(
                request, 'El tamaño total de los archivos supera el límite de 25 MB.')
            return redirect('planta_docente:notificar_planificacion_individual', pk=pk)

        if tipo_mensaje == 'generico':
            exito, mensaje = PlanificacionEmailService.enviar_solicitud_generica(
                planificacion,
                adjuntar_ficha=adjuntar_ficha,
                archivos_adicionales=archivos_adicionales,
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
                archivos_adicionales=archivos_adicionales,
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
    cuerpo_personalizado = request.POST.get(
        'cuerpo_personalizado', '') if tipo_mensaje == 'personalizado' else None

    archivos_adicionales = request.FILES.getlist('archivos_adicionales')

    if archivos_adicionales:
        max_size = 10 * 1024 * 1024
        max_total = 25 * 1024 * 1024
        total_size = sum(f.size for f in archivos_adicionales)

        if any(f.size > max_size for f in archivos_adicionales):
            messages.error(
                request, 'Uno o más archivos superan el tamaño máximo de 10 MB.')
            return redirect('planta_docente:dashboard_planificaciones')

        if total_size > max_total:
            messages.error(
                request, 'El tamaño total de los archivos supera el límite de 25 MB.')
            return redirect('planta_docente:dashboard_planificaciones')

    if tipo_mensaje == 'personalizado' and not cuerpo_personalizado:
        messages.error(request, 'Debe escribir un mensaje personalizado.')
        return redirect('planta_docente:dashboard_planificaciones')

    faltantes = obtener_planificaciones_faltantes(año)

    resultados = {
        'exitosos': 0,
        'fallidos': 0,
        'sin_responsable': 0,
        'errores': []
    }

    for asignatura in faltantes:
        responsable_cargo = obtener_responsable_planificacion(asignatura)

        if not responsable_cargo:
            resultados['sin_responsable'] += 1
            resultados['errores'].append(
                f"{asignatura.nombre}: Sin responsable con email")
            continue

        planificacion, created = PlanificacionAnual.objects.get_or_create(
            asignatura=asignatura,
            año=año,
            defaults={
                'estado': 'pendiente',
                'docente_responsable': responsable_cargo.docente
            }
        )

        # Enviar notificación (sin validar si ya fue enviada)
        if tipo_mensaje == 'generico':
            exito, mensaje = PlanificacionEmailService.enviar_solicitud_generica(
                planificacion,
                adjuntar_ficha=adjuntar_ficha,
                archivos_adicionales=archivos_adicionales,
                usuario=request.user
            )
        else:
            exito, mensaje = PlanificacionEmailService.enviar_solicitud_personalizada(
                planificacion,
                cuerpo_personalizado,
                adjuntar_ficha=adjuntar_ficha,
                archivos_adicionales=archivos_adicionales,
                usuario=request.user
            )

        if exito:
            resultados['exitosos'] += 1
        else:
            resultados['fallidos'] += 1
            resultados['errores'].append(f"{asignatura.nombre}: {mensaje}")

    total_procesadas = resultados['exitosos'] + \
        resultados['fallidos'] + resultados['sin_responsable']

    if resultados['exitosos'] > 0:
        messages.success(
            request,
            f'✅ {resultados["exitosos"]} notificaciones enviadas exitosamente'
        )

    if resultados['sin_responsable'] > 0:
        messages.warning(
            request,
            f'⚠️ {resultados["sin_responsable"]} asignaturas sin responsable con email'
        )

    if resultados['fallidos'] > 0:
        messages.error(
            request,
            f'❌ {resultados["fallidos"]} fallos al enviar'
        )
        for error in resultados['errores'][:3]:
            messages.error(request, error)

    if total_procesadas == 0:
        messages.info(request, 'No hay asignaturas pendientes de notificar')

    return redirect('planta_docente:dashboard_planificaciones')


@login_required
@staff_member_required
def crear_y_notificar(request):
    """
    Crea el registro de planificación y redirige a la vista de notificación.
    """
    if request.method != 'POST':
        return redirect('planta_docente:dashboard_planificaciones')

    asignatura_id = request.POST.get('asignatura_id')
    año = request.POST.get('año', timezone.now().year)

    try:
        año = int(año)
    except (ValueError, TypeError):
        año = timezone.now().year

    asignatura = get_object_or_404(Asignatura, pk=asignatura_id)
    responsable_cargo = obtener_responsable_planificacion(asignatura)

    # Crear registro
    planificacion, created = PlanificacionAnual.objects.get_or_create(
        asignatura=asignatura,
        año=año,
        defaults={
            'estado': 'pendiente',
            'docente_responsable': responsable_cargo.docente if responsable_cargo else None
        }
    )

    # Redirigir a notificar
    return redirect('planta_docente:notificar_planificacion_individual', pk=planificacion.id)


@login_required
@staff_member_required
def gestionar_asignaturas_año(request):
    """
    Vista para habilitar/deshabilitar asignaturas por año.
    """
    año_actual = timezone.now().year
    año_seleccionado = request.GET.get('año', año_actual)

    try:
        año_seleccionado = int(año_seleccionado)
    except (ValueError, TypeError):
        año_seleccionado = año_actual

    # Todas las asignaturas con su estado para el año
    from planta_docente.models import Asignatura, AsignaturaAnual

    asignaturas = Asignatura.objects.all().order_by('nivel', 'nombre')

    asignaturas_data = []
    for asig in asignaturas:
        try:
            config = AsignaturaAnual.objects.get(
                asignatura=asig,
                año=año_seleccionado
            )
        except AsignaturaAnual.DoesNotExist:
            # Por defecto activa
            config = None

        asignaturas_data.append({
            'asignatura': asig,
            'config': config,
            'activa': config.activa if config else True,
            'motivo': config.motivo_deshabilitacion if config else '',
        })

    # Paginación
    from django.core.paginator import Paginator
    paginator = Paginator(asignaturas_data, 30)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Años disponibles
    años_disponibles = range(año_actual - 1, año_actual + 4)

    context = {
        'año_seleccionado': año_seleccionado,
        'años_disponibles': años_disponibles,
        'page_obj': page_obj,
    }

    return render(request, 'planta_docente/planificaciones/gestionar_asignaturas.html', context)


@login_required
@staff_member_required
def toggle_asignatura_año(request):
    """
    AJAX: Habilita/deshabilita una asignatura para un año específico.
    """
    from planta_docente.models import Asignatura, AsignaturaAnual

    asignatura_id = request.POST.get('asignatura_id')
    año = request.POST.get('año')
    activa = request.POST.get('activa') == 'true'
    motivo = request.POST.get('motivo', '')

    try:
        año = int(año)
        asignatura = Asignatura.objects.get(pk=asignatura_id)

        # Crear o actualizar configuración
        config, created = AsignaturaAnual.objects.update_or_create(
            asignatura=asignatura,
            año=año,
            defaults={
                'activa': activa,
                'motivo_deshabilitacion': motivo if not activa else '',
                'modificado_por': request.user
            }
        )

        return JsonResponse({
            'success': True,
            'activa': config.activa,
            'mensaje': f"{'Habilitada' if activa else 'Deshabilitada'} para {año}"
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


# En planta_docente/views/planificaciones.py

@login_required
def cambiar_responsable_planificacion(request):
    """Cambia el responsable de planificación de una asignatura."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)

    asignatura_id = request.POST.get('asignatura_id')
    cargo_id = request.POST.get('cargo_id')

    try:
        asignatura = Asignatura.objects.get(id=asignatura_id)

        # Desmarcar todos los cargos de esta asignatura
        Cargo.objects.filter(
            asignatura=asignatura,
            es_responsable_planificacion=True
        ).update(es_responsable_planificacion=False)

        # Marcar el nuevo responsable
        if cargo_id:
            cargo = Cargo.objects.get(id=cargo_id, asignatura=asignatura)
            cargo.es_responsable_planificacion = True
            cargo.save()

            return JsonResponse({
                'success': True,
                'responsable': f"{cargo.docente.get_full_name()} ({cargo.get_categoria_display()})"
            })

        return JsonResponse({'success': True, 'responsable': 'Sin responsable'})

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
