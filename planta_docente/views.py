"""
Views para el módulo de planta docente.
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Count, Prefetch
from django.http import JsonResponse
from django.utils import timezone
from datetime import timedelta

from .models import Docente, Cargo, Asignatura
from carrera_academica.models import CarreraAcademica
from carrera_academica.forms import CarreraAcademicaForm
from config.pagination import paginate_queryset
from .utils import (
    calcular_edad,
    calcular_antiguedad,
    obtener_estado_vencimiento,
    obtener_estado_jubilacion,
    formatear_antiguedad,
    obtener_alertas_cargo,
)
# planta_docente/views.py


@login_required
def dashboard_planta_view(request):
    """
    Dashboard principal de planta docente.
    
    Muestra resumen de:
    - Cargos activos con alertas
    - Estadísticas generales
    - Filtros por estado, departamento, dedicación
    
    Args:
        request: HttpRequest
        
    Query params:
        - q: Búsqueda por nombre/apellido de docente
        - estado: Filtro por estado del cargo
        - departamento: Filtro por departamento
        - dedicacion: Filtro por dedicación
        - categoria: Filtro por categoría
        - alerta: Filtro por tipo de alerta (vencimiento, jubilacion)
    """
    
    # Usar manager personalizado y excluir jubilados
    cargos_qs = Cargo.objects.with_related_data()

    # Excluir docentes jubilados por defecto
    incluir_jubilados = request.GET.get('incluir_jubilados', 'false') == 'true'
    if not incluir_jubilados:
        cargos_qs = cargos_qs.filter(docente__jubilado=False)

    # Aplicar filtros
    search_query = request.GET.get('q', '').strip()
    estado_filter = request.GET.get('estado', '')
    departamento_filter = request.GET.get('departamento', '')
    dedicacion_filter = request.GET.get('dedicacion', '')
    categoria_filter = request.GET.get('categoria', '')
    alerta_filter = request.GET.get('alerta', '')

    # Filtro de búsqueda
    if search_query:
        cargos_qs = cargos_qs.filter(
            Q(docente__nombre__icontains=search_query) |
            Q(docente__apellido__icontains=search_query) |
            Q(docente__legajo__icontains=search_query)
        )

    # Filtro por estado
    if estado_filter:
        if estado_filter == 'activo':
            cargos_qs = cargos_qs.activos()
        elif estado_filter == 'licencia':
            cargos_qs = cargos_qs.en_licencia()
        elif estado_filter == 'baja':
            cargos_qs = cargos_qs.dados_de_baja()
    else:
        # Por defecto mostrar solo activos y en licencia
        cargos_qs = cargos_qs.filter(estado__in=['activo', 'licencia'])

    # Filtro por departamento
    if departamento_filter:
        cargos_qs = cargos_qs.por_departamento(departamento_filter)

    # Filtro por dedicación
    if dedicacion_filter:
        cargos_qs = cargos_qs.por_dedicacion(dedicacion_filter)

    # Filtro por categoría
    if categoria_filter:
        cargos_qs = cargos_qs.por_categoria(categoria_filter)

    # Filtro por tipo de alerta
    if alerta_filter == 'vencimiento':
        # Cargos que vencen en 6 meses o ya vencidos
        cargos_qs = cargos_qs.filter(
            Q(fecha_vencimiento__lte=timezone.now().date() + timedelta(days=180)) |
            Q(fecha_vencimiento__lt=timezone.now().date())
        )
    elif alerta_filter == 'jubilacion':
        # Docentes mayores de 65 años
        fecha_65_años = timezone.now().date() - timedelta(days=65*365)
        cargos_qs = cargos_qs.filter(
            docente__fecha_nacimiento__lte=fecha_65_años)

    # Ordenar: primero los que tienen alertas urgentes
    cargos_qs = cargos_qs.order_by(
        '-estado', 'fecha_vencimiento', 'docente__apellido')

    # ✅ PAGINACIÓN
    page_obj, pagination_context = paginate_queryset(
        cargos_qs, request, page_size=25)

    # Enriquecer cada cargo con información calculada
    for cargo in page_obj:
        # Estado de vencimiento
        cargo.estado_venc = obtener_estado_vencimiento(cargo)

        # Estado de jubilación del docente
        cargo.estado_jub = obtener_estado_jubilacion(cargo.docente)

        # Antigüedad
        antiguedad = calcular_antiguedad(cargo.fecha_inicio)
        cargo.antiguedad_texto = formatear_antiguedad(antiguedad)
        cargo.antiguedad_años = antiguedad['años']

        # Alertas
        cargo.alertas = obtener_alertas_cargo(cargo)
        cargo.tiene_alertas_urgentes = any(a['urgente'] for a in cargo.alertas)

        # Verificar si tiene CA
        cargo.tiene_ca = hasattr(cargo, 'carrera_academica')

    # Calcular estadísticas generales (solo para el queryset filtrado, no paginado)
    stats = _calcular_estadisticas_dashboard(cargos_qs)

    # Preparar contexto
    contexto = {
        'cargos': page_obj,
        'stats': stats,
        'incluir_jubilados': incluir_jubilados,
        'search_query': search_query,
        'estado_filter': estado_filter,
        'departamento_filter': departamento_filter,
        'dedicacion_filter': dedicacion_filter,
        'categoria_filter': categoria_filter,
        'alerta_filter': alerta_filter,
        'estado_choices': Cargo.ESTADO_CHOICES,
        'departamento_choices': Asignatura.DEPTO_CHOICES,
        'dedicacion_choices': Cargo.DEDICACION_CHOICES,
        'categoria_choices': Cargo.CATEGORIA_CHOICES,
        **pagination_context,
    }

    return render(request, 'planta_docente/dashboard.html', contexto)


def _calcular_estadisticas_dashboard(cargos_qs):
    """
    Calcula estadísticas para el dashboard.
    
    Args:
        cargos_qs: QuerySet de cargos (ya filtrado)
        
    Returns:
        dict: Diccionario con estadísticas
    """
    total_cargos = cargos_qs.count()

    # Cargos por estado
    cargos_activos = cargos_qs.filter(estado='activo').count()
    cargos_licencia = cargos_qs.filter(estado='licencia').count()

    # Cargos próximos a vencer (60 días)
    cargos_criticos = cargos_qs.filter(
        fecha_vencimiento__lte=timezone.now().date() + timedelta(days=60),
        fecha_vencimiento__gte=timezone.now().date()
    ).count()

    # Cargos vencidos
    cargos_vencidos = cargos_qs.filter(
        fecha_vencimiento__lt=timezone.now().date()
    ).count()

    # Cargos jubilados
    total_docentes_jubilados = cargos_qs.filter(
        docente__jubilado=True
    ).values('docente').distinct().count()

    # Cargos regulares/ordinarios sin CA
    cargos_sin_ca = cargos_qs.filter(
        caracter__in=['reg', 'ord'],
        carrera_academica__isnull=True
    ).count()

    # Docentes únicos con alerta de jubilación
    fecha_65_años = timezone.now().date() - timedelta(days=65*365)
    docentes_mayores_65 = cargos_qs.filter(
        docente__fecha_nacimiento__lte=fecha_65_años
    ).values('docente').distinct().count()

    return {
        'total_cargos': total_cargos,
        'cargos_activos': cargos_activos,
        'cargos_licencia': cargos_licencia,
        'cargos_criticos': cargos_criticos,
        'cargos_vencidos': cargos_vencidos,
        'cargos_sin_ca': cargos_sin_ca,
        'docentes_mayores_65': docentes_mayores_65,
        'total_docentes_jubilados': total_docentes_jubilados,
    }


@login_required
def detalle_cargo_view(request, pk):
    """
    Vista de detalle de un cargo específico.
    
    Muestra:
    - Información completa del cargo
    - Información del docente
    - Antigüedad calculada
    - Estado de vencimiento
    - Estado de jubilación del docente
    - Historial de resoluciones
    - Carrera Académica asociada (si existe)
    - Botón para iniciar CA (si corresponde)
    
    Args:
        request: HttpRequest
        pk: ID del cargo
    """
    # ✅ OPTIMIZACIÓN: Usar select_related y prefetch_related
    cargo = get_object_or_404(
        Cargo.objects.select_related(
            'docente',
            'asignatura',
        ).prefetch_related(
            'docente__correos',
            'resoluciones',
        ),
        pk=pk
    )

    # Calcular información adicional
    estado_venc = obtener_estado_vencimiento(cargo)
    estado_jub = obtener_estado_jubilacion(cargo.docente)
    antiguedad = calcular_antiguedad(cargo.fecha_inicio)
    antiguedad_texto = formatear_antiguedad(antiguedad)
    alertas = obtener_alertas_cargo(cargo)

    # Verificar si tiene CA
    tiene_ca = hasattr(cargo, 'carrera_academica')
    puede_iniciar_ca = (
        cargo.caracter in ['reg', 'ord'] and
        not tiene_ca and
        cargo.estado == 'activo'
    )

    # Obtener correo principal del docente
    correo_principal = cargo.docente.correos.filter(principal=True).first()

    # Historial de resoluciones ordenado
    resoluciones = cargo.resoluciones.all().order_by('-año', '-numero')

    contexto = {
        'cargo': cargo,
        'estado_venc': estado_venc,
        'estado_jub': estado_jub,
        'antiguedad': antiguedad,
        'antiguedad_texto': antiguedad_texto,
        'alertas': alertas,
        'tiene_ca': tiene_ca,
        'puede_iniciar_ca': puede_iniciar_ca,
        'correo_principal': correo_principal,
        'resoluciones': resoluciones,
    }

    return render(request, 'planta_docente/detalle_cargo.html', contexto)


@login_required
def detalle_docente_view(request, pk):
    """
    Vista de detalle de un docente.
    
    Muestra:
    - Información personal
    - Edad y estado de jubilación
    - Lista de todos sus cargos (activos e históricos)
    - Correos electrónicos
    
    Args:
        request: HttpRequest
        pk: ID del docente
    """
    # ✅ OPTIMIZACIÓN: Prefetch de relaciones
    docente = get_object_or_404(
        Docente.objects.prefetch_related(
            'correos',
            'cargo_docente',
            'cargo_docente__asignatura',
            'cargo_docente__carrera_academica',
        ),
        pk=pk
    )

    # Calcular edad y estado de jubilación
    edad = calcular_edad(docente.fecha_nacimiento)
    estado_jub = obtener_estado_jubilacion(docente)

    # Separar cargos activos e históricos
    cargos_activos = docente.cargo_docente.filter(estado='activo')
    cargos_historicos = docente.cargo_docente.exclude(estado='activo')

    # Enriquecer cargos activos con información
    for cargo in cargos_activos:
        cargo.estado_venc = obtener_estado_vencimiento(cargo)
        antiguedad = calcular_antiguedad(cargo.fecha_inicio)
        cargo.antiguedad_texto = formatear_antiguedad(antiguedad)
        cargo.tiene_ca = hasattr(cargo, 'carrera_academica')

    # Correos
    correo_principal = docente.correos.filter(principal=True).first()
    otros_correos = docente.correos.filter(principal=False)

    contexto = {
        'docente': docente,
        'edad': edad,
        'estado_jub': estado_jub,
        'cargos_activos': cargos_activos,
        'cargos_historicos': cargos_historicos,
        'correo_principal': correo_principal,
        'otros_correos': otros_correos,
    }

    return render(request, 'planta_docente/detalle_docente.html', contexto)


@login_required
def vencimientos_view(request):
    """
    Reporte de cargos próximos a vencer.
    
    Muestra cargos que vencen en los próximos 6 meses,
    ordenados por fecha de vencimiento.
    
    Query params:
        - dias: Días hacia adelante (default: 180)
        - incluir_vencidos: Si incluir cargos ya vencidos (default: True)
    """
    dias = int(request.GET.get('dias', 180))
    incluir_vencidos = request.GET.get('incluir_vencidos', 'true') == 'true'

    # Obtener cargos próximos a vencer
    cargos_qs = Cargo.objects.with_related_data().proximos_a_vencer(dias)

    # Incluir vencidos si se solicita
    if incluir_vencidos:
        cargos_vencidos = Cargo.objects.with_related_data().vencidos()
        cargos_qs = cargos_qs | cargos_vencidos

    # Ordenar por urgencia (vencidos primero, luego por fecha)
    cargos_qs = cargos_qs.order_by('fecha_vencimiento')

    # Enriquecer con información
    cargos = list(cargos_qs)
    for cargo in cargos:
        cargo.estado_venc = obtener_estado_vencimiento(cargo)
        antiguedad = calcular_antiguedad(cargo.fecha_inicio)
        cargo.antiguedad_texto = formatear_antiguedad(antiguedad)
        cargo.tiene_ca = hasattr(cargo, 'carrera_academica')

    # Agrupar por urgencia
    vencidos = [c for c in cargos if c.estado_venc['tipo'] == 'vencido']
    criticos = [c for c in cargos if c.estado_venc['tipo'] == 'critico']
    proximos = [c for c in cargos if c.estado_venc['tipo'] == 'proximo']

    contexto = {
        'vencidos': vencidos,
        'criticos': criticos,
        'proximos': proximos,
        'total_alertas': len(vencidos) + len(criticos) + len(proximos),
        'dias': dias,
        'incluir_vencidos': incluir_vencidos,
    }

    return render(request, 'planta_docente/vencimientos.html', contexto)


@login_required
def jubilaciones_view(request):
    """
    Reporte de docentes próximos a jubilarse.
    
    Muestra docentes que cumplen 65 o 70 años en los próximos años.
    
    Query params:
        - años: Años hacia adelante (default: 2)
    """
    años = int(request.GET.get('años', 2))

    # Obtener docentes próximos a jubilarse
    docentes_qs = Docente.objects.with_related_data().proximos_a_jubilarse(años)

    # También incluir los que ya tienen 65+
    docentes_mayores = Docente.objects.with_related_data().mayores_de_65()

    # Unir querysets
    docentes_qs = (docentes_qs | docentes_mayores).distinct()

    # Enriquecer con información
    docentes = list(docentes_qs)
    for docente in docentes:
        docente.edad = calcular_edad(docente.fecha_nacimiento)
        docente.estado_jub = obtener_estado_jubilacion(docente)

        # Obtener cargos activos
        docente.cargos_activos = docente.cargo_docente.filter(estado='activo')
        for cargo in docente.cargos_activos:
            cargo.tiene_ca = hasattr(cargo, 'carrera_academica')

    # Agrupar por urgencia
    mayores_70 = [
        d for d in docentes if d.estado_jub['estado'] == 'jubilado_70']
    entre_65_70 = [
        d for d in docentes if d.estado_jub['estado'] == 'jubilado_65']
    proximos_65 = [
        d for d in docentes if d.estado_jub['estado'] == 'proximo_65']

    contexto = {
        'mayores_70': mayores_70,
        'entre_65_70': entre_65_70,
        'proximos_65': proximos_65,
        'total_alertas': len(mayores_70) + len(entre_65_70) + len(proximos_65),
        'años': años,
    }

    return render(request, 'planta_docente/jubilaciones.html', contexto)


@login_required
def cargos_sin_ca_view(request):
    """
    Reporte de cargos regulares/ordinarios sin Carrera Académica.
    
    Lista cargos que deberían tener CA iniciada pero no la tienen.
    """
    # Obtener cargos sin CA
    cargos_qs = Cargo.objects.with_related_data().sin_ca().filter(estado='activo')

    # Ordenar por antigüedad (más antiguos primero)
    cargos_qs = cargos_qs.order_by('fecha_inicio')

    # Enriquecer con información
    cargos = list(cargos_qs)
    for cargo in cargos:
        antiguedad = calcular_antiguedad(cargo.fecha_inicio)
        cargo.antiguedad_texto = formatear_antiguedad(antiguedad)
        cargo.antiguedad_años = antiguedad['años']
        cargo.estado_venc = obtener_estado_vencimiento(cargo)

    contexto = {
        'cargos': cargos,
        'total_sin_ca': len(cargos),
    }

    return render(request, 'planta_docente/sin_ca.html', contexto)


@login_required
def iniciar_ca_desde_cargo_view(request, pk):
    """
    Inicia una Carrera Académica desde un cargo existente.
    
    Redirige al formulario de creación de CA con el cargo preseleccionado.
    
    Args:
        request: HttpRequest
        pk: ID del cargo
    """
    cargo = get_object_or_404(Cargo, pk=pk)

    # Verificar que el cargo puede tener CA
    if cargo.caracter not in ['reg', 'ord']:
        messages.error(
            request,
            f'Solo los cargos Regulares u Ordinarios pueden tener Carrera Académica. '
            f'Este cargo es {cargo.get_caracter_display()}.'
        )
        return redirect('planta_docente:detalle_cargo', pk=pk)

    # Verificar que no tenga CA ya
    if hasattr(cargo, 'carrera_academica'):
        messages.warning(
            request,
            'Este cargo ya tiene una Carrera Académica iniciada.'
        )
        return redirect('detalle_ca', pk=cargo.carrera_academica.pk)

    # Verificar que el cargo esté activo
    if cargo.estado != 'activo':
        messages.error(
            request,
            f'No se puede iniciar Carrera Académica para un cargo {cargo.get_estado_display()}.'
        )
        return redirect('planta_docente:detalle_cargo', pk=pk)

    if request.method == 'POST':
        # Crear la CA con las fechas del cargo
        try:
            nueva_ca = CarreraAcademica(
                cargo=cargo,
                fecha_inicio=cargo.fecha_inicio,
                fecha_vencimiento_original=cargo.fecha_vencimiento,
                fecha_vencimiento_actual=cargo.fecha_vencimiento,
            )
            nueva_ca.full_clean()
            nueva_ca.save()

            messages.success(
                request,
                f'Carrera Académica iniciada exitosamente para {cargo.docente}.'
            )
            return redirect('detalle_ca', pk=nueva_ca.pk)

        except Exception as e:
            messages.error(
                request,
                f'Error al crear la Carrera Académica: {str(e)}'
            )
            return redirect('planta_docente:detalle_cargo', pk=pk)

    # GET: Mostrar confirmación
    contexto = {
        'cargo': cargo,
        'docente': cargo.docente,
        'asignatura': cargo.asignatura,
    }

    return render(request, 'planta_docente/confirmar_iniciar_ca.html', contexto)


@login_required
def cargo_info_api_view(request, pk):
    """
    API endpoint para obtener información de un cargo en formato JSON.
    
    Útil para cargar datos vía AJAX sin recargar la página.
    
    Args:
        request: HttpRequest
        pk: ID del cargo
        
    Returns:
        JsonResponse con información del cargo
    """
    try:
        cargo = Cargo.objects.select_related(
            'docente',
            'asignatura'
        ).get(pk=pk)

        # Calcular información
        estado_venc = obtener_estado_vencimiento(cargo)
        estado_jub = obtener_estado_jubilacion(cargo.docente)
        antiguedad = calcular_antiguedad(cargo.fecha_inicio)

        data = {
            'id': cargo.pk,
            'docente': {
                'nombre_completo': str(cargo.docente),
                'legajo': cargo.docente.legajo,
                'edad': calcular_edad(cargo.docente.fecha_nacimiento),
            },
            'asignatura': {
                'nombre': cargo.asignatura.nombre,
                'departamento': cargo.get_asignatura.get_departamento_display(),
            },
            'cargo': {
                'caracter': cargo.get_caracter_display(),
                'categoria': cargo.get_categoria_display(),
                'dedicacion': cargo.get_dedicacion_display(),
                'estado': cargo.get_estado_display(),
            },
            'fechas': {
                'inicio': cargo.fecha_inicio.strftime('%d/%m/%Y'),
                'vencimiento': cargo.fecha_vencimiento.strftime('%d/%m/%Y') if cargo.fecha_vencimiento else None,
            },
            'antiguedad': {
                'años': antiguedad['años'],
                'meses': antiguedad['meses'],
                'dias': antiguedad['dias'],
                'texto': formatear_antiguedad(antiguedad),
            },
            'estado_vencimiento': estado_venc,
            'estado_jubilacion': estado_jub,
            'tiene_ca': hasattr(cargo, 'carrera_academica'),
        }

        return JsonResponse(data)

    except Cargo.DoesNotExist:
        return JsonResponse(
            {'error': 'Cargo no encontrado'},
            status=404
        )
    except Exception as e:
        return JsonResponse(
            {'error': str(e)},
            status=500
        )
