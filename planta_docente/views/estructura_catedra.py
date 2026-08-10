from datetime import datetime
from django.conf import settings

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Prefetch, Q
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.utils import timezone
from weasyprint import HTML
from django.shortcuts import get_object_or_404, redirect, render

from planta_docente.models import Asignatura, Cargo, ActividadSustantiva
from planta_docente.forms import AsignaturaFichaForm
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages


@login_required
def dashboard_asignaturas(request):
    """
    Dashboard con listado de asignaturas y filtros.
    """
    asignaturas = Asignatura.objects.all()

    # Filtros
    nombre = request.GET.get("nombre", "")
    nivel = request.GET.get("nivel", "")
    departamento = request.GET.get("departamento", "")
    especialidad = request.GET.get("especialidad", "")

    if nombre:
        asignaturas = asignaturas.filter(nombre__icontains=nombre)
    if nivel:
        asignaturas = asignaturas.filter(nivel=nivel)
    if departamento:
        asignaturas = asignaturas.filter(departamento=departamento)
    if especialidad:
        asignaturas = asignaturas.filter(especialidad=especialidad)

    # Ordenar
    asignaturas = asignaturas.order_by("-obligatoria", "nivel", "nombre")

    # Paginación
    paginator = Paginator(asignaturas, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "filtros": {
            "nombre": nombre,
            "nivel": nivel,
            "departamento": departamento,
            "especialidad": especialidad,
        },
        "nivel_choices": Asignatura.NIVEL_CHOICES,
        "depto_choices": Asignatura.DEPTO_CHOICES,
        "especialidad_choices": Asignatura.ESPECIALIDAD_CHOICES,
    }

    return render(request, "planta_docente/estructura_catedra/dashboard.html", context)


@login_required
def formulario_estructura(request, asignatura_id):
    """
    Formulario pre-impresión para configurar el PDF.
    """
    asignatura = get_object_or_404(Asignatura, pk=asignatura_id)

    # Obtener cargos activos (incluye Ad-Honorem para que se vean en la vista previa)
    cargos = (
        Cargo.objects.filter(asignatura=asignatura, estado="activo")
        .select_related("docente")
        .prefetch_related("resoluciones")
        .order_by("categoria")
    )

    context = {
        "asignatura": asignatura,
        "cargos": cargos,
        "ano_actual": timezone.now().year,
    }

    return render(request, "planta_docente/estructura_catedra/formulario.html", context)


def calcular_antiguedad(fecha_inicio):
    """Calcula antigüedad en formato 'X años Y meses'."""
    hoy = timezone.now().date()
    years = hoy.year - fecha_inicio.year
    months = hoy.month - fecha_inicio.month

    if months < 0:
        years -= 1
        months += 12

    if years > 0 and months > 0:
        return f"{years} A {months} M"
    elif years > 0:
        return f"{years} A"
    elif months > 0:
        return f"{months} M"
    else:
        return "Menos de 1 mes"


