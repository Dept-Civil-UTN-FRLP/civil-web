from django.shortcuts import render
from .models import Asignatura, Cargo, Docente, AsignaturaParaEquivalencia
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages

# planta_docente/views.py


@login_required
def detalle_asignatura_view(request, pk):
    asignatura = get_object_or_404(Asignatura, pk=pk)

    # Lógica para actualizar el responsable de equivalencias
    if request.method == "POST":
        responsable_id = request.POST.get("responsable_id")
        responsable = get_object_or_404(Docente, pk=responsable_id)

        # Usamos get_or_create para crear el vínculo si no existe
        asig_para_equiv, created = AsignaturaParaEquivalencia.objects.get_or_create(
            asignatura=asignatura
        )
        asig_para_equiv.docente_responsable = responsable
        asig_para_equiv.save()

        messages.success(
            request,
            f"Se asignó a {responsable} como responsable de equivalencias para {asignatura}.",
        )
        return redirect("detalle_asignatura", pk=asignatura.pk)

    # Obtenemos los cargos
    cargos_activos = Cargo.objects.filter(
        asignatura=asignatura, estado="activo"
    ).select_related("docente")
    cargos_historicos = (
        Cargo.objects.filter(asignatura=asignatura)
        .exclude(estado="activo")
        .select_related("docente")
    )

    # Obtenemos el responsable actual de equivalencias
    responsable_actual = AsignaturaParaEquivalencia.objects.filter(
        asignatura=asignatura
    ).first()

    # Obtenemos la lista de docentes para el dropdown
    docentes_elegibles = Docente.objects.filter(
        cargo_docente__caracter__in=["ord", "reg"]
    ).distinct()

    contexto = {
        "asignatura": asignatura,
        "cargos_activos": cargos_activos,
        "cargos_historicos": cargos_historicos,
        "responsable_actual": responsable_actual,
        "docentes_elegibles": docentes_elegibles,
    }
    return render(request, "planta_docente/detalle_asignatura.html", contexto)
