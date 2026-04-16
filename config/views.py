from django.shortcuts import render
from equivalencias.models import AsignaturaParaEquivalencia, Estudiante, SolicitudEquivalencia
from planta_docente.models import Asignatura
from itertools import groupby


NIVEL_LABELS = {
    'i': '1° año', 'ii': '2° año', 'iii': '3° año',
    'iv': '4° año', 'v': '5° año', 'vi': '6° año', '-': 'Sin nivel',
}


def _handle_dni_consulta(request):
    solicitudes = None
    dni_buscado = None
    error_dni = None

    if request.method == 'POST':
        dni = request.POST.get('dni', '').strip()
        if dni:
            dni_buscado = dni
            try:
                estudiante = Estudiante.objects.get(dni_pasaporte=dni)
                solicitudes = SolicitudEquivalencia.objects.filter(
                    id_estudiante=estudiante
                ).prefetch_related(
                    'detallesolicitud_set__id_asignatura__asignatura',
                    'detallesolicitud_set__id_asignatura__docente_responsable__correos',
                ).order_by('-fecha_inicio')

                if not solicitudes.exists():
                    error_dni = "No se encontraron solicitudes para ese DNI."
            except Estudiante.DoesNotExist:
                error_dni = "No se encontraron solicitudes para ese DNI."
        else:
            error_dni = "Ingresá tu DNI para consultar."

    return {
        "solicitudes": solicitudes,
        "dni_buscado": dni_buscado,
        "error_dni": error_dni,
    }


def _get_landing_context(especialidad):
    asignaturas = AsignaturaParaEquivalencia.objects.select_related(
        'asignatura', 'docente_responsable',
    ).filter(asignatura__especialidad=especialidad).order_by(
        'asignatura__nivel', 'asignatura__nombre'
    )

    asignaturas_plan = Asignatura.objects.filter(
        especialidad=especialidad, obligatoria=True, tipo='asignatura',
    ).order_by('nivel', 'nombre')

    plan_estudios = []
    for nivel, materias_grupo in groupby(asignaturas_plan, key=lambda a: a.nivel):
        plan_estudios.append({
            "label": NIVEL_LABELS.get(nivel, f"Nivel {nivel.upper()}"),
            "materias": [{"nombre": a.nombre.title(), "programa": a.programa} for a in materias_grupo],
        })

    electivas = Asignatura.objects.filter(
        especialidad=especialidad, obligatoria=False, tipo='asignatura',
    ).order_by('nombre')

    if electivas.exists():
        plan_estudios.append({
            "label": "Electivas",
            "materias": [{"nombre": a.nombre.title(), "programa": a.programa} for a in electivas],
        })

    laboratorios = Asignatura.objects.filter(
        especialidad=especialidad, tipo__in=['laboratorio', 'grupo', 'centro'],
    ).order_by('nombre')

    return {
        "asignaturas": asignaturas,
        "plan_estudios": plan_estudios,
        "laboratorios": laboratorios,
    }


def landing_civil(request):
    context = _get_landing_context('civil')
    context.update(_handle_dni_consulta(request))
    context["perfil_items"] = [
        {
            "titulo": "Infraestructura urbana",
            "descripcion": "Edificios, viviendas, fábricas y toda obra relacionada con el entorno urbano.",
            "icon_path": '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M9 21V9"/>',
        },
        {
            "titulo": "Vías y transporte",
            "descripcion": "Puentes, carreteras, vías ferroviarias, puertos y aeropuertos.",
            "icon_path": '<path d="M3 12h18M3 6l9-3 9 3M3 18l9 3 9-3"/>',
        },
        {
            "titulo": "Hidráulica y ambiente",
            "descripcion": "Sistemas de riego, aprovechamientos hidroeléctricos, desagües y control ecológico.",
            "icon_path": '<path d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10 10-4.5 10-10S17.5 2 12 2z"/><path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>',
        },
        {
            "titulo": "Gestión y planificación",
            "descripcion": "Factibilidad, presupuestación, dirección de obras y control técnico-económico.",
            "icon_path": '<path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/>',
        },
    ]
    return render(request, "civil/landing.html", context)


def landing_industrial(request):
    context = _get_landing_context('industrial')
    context.update(_handle_dni_consulta(request))
    context["perfil_items"] = [
        {
            "titulo": "Producción y operaciones",
            "descripcion": "Diseño y gestión de sistemas productivos, planificación y control de la producción.",
            "icon_path": '<rect x="2" y="7" width="20" height="14" rx="2"/><path d="M16 3h-8M12 3v4"/>',
        },
        {
            "titulo": "Calidad e innovación",
            "descripcion": "Implementación de sistemas de gestión de calidad, mejora continua e innovación tecnológica.",
            "icon_path": '<path d="M9 11l3 3L22 4"/><circle cx="12" cy="12" r="10"/>',
        },
        {
            "titulo": "Logística y cadena de valor",
            "descripcion": "Optimización de cadenas de suministro, distribución y gestión de recursos.",
            "icon_path": '<path d="M3 12h18M3 6l9-3 9 3M3 18l9 3 9-3"/>',
        },
        {
            "titulo": "Gestión organizacional",
            "descripcion": "Conducción de proyectos, integración del factor humano y toma de decisiones estratégicas.",
            "icon_path": '<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/>',
        },
    ]
    return render(request, "industrial/landing.html", context)
