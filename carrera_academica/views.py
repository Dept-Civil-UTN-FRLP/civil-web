# carrera_academica/views.py
import io
import os
from contextlib import redirect_stderr
from datetime import date, timedelta

from django.core.exceptions import ValidationError
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import EmailMessage
from django.db.models import Count, Q, Max
from django.http import HttpResponse, FileResponse, JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.text import slugify

from pypdf import PdfWriter
from weasyprint import HTML
from docx import Document
from docx.shared import Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH

from .models import (
    CarreraAcademica,
    Formulario,
    JuntaEvaluadora,
    Cargo,
    Docente,
    Evaluacion,
    PlantillaDocumento,
    MembreteAnual,
)
from .forms import (
    ResolucionForm,
    CarreraAcademicaForm,
    JuntaEvaluadoraForm,
    CargoForm,
    ExpedienteForm,
    EvaluacionForm,
)
from carrera_academica.services.email_service import EmailService
from carrera_academica.services.pdf_service import PDFService
from carrera_academica.services.document_service import DocumentService

logger = logging.getLogger(__name__)



def replace_text_in_doc(doc, replacements):
    """
    Busca y reemplaza texto en párrafos y tablas, conservando el formato.
    `replacements` es un diccionario con {marcador: texto_nuevo}.
    """
    # Recorremos todos los párrafos del cuerpo del documento
    for p in doc.paragraphs:
        for run in p.runs:
            for old_text, new_text in replacements.items():
                if old_text in run.text:
                    run.text = run.text.replace(old_text, new_text)

    # Recorremos todas las tablas del cuerpo del documento
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    for run in p.runs:
                        for old_text, new_text in replacements.items():
                            if old_text in run.text:
                                run.text = run.text.replace(old_text, new_text)


@login_required
def dashboard_ca_view(request):
    # --- Lógica de Filtros y Búsqueda ---
    search_query = request.GET.get("q", "")
    estado_filter = request.GET.get("estado", "")

    # --- Lógica de Formularios Debidos ---
    current_year = timezone.now().year
    # Definimos qué formularios son "debidos" hasta la fecha
    q_formularios_debidos = (
        # Todos los de años anteriores
        Q(formularios__anio_correspondiente__lt=current_year)
        |
        # Solo F04 del año actual
        Q(
            formularios__anio_correspondiente=current_year,
            formularios__tipo_formulario="F04",
        )
        |
        # Formularios sin año (únicos y de evaluación)
        Q(formularios__anio_correspondiente__isnull=True)
    )

    # Query base optimizada con el nuevo cálculo de progreso
    carreras_qs = CarreraAcademica.objects.select_related(
        "cargo__docente", "cargo__asignatura"
    ).annotate(
        # Contamos el total de formularios DEBIDOS
        total_formularios_debidos=Count("formularios", filter=q_formularios_debidos),
        # Contamos los entregados que también son DEBIDOS
        formularios_entregados=Count(
            "formularios", filter=Q(formularios__estado="ENT") & q_formularios_debidos
        ),
    )

    # Aplicamos filtros de búsqueda
    if search_query:
        carreras_qs = carreras_qs.filter(
            Q(cargo__docente__nombre__icontains=search_query)
            | Q(cargo__docente__apellido__icontains=search_query)
        )
    if estado_filter:
        carreras_qs = carreras_qs.filter(estado=estado_filter)

    contexto = {
        "carreras": carreras_qs.order_by("fecha_vencimiento_actual"),
        "search_query": search_query,
        "estado_filter": estado_filter,
        "estado_choices": CarreraAcademica.ESTADO_CHOICES,
    }

    return render(request, "carrera_academica/dashboard_ca.html", contexto)


