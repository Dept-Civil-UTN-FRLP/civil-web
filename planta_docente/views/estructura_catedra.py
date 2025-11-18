from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q, Prefetch
from django.shortcuts import render, get_object_or_404
from django.utils import timezone

from planta_docente.models import Asignatura, Cargo


@login_required
def dashboard_asignaturas(request):
    """
    Dashboard con listado de asignaturas y filtros.
    """
    asignaturas = Asignatura.objects.all()

    # Filtros
    nombre = request.GET.get('nombre', '')
    nivel = request.GET.get('nivel', '')
    departamento = request.GET.get('departamento', '')
    especialidad = request.GET.get('especialidad', '')

    if nombre:
        asignaturas = asignaturas.filter(nombre__icontains=nombre)
    if nivel:
        asignaturas = asignaturas.filter(nivel=nivel)
    if departamento:
        asignaturas = asignaturas.filter(departamento=departamento)
    if especialidad:
        asignaturas = asignaturas.filter(especialidad=especialidad)

    # Ordenar
    asignaturas = asignaturas.order_by('-obligatoria', 'nivel', 'nombre')

    # Paginación
    paginator = Paginator(asignaturas, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'filtros': {
            'nombre': nombre,
            'nivel': nivel,
            'departamento': departamento,
            'especialidad': especialidad,
        },
        'nivel_choices': Asignatura.NIVEL_CHOICES,
        'depto_choices': Asignatura.DEPTO_CHOICES,
        'especialidad_choices': Asignatura.ESPECIALIDAD_CHOICES,
    }

    return render(request, 'planta_docente/estructura_catedra/dashboard.html', context)


@login_required
def formulario_estructura(request, asignatura_id):
    """
    Formulario pre-impresión para configurar el PDF.
    """
    asignatura = get_object_or_404(Asignatura, pk=asignatura_id)

    # Obtener cargos activos (excluyendo Ad-Honorem)
    cargos = Cargo.objects.filter(
        asignatura=asignatura,
        estado='activo'
    ).exclude(
        caracter='adh'
    ).select_related('docente').prefetch_related('resoluciones').order_by('categoria')

    context = {
        'asignatura': asignatura,
        'cargos': cargos,
        'ano_actual': timezone.now().year,
    }

    return render(request, 'planta_docente/estructura_catedra/formulario.html', context)