@login_required
def generar_pdf_estructura(request, asignatura_id):
    """
    Genera el PDF de estructura de cátedra.
    """
    if request.method != "POST":
        return HttpResponse("Método no permitido", status=405)

    asignatura = get_object_or_404(Asignatura, pk=asignatura_id)

    # Datos del formulario
    numero_estudiantes = request.POST.get("numero_estudiantes")
    otros_aportes = request.POST.get("otros_aportes", "")
    incluir_areas = request.POST.get("incluir_areas") == "on"
    incluir_bloques = request.POST.get("incluir_bloques") == "on"
    incluir_otros_aportes = request.POST.get("incluir_otros_aportes") == "on"
    incluir_adhonorem = request.POST.get("incluir_adhonorem") == "on"

    # Obtener cargos activos optimizados
    cargos_query = (
        Cargo.objects.filter(asignatura=asignatura, estado="activo")
        .select_related("docente")
        .prefetch_related("resoluciones")
        .order_by("categoria", "docente__apellido")
    )
    if not incluir_adhonorem:
        cargos_query = cargos_query.exclude(caracter="adh")

    # Separar profesores y auxiliares
    categorias_profesores = ["tit", "aso", "adj"]
    categorias_auxiliares = ["jtp", "atp1", "atp2", "ads"]

    profesores = []
    auxiliares = []

    for cargo in cargos_query:
        # Considerar licencias M.J.
        cargo_efectivo = cargo.get_cargo_efectivo_docente()

        # Calcular fechas
        fecha_primera = cargo.fecha_inicio

        # Última designación: resolución más reciente de alta o designación
        resoluciones = cargo.resoluciones.filter(
            objeto__in=['alta', 'designacion']
        ).order_by('año', 'numero')

        if cargo.caracter == 'int':
            # Interino: la más cercana entre fecha_inicio y 1/4 del año actual
            from datetime import date
            primer_abril = date(timezone.now().year, 4, 1)
            fecha_ultima = min(
                fecha_primera, primer_abril).strftime('%d/%m/%Y')
        else:
            # Ordinario / Regular: primera resolución de ese tipo y última redesignación
            primera_res = resoluciones.first()
            ultima_res = resoluciones.last()
            if primera_res and ultima_res and primera_res.pk != ultima_res.pk:
                fecha_ultima = f"{primera_res.año} / {ultima_res.año}"
            elif primera_res:
                fecha_ultima = str(primera_res.año)
            else:
                fecha_ultima = str(cargo.fecha_inicio.year)

        # Antigüedad
        antiguedad = calcular_antiguedad(fecha_primera)

        # Verificar si es función sustantiva desde otro cargo
        es_funcion_sustantiva = False
        cargo_origen = None

        # Buscar si este docente tiene una función sustantiva en esta asignatura
        funcion_sustantiva = ActividadSustantiva.objects.filter(
            cargo__docente=cargo.docente,
            asignatura_vinculada=asignatura,
            activa=True
        ).select_related('cargo').first()

        if funcion_sustantiva:
            es_funcion_sustantiva = True
            cargo_origen = funcion_sustantiva.cargo

        cargo_data = {
            'docente': cargo.docente,
            'legajo': cargo.docente.legajo,
            'categoria': cargo.get_categoria_display_abreviada(),
            'caracter': cargo.get_caracter_display(),
            'dedicacion': cargo.get_dedicacion_display(),
            'comisiones': cargo.cantidad_comisiones,
            'fecha_primera': fecha_primera.strftime('%d/%m/%Y'),
            'fecha_ultima': fecha_ultima,
            'antiguedad': antiguedad,
            'es_funcion_sustantiva': es_funcion_sustantiva,
            'cargo_origen': cargo_origen,
        }

        if cargo.categoria in categorias_profesores:
            profesores.append(cargo_data)
        elif cargo.categoria in categorias_auxiliares:
            auxiliares.append(cargo_data)

    # Calcular totales de comisiones
    total_comisiones_profesores = sum(p["comisiones"] for p in profesores)
    total_comisiones_auxiliares = sum(a["comisiones"] for a in auxiliares)

    # Obtener membrete del año actual
    from carrera_academica.models import MembreteAnual
    import pathlib

    ano_actual = timezone.now().year
    membrete = MembreteAnual.objects.filter(anio=ano_actual).first()

    # ✅ Convertir ruta del logo a URI para WeasyPrint
    logo_uri = None
    if membrete and membrete.logo:
        logo_uri = pathlib.Path(membrete.logo.path).as_uri()

    # Áreas y bloques
    areas = list(asignatura.area.all()) if incluir_areas else []
    bloques = list(asignatura.bloque.all()) if incluir_bloques else []

    import string
    asignaturas_del_area = []
    if areas:
        qs = list(
            Asignatura.objects.filter(area__in=areas)
            .exclude(pk=asignatura.pk)
            .distinct()
            .order_by('nombre')
        )
        asignaturas_del_area = [
            {'letra': string.ascii_lowercase[i], 'nombre': a.nombre}
            for i, a in enumerate(qs)
        ]

    context = {
        "asignatura": asignatura,
        "numero_estudiantes": numero_estudiantes,
        "profesores": profesores,
        "auxiliares": auxiliares,
        "total_comisiones_profesores": total_comisiones_profesores,
        "total_comisiones_auxiliares": total_comisiones_auxiliares,
        "otros_aportes": otros_aportes if incluir_otros_aportes else None,
        "membrete": membrete,
        "logo_uri": logo_uri,  # ✅ Pasar URI del logo
        "fecha_generacion": timezone.now(),
        "areas": areas,
        "bloques": bloques,
        "asignaturas_del_area": asignaturas_del_area,
        "MEDIA_ROOT": settings.MEDIA_ROOT,
    }

    # Renderizar HTML
    html_string = render_to_string(
        "planta_docente/estructura_catedra/pdf_template.html", context
    )

    # Generar PDF
    html = HTML(string=html_string, base_url=request.build_absolute_uri('/'))
    pdf = html.write_pdf()

    # Respuesta HTTP
    filename = (
        f"estructura_catedra_{asignatura.nombre.replace(' ', '_')}_{ano_actual}.pdf"
    )
    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{filename}"'

    return response


