from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Prefetch
from django.shortcuts import get_object_or_404, redirect, render

from .forms import ActaForm, CertificacionForm, CicloLectivoForm, DisposicionForm
from .models import Acta, Certificacion, CicloLectivo, Disposicion


@login_required
def lista_actas_view(request):
    actas = Acta.objects.annotate(
        num_disposiciones=Count("disposiciones", distinct=True),
        num_certificaciones=Count("certificaciones", distinct=True),
    )
    ciclos = CicloLectivo.objects.prefetch_related(Prefetch("actas", queryset=actas))
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


# ── Ciclo Lectivo ────────────────────────────────────────────────────────────

@login_required
def crear_ciclo_view(request):
    form = CicloLectivoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        ciclo = form.save()
        messages.success(request, f"Ciclo Lectivo {ciclo.anio} creado.")
        return redirect("digesto:lista_actas")
    return render(request, "digesto/form_ciclo.html", {"form": form, "titulo": "Nuevo Ciclo Lectivo"})


# ── Acta ─────────────────────────────────────────────────────────────────────

@login_required
def crear_acta_view(request):
    form = ActaForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        acta = form.save()
        messages.success(request, f"Acta {acta} creada.")
        return redirect("digesto:detalle_acta", pk=acta.pk)
    return render(request, "digesto/form_acta.html", {"form": form, "titulo": "Nueva Acta"})


@login_required
def editar_acta_view(request, pk):
    acta = get_object_or_404(Acta, pk=pk)
    form = ActaForm(request.POST or None, request.FILES or None, instance=acta)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Acta actualizada.")
        return redirect("digesto:detalle_acta", pk=acta.pk)
    return render(request, "digesto/form_acta.html", {
        "form": form,
        "titulo": f"Editar Acta — {acta}",
        "acta": acta,
    })


# ── Disposición ──────────────────────────────────────────────────────────────

@login_required
def crear_disposicion_view(request, acta_pk):
    acta = get_object_or_404(Acta, pk=acta_pk)
    form = DisposicionForm(request.POST or None, acta=acta)
    if request.method == "POST" and form.is_valid():
        disposicion = form.save(commit=False)
        disposicion.acta = acta
        disposicion.save()
        messages.success(request, f"Disposición {disposicion.numero} creada.")
        return redirect("digesto:detalle_acta", pk=acta.pk)
    return render(request, "digesto/form_disposicion.html", {
        "form": form,
        "acta": acta,
        "titulo": f"Nueva Disposición — {acta}",
    })


@login_required
def editar_disposicion_view(request, pk):
    disposicion = get_object_or_404(Disposicion.objects.select_related("acta__ciclo"), pk=pk)
    form = DisposicionForm(request.POST or None, instance=disposicion, acta=disposicion.acta)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Disposición actualizada.")
        return redirect("digesto:detalle_acta", pk=disposicion.acta.pk)
    return render(request, "digesto/form_disposicion.html", {
        "form": form,
        "acta": disposicion.acta,
        "disposicion": disposicion,
        "titulo": f"Editar Disposición {disposicion.numero} — {disposicion.acta}",
    })


# ── Certificación ─────────────────────────────────────────────────────────────

@login_required
def crear_certificacion_view(request, acta_pk):
    acta = get_object_or_404(Acta, pk=acta_pk)
    form = CertificacionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        cert = form.save(commit=False)
        cert.acta = acta
        cert.save()
        messages.success(request, f"Certificación {cert.numero} creada.")
        return redirect("digesto:detalle_acta", pk=acta.pk)
    return render(request, "digesto/form_certificacion.html", {
        "form": form,
        "acta": acta,
        "titulo": f"Nueva Certificación — {acta}",
    })


@login_required
def editar_certificacion_view(request, pk):
    cert = get_object_or_404(Certificacion.objects.select_related("acta__ciclo"), pk=pk)
    form = CertificacionForm(request.POST or None, instance=cert)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Certificación actualizada.")
        return redirect("digesto:detalle_acta", pk=cert.acta.pk)
    return render(request, "digesto/form_certificacion.html", {
        "form": form,
        "acta": cert.acta,
        "cert": cert,
        "titulo": f"Editar Certificación {cert.numero} — {cert.acta}",
    })