@login_required
def detalle_ca_view(request, pk):
    ca = get_object_or_404(CarreraAcademica, pk=pk)

    if request.method == "POST":
        formulario_id = request.POST.get("formulario_id")
        archivo = request.FILES.get("archivo")

        if formulario_id and archivo:
            formulario = get_object_or_404(Formulario, pk=formulario_id)
            formulario.archivo = archivo
            formulario.estado = "ENT"  # Entregado
            formulario.fecha_entrega = timezone.now()
            formulario.save()
            messages.success(
                request,
                f"Se subió el archivo para el formulario {formulario.tipo_formulario}.",
            )

        return redirect("detalle_ca", pk=ca.pk)

    # Obtenemos y separamos los formularios para la plantilla
    current_year = timezone.now().year

    formularios_visibles = []
    todos_los_formularios = ca.formularios.all().order_by(
        "anio_correspondiente", "evaluacion__numero_evaluacion", "tipo_formulario"
    )

    for form in todos_los_formularios:
        # Si no es un formulario anual, siempre se muestra
        if not form.anio_correspondiente:
            formularios_visibles.append(form)
            continue

        # Si es anual, aplicamos la regla
        if form.anio_correspondiente < current_year:
            formularios_visibles.append(form)
        elif (
            form.anio_correspondiente == current_year and form.tipo_formulario == "F04"
        ):
            formularios_visibles.append(form)

    # Separamos los formularios visibles para la plantilla
    form_cv = next((f for f in formularios_visibles if f.tipo_formulario == "CV"), None)
    form_unicos = [
        f for f in formularios_visibles if f.tipo_formulario in ["F01", "F02", "F03"]
    ]
    form_anuales = [
        f
        for f in formularios_visibles
        if f.tipo_formulario in ["F04", "F05", "F06", "F07", "ENC", "F13"]
    ]
    form_evaluacion = [
        f
        for f in formularios_visibles
        if f.tipo_formulario in ["F08", "F09", "F10", "F11", "F12"]
    ]

    # Pasamos una instancia vacía del formulario a la plantilla
    form_resolucion = ResolucionForm()

    # Pasamos una instancia del formulario para el expediente
    expediente_form = ExpedienteForm(instance=ca)

    # --- Añadimos el cálculo de años pendientes ---
    start_year = ca.fecha_inicio.year
    end_year = timezone.now().year
    todos_los_anios = set(range(start_year, end_year + 1))
    anios_ya_evaluados = set()
    for ev in ca.evaluaciones.all():
        for anio in ev.anios_evaluados:
            anios_ya_evaluados.add(anio)
    anios_pendientes = sorted(list(todos_los_anios - anios_ya_evaluados))

    # --- Lógica para el botón de notificación ---
    tipos_a_notificar = ["F02", "F04", "F05"]
    hay_formularios_pendientes = ca.formularios.filter(
        estado="PEN", tipo_formulario__in=tipos_a_notificar
    ).exists()

    contexto = {
        "ca": ca,
        "form_cv": form_cv,
        "form_unicos": form_unicos,
        "form_anuales": form_anuales,
        "form_evaluacion": form_evaluacion,
        "form_resolucion": form_resolucion,
        "expediente_form": expediente_form,
        "anios_pendientes_evaluacion": anios_pendientes,
        "hay_formularios_pendientes": hay_formularios_pendientes,
    }
    return render(request, "carrera_academica/detalle_ca.html", contexto)