@login_required
@staff_member_required
def editar_ficha_asignatura(request, asignatura_id):
    """
    Vista para editar la ficha completa de una asignatura.
    """
    asignatura = get_object_or_404(Asignatura, pk=asignatura_id)

    if request.method == 'POST':
        form = AsignaturaFichaForm(request.POST, instance=asignatura)

        if form.is_valid():
            form.save()
            messages.success(
                request,
                f'✓ Ficha de "{asignatura.nombre}" actualizada correctamente.'
            )
            return redirect('planta_docente:ver_ficha_asignatura', asignatura_id=asignatura.pk)
        else:
            messages.error(
                request, 'Por favor corrige los errores del formulario.')
    else:
        form = AsignaturaFichaForm(instance=asignatura)

    context = {
        'form': form,
        'asignatura': asignatura,
    }

    return render(request, 'planta_docente/asignatura/editar_ficha.html', context)


@login_required
def ver_ficha_asignatura(request, asignatura_id):
    """
    Vista para ver la ficha completa de una asignatura.
    """
    asignatura = get_object_or_404(Asignatura, pk=asignatura_id)

    # Obtener áreas y bloques
    areas = asignatura.area.all()
    bloques = asignatura.bloque.all()

    # ✅ Filtro de cargos activos/todos
    mostrar_todos = request.GET.get('mostrar_todos', 'false') == 'true'
    
    from planta_docente.models import Cargo

    if mostrar_todos:
        # Mostrar todos los cargos
        cargos = Cargo.objects.filter(
            asignatura=asignatura
        ).select_related('docente').order_by('categoria', 'docente__apellido')
    else:
        # Por defecto solo activos
        cargos = Cargo.objects.filter(
            asignatura=asignatura,
            estado='activo'
        ).select_related('docente').order_by('categoria', 'docente__apellido')

    # Agrupar cargos por categoría según tipo
    profesores = []  # Titular, Asociado, Adjunto
    auxiliares = []  # JTP, ATP1, ATP2

    TIPOS_PROFESORES = ['tit', 'aso', 'adj']
    TIPOS_AUXILIARES = ['jtp', 'atp1', 'atp2', 'ads']
    
    for cargo in cargos:
        tipo_nombre = cargo.categoria

        # Clasificar por tipo
        if any(tipo in tipo_nombre for tipo in TIPOS_PROFESORES):
            profesores.append(cargo)
        elif any(tipo in tipo_nombre for tipo in TIPOS_AUXILIARES):
            auxiliares.append(cargo)

    # Parsear objetivos (uno por línea)
    objetivos_lista = []
    if asignatura.objetivos:
        objetivos_lista = [
            obj.strip().lstrip('•').lstrip('-').strip()
            for obj in asignatura.objetivos.split('\n')
            if obj.strip()
        ]
        
    # Parsear contenidos (uno por línea)
    contenidos_lista = []
    if asignatura.contenidos_minimos:
        contenidos_lista = [
            obj.strip().lstrip('•').lstrip('-').strip()
            for obj in asignatura.contenidos_minimos.split('\n')
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
    
    # Parsear bibliografía básica (uno por línea)
    bibliografia_basica_lista = []
    if asignatura.bibliografia_basica:
        bibliografia_basica_lista = [
            item.strip()
            for item in asignatura.bibliografia_basica.split('\n')
            if item.strip()
        ]

    # Parsear bibliografía complementaria (uno por línea)
    bibliografia_complementaria_lista = []
    if asignatura.bibliografia_complementaria:
        bibliografia_complementaria_lista = [
            item.strip()
            for item in asignatura.bibliografia_complementaria.split('\n')
            if item.strip()
        ]

    context = {
        'asignatura': asignatura,
        'areas': areas,
        'bloques': bloques,
        'objetivos_lista': objetivos_lista,
        'competencias_lista': competencias_lista,
        'contenidos_lista': contenidos_lista,
        'profesores': profesores,
        'auxiliares': auxiliares,
        'bibliografia_basica_lista': bibliografia_basica_lista,
        'bibliografia_complementaria_lista': bibliografia_complementaria_lista,
        'mostrar_todos': mostrar_todos,
        'total_cargos': cargos.count(),
    }

    return render(request, 'planta_docente/asignatura/ver_ficha.html', context)