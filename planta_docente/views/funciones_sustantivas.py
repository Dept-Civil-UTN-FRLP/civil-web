from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.utils import timezone

from planta_docente.models import Cargo, ActividadSustantiva, Asignatura, Resolucion


@login_required
def gestionar_funciones_sustantivas(request, cargo_pk):
    """
    Vista para gestionar las funciones sustantivas de un cargo.
    """
    cargo = get_object_or_404(
        Cargo.objects.select_related('docente', 'asignatura'),
        pk=cargo_pk
    )

    # Verificar si requiere funciones sustantivas
    requiere, razon = cargo.requiere_funciones_sustantivas()

    # Obtener funciones actuales
    funciones = cargo.actividades_sustantivas.select_related(
        'asignatura_vinculada',
        'resolucion_cd'
    ).order_by('-activa', 'categoria', 'fecha_inicio')

    # Resumen por categoría
    resumen = cargo.resumen_funciones_sustantivas()

    # Totales de horas
    horas_totales = cargo.get_horas_funciones_sustantivas()

    # Verificar completitud
    completo, mensaje_completo = cargo.tiene_funciones_sustantivas_completas()

    context = {
        'cargo': cargo,
        'requiere': requiere,
        'razon': razon,
        'funciones': funciones,
        'resumen': resumen,
        'horas_totales': horas_totales,
        'completo': completo,
        'mensaje_completo': mensaje_completo,
    }

    return render(request, 'planta_docente/funciones_sustantivas/gestionar.html', context)


@login_required
def crear_funcion_sustantiva(request, cargo_pk):
    """
    Vista para crear una nueva función sustantiva.
    """
    cargo = get_object_or_404(Cargo, pk=cargo_pk)

    if request.method == 'POST':
        try:
            # Extraer datos del formulario
            tipo_actividad = request.POST.get('tipo_actividad')
            descripcion = request.POST.get('descripcion')
            horas_semanales = request.POST.get('horas_semanales')
            codigo_proyecto = request.POST.get('codigo_proyecto', '')
            nombre_proyecto = request.POST.get('nombre_proyecto', '')
            asignatura_vinculada_id = request.POST.get('asignatura_vinculada')
            resolucion_cd_id = request.POST.get('resolucion_cd')
            fecha_inicio = request.POST.get('fecha_inicio')
            fecha_fin = request.POST.get('fecha_fin') or None
            observaciones = request.POST.get('observaciones', '')

            # Crear la actividad sustantiva
            actividad = ActividadSustantiva(
                cargo=cargo,
                tipo_actividad=tipo_actividad,
                descripcion=descripcion,
                horas_semanales=int(
                    horas_semanales) if horas_semanales else None,
                codigo_proyecto=codigo_proyecto,
                nombre_proyecto=nombre_proyecto,
                resolucion_cd_id=resolucion_cd_id,
                fecha_inicio=fecha_inicio,
                fecha_fin=fecha_fin,
                observaciones=observaciones,
            )

            # Asignar asignatura vinculada si existe
            if asignatura_vinculada_id:
                actividad.asignatura_vinculada_id = asignatura_vinculada_id

            # Validar y guardar
            actividad.save()

            messages.success(
                request,
                f'Función sustantiva "{actividad.get_tipo_actividad_display()}" agregada exitosamente.'
            )

            return redirect('planta_docente:gestionar_funciones_sustantivas', cargo_pk=cargo.pk)

        except Exception as e:
            messages.error(
                request, f'Error al crear la función sustantiva: {str(e)}')

    # GET: Mostrar formulario
    asignaturas = Asignatura.objects.all().order_by('nombre')
    resoluciones = Resolucion.objects.filter(
        origen__in=['cd', 'csu']
    ).order_by('-año', '-numero')[:50]

    context = {
        'cargo': cargo,
        'asignaturas': asignaturas,
        'resoluciones': resoluciones,
        'tipos_actividad': ActividadSustantiva.TIPO_ACTIVIDAD_CHOICES,
    }

    return render(request, 'planta_docente/funciones_sustantivas/crear.html', context)


@login_required
def editar_funcion_sustantiva(request, pk):
    """
    Vista para editar una función sustantiva existente.
    """
    funcion = get_object_or_404(ActividadSustantiva, pk=pk)
    cargo = funcion.cargo

    if request.method == 'POST':
        try:
            # Actualizar campos
            funcion.tipo_actividad = request.POST.get('tipo_actividad')
            funcion.descripcion = request.POST.get('descripcion')

            horas = request.POST.get('horas_semanales')
            funcion.horas_semanales = int(horas) if horas else None

            funcion.codigo_proyecto = request.POST.get('codigo_proyecto', '')
            funcion.nombre_proyecto = request.POST.get('nombre_proyecto', '')

            asignatura_id = request.POST.get('asignatura_vinculada')
            funcion.asignatura_vinculada_id = asignatura_id if asignatura_id else None

            funcion.resolucion_cd_id = request.POST.get('resolucion_cd')
            funcion.fecha_inicio = request.POST.get('fecha_inicio')

            fecha_fin = request.POST.get('fecha_fin')
            funcion.fecha_fin = fecha_fin if fecha_fin else None

            funcion.activa = request.POST.get('activa') == 'on'
            funcion.observaciones = request.POST.get('observaciones', '')

            funcion.save()

            messages.success(
                request, 'Función sustantiva actualizada exitosamente.')
            return redirect('planta_docente:gestionar_funciones_sustantivas', cargo_pk=cargo.pk)

        except Exception as e:
            messages.error(request, f'Error al actualizar: {str(e)}')

    # GET: Mostrar formulario
    asignaturas = Asignatura.objects.all().order_by('nombre')
    resoluciones = Resolucion.objects.filter(
        origen__in=['cd', 'csu']
    ).order_by('-año', '-numero')[:50]

    context = {
        'funcion': funcion,
        'cargo': cargo,
        'asignaturas': asignaturas,
        'resoluciones': resoluciones,
        'tipos_actividad': ActividadSustantiva.TIPO_ACTIVIDAD_CHOICES,
    }

    return render(request, 'planta_docente/funciones_sustantivas/editar.html', context)


@login_required
def eliminar_funcion_sustantiva(request, pk):
    """
    Vista para eliminar una función sustantiva.
    """
    funcion = get_object_or_404(ActividadSustantiva, pk=pk)
    cargo_pk = funcion.cargo.pk

    if request.method == 'POST':
        nombre = funcion.get_tipo_actividad_display()
        funcion.delete()
        messages.success(
            request, f'Función sustantiva "{nombre}" eliminada exitosamente.')
        return redirect('planta_docente:gestionar_funciones_sustantivas', cargo_pk=cargo_pk)

    context = {
        'funcion': funcion,
    }

    return render(request, 'planta_docente/funciones_sustantivas/eliminar.html', context)


@login_required
def toggle_activa_funcion_sustantiva(request, pk):
    """
    Vista AJAX para activar/desactivar una función sustantiva.
    """
    if request.method == 'POST':
        funcion = get_object_or_404(ActividadSustantiva, pk=pk)
        funcion.activa = not funcion.activa
        funcion.save()

        return JsonResponse({
            'success': True,
            'activa': funcion.activa,
            'mensaje': f'Función sustantiva {"activada" if funcion.activa else "desactivada"}.'
        })

    return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)