@login_required
def iniciar_evaluacion_view(request, pk):
    ca = get_object_or_404(CarreraAcademica, pk=pk)

    # Verificar si se puede iniciar evaluación
    puede, razon = ca.puede_iniciar_evaluacion()
    if not puede:
        messages.error(request, f"No se puede iniciar evaluación: {razon}")
        return redirect("detalle_ca", pk=ca.pk)

    # --- Lógica para determinar años pendientes ---
    start_year = ca.fecha_inicio.year
    end_year = timezone.now().year
    todos_los_anios = set(range(start_year, end_year + 1))

    anios_ya_evaluados = set()
    for ev in ca.evaluaciones.all():
        for anio in ev.anios_evaluados:
            anios_ya_evaluados.add(anio)

    anios_pendientes = sorted(list(todos_los_anios - anios_ya_evaluados))

    if request.method == "POST":
        form = EvaluacionForm(request.POST)
        form.fields["anios_a_evaluar"].choices = [
            (y, y) for y in anios_pendientes]

        if form.is_valid():
            try:
                anios_seleccionados = form.cleaned_data["anios_a_evaluar"]

                # Obtener el siguiente número de evaluación
                from django.db.models import Max
                max_eval = ca.evaluaciones.aggregate(
                    max_num=Max("numero_evaluacion"))["max_num"]
                nuevo_num = (max_eval or 0) + 1

                # Crear la nueva evaluación
                nueva_evaluacion = Evaluacion(
                    carrera_academica=ca,
                    numero_evaluacion=nuevo_num,
                    anios_evaluados=[int(a) for a in anios_seleccionados],
                )

                # Validar antes de guardar
                nueva_evaluacion.full_clean()
                nueva_evaluacion.save()

                # Crear los formularios asociados
                for tipo in ["F08", "F09", "F10", "F11", "F12"]:
                    Formulario.objects.create(
                        carrera_academica=ca,
                        tipo_formulario=tipo,
                        evaluacion=nueva_evaluacion,
                    )

                messages.success(
                    request,
                    f"Evaluación N°{nuevo_num} creada, cubriendo los años {', '.join(anios_seleccionados)}.",
                )
                return redirect("detalle_ca", pk=ca.pk)

            except ValidationError as e:
                logger.warning(f"Error de validación al crear evaluación: {e}")
                for error in e.messages:
                    messages.error(request, error)

            except Exception as e:
                logger.error(f"Error inesperado al crear evaluación: {e}")
                messages.error(
                    request, "Error al crear la evaluación. Contacte al administrador.")
    else:
        form = EvaluacionForm()
        form.fields["anios_a_evaluar"].choices = [
            (y, y) for y in anios_pendientes]

    return render(
        request, "carrera_academica/iniciar_evaluacion.html", {
            "form": form, "ca": ca}
    )


@login_required
def registrar_resolucion_view(request, pk):
    ca = get_object_or_404(CarreraAcademica, pk=pk)

    if request.method == "POST":
        form = ResolucionForm(request.POST, request.FILES)
        if form.is_valid():
            nueva_resolucion = form.save(commit=False)
            nueva_resolucion.cargo = ca.cargo
            nueva_resolucion.save()

            # --- Lógica de Negocio (CORREGIDA Y AMPLIADA) ---
            objeto = form.cleaned_data["objeto"]

            # 1. Vinculamos la resolución al expediente si corresponde
            if objeto == "alta" or objeto == "redesignacion":
                ca.resolucion_designacion = nueva_resolucion
                messages.info(
                    request, "La resolución se ha vinculado como 'Designación'."
                )

            elif objeto == "puesta_funcion":
                ca.resolucion_puesta_en_funcion = nueva_resolucion
                messages.info(
                    request, "La resolución se ha vinculado como 'Puesta en Función'."
                )

            # 2. Actualizamos el estado o las fechas de la CA si corresponde
            if objeto == "prorroga_ca":
                dias = form.cleaned_data.get("prorroga_dias", 0)
                if dias > 0:
                    ca.fecha_vencimiento_actual += timedelta(days=dias)
                print(f"Prórroga aplicada: {dias} días.")

            elif objeto == "licencia_alta":
                ca.estado = "STB"  # Standby

            elif objeto == "licencia_baja":
                ca.estado = "ACT"  # Activa

            # Guardamos todos los cambios en la Carrera Académica
            ca.save()

            messages.success(
                request,
                f"Resolución de '{nueva_resolucion.get_objeto_display()}' registrada exitosamente.",
            )
            return redirect("detalle_ca", pk=ca.pk)

    # Si el formulario no es válido o no es POST, redirigimos
    # (podríamos pasar el form con errores, pero por ahora es más simple así)
    return redirect("detalle_ca", pk=ca.pk)


