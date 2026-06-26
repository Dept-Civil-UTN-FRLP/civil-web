from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render
from django.db.models import Q

from .models import Acta, CicloLectivo, Disposicion


@login_required
def lista_actas_view(request):
    ciclos = CicloLectivo.objects.prefetch_related("actas").all()
    return render(request, "digesto/lista_actas.html", {"ciclos": ciclos})


@login_required
def detalle_acta_view(request, pk):
    acta = get_object_or_404(Acta, pk=pk)
    return render(request, "digesto/detalle_acta.html", {"acta": acta})


@login_required
def buscar_view(request):
    query = request.GET.get("q", "").strip()
    actas = []
    disposiciones = []
    if query:
        actas = Acta.objects.filter(contenido_md__icontains=query).order_by("-ciclo__anio", "-numero")
        disposiciones = Disposicion.objects.filter(texto__icontains=query).select_related("acta__ciclo")
    return render(request, "digesto/buscar.html", {
        "query": query,
        "actas": actas,
        "disposiciones": disposiciones,
    })


@login_required
def lista_disposiciones_view(request):
    disposiciones = Disposicion.objects.select_related("acta__ciclo", "deroga__acta", "modifica__acta").all()
    return render(request, "digesto/lista_disposiciones.html", {"disposiciones": disposiciones})


@login_required
def detalle_disposicion_view(request, pk):
    disposicion = get_object_or_404(
        Disposicion.objects.select_related("acta__ciclo", "deroga__acta", "modifica__acta"),
        pk=pk,
    )
    return render(request, "digesto/detalle_disposicion.html", {"disposicion": disposicion})