@login_required
def crear_ca_view(request):
    ca_form = CarreraAcademicaForm()
    cargo_form = CargoForm()

    if request.method == "POST":
        if "submit_existente" in request.POST:
            form = CarreraAcademicaForm(request.POST)
            if form.is_valid():
                try:
                    cargo_seleccionado = form.cleaned_data["cargo"]

                    # Crear la CA manualmente con las fechas del cargo
                    nueva_ca = CarreraAcademica(
                        cargo=cargo_seleccionado,
                        numero_expediente=form.cleaned_data["numero_expediente"],
                        fecha_inicio=cargo_seleccionado.fecha_inicio,
                        fecha_vencimiento_original=cargo_seleccionado.fecha_vencimiento,
                    )

                    # Validar antes de guardar
                    nueva_ca.full_clean()
                    nueva_ca.save()

                    messages.success(
                        request,
                        f"Carrera Académica iniciada para el cargo de {cargo_seleccionado}.",
                    )
                    return redirect("dashboard_ca")

                except ValidationError as e:
                    # Manejar errores de validación
                    logger.warning(f"Error de validación al crear CA: {e}")
                    for field, errors in e.message_dict.items():
                        for error in errors:
                            messages.error(request, f"{field}: {error}")
                    ca_form = form

                except Exception as e:
                    logger.error(f"Error inesperado al crear CA: {e}")
                    messages.error(
                        request, "Error al crear la Carrera Académica. Contacte al administrador.")
                    ca_form = form
            else:
                ca_form = form

        elif "submit_nuevo" in request.POST:
            form = CargoForm(request.POST)
            if form.is_valid():
                try:
                    # Crear el nuevo cargo
                    nuevo_cargo = form.save()

                    # Crear la CA asociada
                    nueva_ca = CarreraAcademica(
                        cargo=nuevo_cargo,
                        fecha_inicio=nuevo_cargo.fecha_inicio,
                        fecha_vencimiento_original=nuevo_cargo.fecha_vencimiento,
                    )

                    nueva_ca.full_clean()
                    nueva_ca.save()

                    messages.success(
                        request,
                        f"Nuevo cargo y Carrera Académica creados para {nuevo_cargo.docente}.",
                    )
                    return redirect("dashboard_ca")

                except ValidationError as e:
                    logger.warning(
                        f"Error de validación al crear cargo y CA: {e}")
                    for field, errors in e.message_dict.items():
                        for error in errors:
                            messages.error(request, f"{field}: {error}")
                    cargo_form = form

                except Exception as e:
                    logger.error(f"Error inesperado al crear cargo y CA: {e}")
                    messages.error(
                        request, "Error al crear el cargo. Contacte al administrador.")
                    cargo_form = form
            else:
                cargo_form = form

    contexto = {
        "ca_form": ca_form,
        "cargo_form": cargo_form,
    }
    return render(request, "carrera_academica/crear_ca.html", contexto)


@login_required
def editar_junta_view(request, pk):
    ca = get_object_or_404(CarreraAcademica, pk=pk)

    # Usamos get_or_create para obtener la junta existente o crear una nueva si no existe
    junta, created = JuntaEvaluadora.objects.get_or_create(carrera_academica=ca)

    if request.method == "POST":
        form = JuntaEvaluadoraForm(request.POST, instance=junta)
        if form.is_valid():
            form.save()
            messages.success(
                request, "La Junta Evaluadora ha sido actualizada exitosamente."
            )
            return redirect("detalle_ca", pk=ca.pk)
    else:
        form = JuntaEvaluadoraForm(instance=junta)

    contexto = {
        "form": form,
        "ca": ca,
        "categoria_choices": Cargo.CATEGORIA_CHOICES,
        "dedicacion_choices": Cargo.DEDICACION_CHOICES,
    }
    return render(request, "carrera_academica/editar_junta.html", contexto)


@login_required
def asignar_expediente_view(request, pk):
    ca = get_object_or_404(CarreraAcademica, pk=pk)
    if request.method == "POST":
        # Pasamos la instancia existente para que el formulario la actualice
        form = ExpedienteForm(request.POST, instance=ca)
        if form.is_valid():
            form.save()
            messages.success(request, "Número de expediente actualizado correctamente.")
    # Siempre redirigimos de vuelta al detalle
    return redirect("detalle_ca", pk=ca.pk)


def docentes_filtrados_api_view(request):
    # Empezamos con el queryset base (docentes con cargos regulares u ordinarios)
    queryset = Docente.objects.filter(
        cargo_docente__caracter__in=["ord", "reg"]
    ).distinct()

    # Obtenemos los filtros de la petición GET
    categoria_seleccionada = request.GET.get("categoria")
    dedicacion_seleccionada = request.GET.get("dedicacion")

    # --- Lógica de Filtro Jerárquico para CATEGORÍA ---
    if categoria_seleccionada:
        # 1. Definimos el orden jerárquico
        categorias_orden = ["jtp", "adj", "aso", "tit"]
        try:
            # 2. Encontramos el índice de la categoría seleccionada
            start_index = categorias_orden.index(categoria_seleccionada)
            # 3. Creamos una lista con esa categoría y todas las superiores
            categorias_validas = categorias_orden[start_index:]
            # 4. Usamos el filtro `__in` para buscar en la lista de categorías válidas
            queryset = queryset.filter(cargo_docente__categoria__in=categorias_validas)
        except ValueError:
            pass  # Si la categoría no es válida, no se aplica el filtro

    # --- Lógica de Filtro Jerárquico para DEDICACIÓN ---
    if dedicacion_seleccionada:
        # 1. Definimos el orden jerárquico
        dedicaciones_orden = ["ds", "se", "de"]
        try:
            # 2. Encontramos el índice de la dedicación seleccionada
            start_index = dedicaciones_orden.index(dedicacion_seleccionada)
            # 3. Creamos una lista con esa dedicación y todas las superiores
            dedicaciones_validas = dedicaciones_orden[start_index:]
            # 4. Usamos el filtro `__in`
            queryset = queryset.filter(
                cargo_docente__dedicacion__in=dedicaciones_validas
            )
        except ValueError:
            pass  # Si la dedicación no es válida, no se aplica el filtro

    # Preparamos los datos para la respuesta JSON (sin cambios)
    docentes_list = list(queryset.values("id", "apellido", "nombre"))

    for docente in docentes_list:
        docente["full_name"] = (
            f"{docente['apellido'].upper()}, {docente['nombre'].title()}"
        )

    return JsonResponse({"docentes": docentes_list})


@login_required
def finalizar_ca_view(request, pk):
    # Usamos POST para asegurarnos de que la acción sea intencional
    if request.method == "POST":
        ca = get_object_or_404(CarreraAcademica, pk=pk)
        ca.estado = "FIN"  # 'Finalizada'
        ca.fecha_finalizacion = timezone.now()
        ca.save()
        messages.success(
            request,
            f"El expediente de {ca.cargo.docente} ha sido marcado como 'Finalizado'.",
        )

    # Redirigimos siempre al detalle del expediente
    return redirect("detalle_ca", pk=pk)


@login_required
def consolidar_pdf_view(request, pk):
    """Vista para consolidar expediente en PDF."""
    ca = get_object_or_404(CarreraAcademica, pk=pk)

    output_buffer, errores = PDFService.consolidar_expediente(ca)

    if not output_buffer:
        messages.error(request, "No se pudo generar el PDF consolidado")
        return redirect("detalle_ca", pk=ca.pk)

    for error in errores:
        messages.warning(request, error)

    response = HttpResponse(output_buffer, content_type="application/pdf")
    response["Content-Disposition"] = (
        f'attachment; filename="expediente_{slugify(ca.cargo.docente)}.pdf"'
    )
    return response


@login_required
def generar_propuesta_jurado_view(request, pk):
    """Vista para generar PDF de propuesta de jurado."""
    ca = get_object_or_404(CarreraAcademica, pk=pk)

    signature_path = "/static/images/firma_holografica.png"
    pdf_file = PDFService.generar_propuesta_jurado(ca, signature_path)

    if not pdf_file:
        messages.error(request, "No se pudo generar la propuesta de jurado")
        return redirect("detalle_ca", pk=ca.pk)

    response = HttpResponse(pdf_file, content_type="application/pdf")
    response["Content-Disposition"] = (
        f'attachment; filename="propuesta_jurado_{slugify(ca.cargo.docente)}.pdf"'
    )
    return response


@login_required
def notificar_pendientes_view(request, pk):
    """Vista para notificar formularios pendientes."""
    ca = get_object_or_404(CarreraAcademica, pk=pk)

    exito, mensaje = EmailService.enviar_recordatorio_formularios_pendientes(
        ca)

    if exito:
        messages.success(request, mensaje)
    else:
        messages.error(request, mensaje)

    return redirect("detalle_ca", pk=ca.pk)


@login_required
def descargar_plantilla_view(request, pk):
    """Vista para descargar plantilla de formulario."""
    formulario = get_object_or_404(Formulario, pk=pk)
    tipos_dinamicos = ["F06", "F07", "F13", "ENC", "F04", "F05"]

    if formulario.tipo_formulario in tipos_dinamicos:
        buffer, filename = DocumentService.generar_documento_dinamico(
            formulario)

        if buffer:
            return FileResponse(buffer, as_attachment=True, filename=filename)
        else:
            messages.error(
                request,
                "No se pudo generar el documento. Verifique plantillas y membretes."
            )
            return redirect("detalle_ca", pk=formulario.carrera_academica.pk)
    else:
        # Lógica para plantillas estáticas
        plantilla = PlantillaDocumento.objects.filter(
            tipo_formulario=formulario.tipo_formulario
        ).first()

        if plantilla and plantilla.archivo:
            return FileResponse(
                plantilla.archivo.open("rb"),
                as_attachment=True,
                filename=plantilla.archivo.name,
            )
        else:
            messages.error(
                request,
                f"No se encontró plantilla para {formulario.tipo_formulario}."
            )
            return redirect("detalle_ca", pk=formulario.carrera_academica.pk)


@login_required
def notificar_junta_view(request, pk):
    """Vista para notificar a la junta evaluadora."""
    evaluacion = get_object_or_404(Evaluacion, pk=pk)
    ca = evaluacion.carrera_academica

    emails_enviados, errores = EmailService.enviar_notificacion_junta(
        evaluacion)

    if emails_enviados > 0:
        messages.success(
            request,
            f"Se han enviado {emails_enviados} correos a los miembros de la junta."
        )

    for error in errores:
        messages.warning(request, error)

    return redirect("detalle_ca", pk=ca.pk)


@login_required
def agendar_evaluacion_view(request, pk):
    # El 'pk' que recibimos es el de la Evaluación
    evaluacion = get_object_or_404(Evaluacion, pk=pk)

    # Esta acción solo debe ocurrir si se envía el formulario
    if request.method == "POST":
        # Obtenemos el valor del campo 'fecha_evaluacion' del formulario
        fecha_str = request.POST.get("fecha_evaluacion")

        if fecha_str:
            # Si se proporcionó una fecha, la guardamos en el objeto Evaluacion
            evaluacion.fecha_evaluacion = fecha_str
            evaluacion.save()
            messages.success(
                request,
                f"Se agendó la fecha para la Evaluación N°{evaluacion.numero_evaluacion}.",
            )
        else:
            # Si se envía el campo vacío, borramos la fecha
            evaluacion.fecha_evaluacion = None
            evaluacion.save()
            messages.info(
                request,
                f"Se ha quitado la fecha para la Evaluación N°{evaluacion.numero_evaluacion}.",
            )

    # Sin importar qué pase, siempre redirigimos de vuelta a la página del expediente
    return redirect("detalle_ca", pk=evaluacion.carrera_academica.pk)
