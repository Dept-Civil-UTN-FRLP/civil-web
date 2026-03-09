# carrera_academica/views.py
import io
import logging
import os
from contextlib import redirect_stderr
from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.mail import EmailMessage
from django.db.models import Count, Max, Q
from django.http import FileResponse, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.text import slugify
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches
from pypdf import PdfWriter
from weasyprint import HTML

from carrera_academica.services.document_service import DocumentService
from carrera_academica.services.email_service import EmailService
from carrera_academica.services.pdf_service import PDFService
from config.pagination import paginate_queryset

from .forms import (
    CargoForm,
    CarreraAcademicaForm,
    EvaluacionForm,
    ExpedienteForm,
    JuntaEvaluadoraForm,
    ResolucionForm,
)
from .models import (
    Cargo,
    CarreraAcademica,
    Docente,
    Evaluacion,
    Formulario,
    JuntaEvaluadora,
    MembreteAnual,
    PlantillaDocumento,
)

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
    """Dashboard optimizado de Carrera Académica."""
    # Lógica de Filtros y Búsqueda
    search_query = request.GET.get("q", "")
    estado_filter = request.GET.get("estado", "")

    # Lógica de Formularios Debidos
    current_year = timezone.now().year
    q_formularios_debidos = (
        Q(formularios__anio_correspondiente__lt=current_year)
        | Q(
            formularios__anio_correspondiente=current_year,
            formularios__tipo_formulario="F04",
        )
        | Q(formularios__anio_correspondiente__isnull=True)
    )

    # OPTIMIZACIÓN: Usar el manager personalizado
    carreras_qs = CarreraAcademica.objects.with_related_data().annotate(
        total_formularios_debidos=Count("formularios", filter=q_formularios_debidos),
        formularios_entregados=Count(
            "formularios", filter=Q(formularios__estado="ENT") & q_formularios_debidos
        ),
    )

    # Aplicar filtros
    if search_query:
        carreras_qs = carreras_qs.filter(
            Q(cargo__docente__nombre__icontains=search_query)
            | Q(cargo__docente__apellido__icontains=search_query)
        )
    if estado_filter:
        carreras_qs = carreras_qs.filter(estado=estado_filter)

    # Ordenar
    carreras_qs = carreras_qs.order_by("fecha_vencimiento_actual")

    # ✅ PAGINACIÓN: Aplicar paginación
    page_obj, pagination_context = paginate_queryset(carreras_qs, request, page_size=25)

    # OPTIMIZACIÓN: Ordenar sin queries adicionales
    contexto = {
        "carreras": page_obj,
        "search_query": search_query,
        "estado_filter": estado_filter,
        "estado_choices": CarreraAcademica.ESTADO_CHOICES,
        **pagination_context,
    }

    return render(request, "carrera_academica/dashboard_ca.html", contexto)


@login_required
def detalle_ca_view(request, pk):
    """Vista de detalle optimizada."""
    # ✅ OPTIMIZACIÓN: Usar with_full_detail()
    ca = get_object_or_404(CarreraAcademica.objects.with_full_detail(), pk=pk)

    if request.method == "POST":
        formulario_id = request.POST.get("formulario_id")
        archivo = request.FILES.get("archivo")

        if formulario_id and archivo:
            # ✅ OPTIMIZACIÓN: No hacer query adicional, ya lo tenemos
            formulario = ca.formularios.get(pk=formulario_id)
            formulario.archivo = archivo
            formulario.estado = "ENT"
            formulario.fecha_entrega = timezone.now()
            formulario.save()
            messages.success(
                request,
                f"Se subió el archivo para el formulario {formulario.tipo_formulario}.",
            )

        return redirect("carrera_academica:detalle_ca", pk=ca.pk)

    # Obtener y separar los formularios
    current_year = timezone.now().year
    formularios_visibles = []

    todos_los_formularios = ca.formularios.all().order_by(
        "anio_correspondiente", "evaluacion__numero_evaluacion", "tipo_formulario"
    )

    for form in todos_los_formularios:
        if not form.anio_correspondiente:
            formularios_visibles.append(form)
            continue

        if form.anio_correspondiente < current_year:
            formularios_visibles.append(form)
        elif (
            form.anio_correspondiente == current_year and form.tipo_formulario == "F04"
        ):
            formularios_visibles.append(form)

    # Separar formularios para la plantilla
    form_cv = next((f for f in formularios_visibles if f.tipo_formulario == "CV"), None)
    form_unicos = [
        f for f in formularios_visibles if f.tipo_formulario in ["F01", "F02", "F03"]
    ]
    form_anuales = [
        f
        for f in formularios_visibles
        if f.tipo_formulario in ["F04", "F05", "F06", "F07", "ENC", "F13"]
    ]

    form_resolucion = ResolucionForm()
    expediente_form = ExpedienteForm(instance=ca)

    # Calcular años pendientes de evaluación
    start_year = ca.fecha_inicio.year
    end_year = timezone.now().year
    todos_los_anios = set(range(start_year, end_year + 1))

    anios_ya_evaluados = set()
    # OPTIMIZACIÓN: Las evaluaciones ya están precargadas
    for ev in ca.evaluaciones.all():
        for anio in ev.anios_evaluados:
            anios_ya_evaluados.add(anio)

    anios_pausados = {item['anio'] for item in ca.anios_pausados}
    
    anios_pendientes = sorted(list(todos_los_anios - anios_ya_evaluados - anios_pausados))

    # Obtener resumen de años con formularios
    resumen_anios = ca.get_resumen_anios()

    # Asociar formularios a cada año
    form_anuales = ca.formularios.filter(anio_correspondiente__isnull=False).order_by(
        'anio_correspondiente', 'tipo_formulario')

    # Agrupar formularios por año
    formularios_por_anio = {}
    for form in form_anuales:
        anio = form.anio_correspondiente
        if anio not in formularios_por_anio:
            formularios_por_anio[anio] = []
        formularios_por_anio[anio].append(form)

    # Agregar formularios al resumen
    for item in resumen_anios:
        item['formularios'] = formularios_por_anio.get(item['anio'], [])

    # Lógica para el botón de notificación
    tipos_a_notificar = ["F02", "F04", "F05"]
    hay_formularios_pendientes = any(
        f.estado == "PEN" and f.tipo_formulario in tipos_a_notificar
        for f in ca.formularios.all()
    )

    contexto = {
        "ca": ca,
        "form_cv": form_cv,
        "form_unicos": form_unicos,
        "form_anuales": form_anuales,
        "form_resolucion": form_resolucion,
        "expediente_form": expediente_form,
        "anios_pendientes_evaluacion": anios_pendientes,
        "hay_formularios_pendientes": hay_formularios_pendientes,
        'resumen_anios': resumen_anios,
    }
    return render(request, "carrera_academica/ca_detail.html", contexto)


@login_required
def iniciar_evaluacion_view(request, pk):
    ca = get_object_or_404(CarreraAcademica, pk=pk)

    # Verificar si se puede iniciar evaluación
    puede, razon = ca.puede_iniciar_evaluacion()
    if not puede:
        messages.error(request, f"No se puede iniciar evaluación: {razon}")
        return redirect("carrera_academica:detalle_ca", pk=ca.pk)

    # --- Lógica para determinar años pendientes ---
    start_year = ca.fecha_inicio.year
    end_year = timezone.now().year
    todos_los_anios = set(range(start_year, end_year + 1))

    anios_ya_evaluados = set()
    for ev in ca.evaluaciones.all():
        for anio in ev.anios_evaluados:
            anios_ya_evaluados.add(anio)
    
    anios_pausados = {item['anio'] for item in ca.anios_pausados}

    anios_pendientes = sorted(
        list(todos_los_anios - anios_ya_evaluados - anios_pausados))

    if request.method == "POST":
        form = EvaluacionForm(request.POST)
        form.fields["anios_a_evaluar"].choices = [(y, y) for y in anios_pendientes]

        if form.is_valid():
            try:
                anios_seleccionados = form.cleaned_data["anios_a_evaluar"]

                # Obtener el siguiente número de evaluación
                from django.db.models import Max

                max_eval = ca.evaluaciones.aggregate(max_num=Max("numero_evaluacion"))[
                    "max_num"
                ]
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
                return redirect("carrera_academica:detalle_ca", pk=ca.pk)

            except ValidationError as e:
                logger.warning(f"Error de validación al crear evaluación: {e}")
                for error in e.messages:
                    messages.error(request, error)

            except Exception as e:
                logger.error(f"Error inesperado al crear evaluación: {e}")
                messages.error(
                    request, "Error al crear la evaluación. Contacte al administrador."
                )
    else:
        form = EvaluacionForm()
        form.fields["anios_a_evaluar"].choices = [(y, y) for y in anios_pendientes]

    return render(
        request, "carrera_academica/evaluacion_create.html", {"form": form, "ca": ca}
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
                    anios_nuevos, forms_creados, mensaje = ca.agregar_anios_por_prorroga(
                        ca.fecha_vencimiento_actual
                    )
                    if anios_nuevos:
                        messages.success(
                            request,
                            f"Prórroga aplicada: {dias} días. {mensaje}"
                        )
                    else:
                        messages.info(
                            request,
                            f"Prórroga aplicada: {dias} días (sin años nuevos completos)."
                        )
                

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
            return redirect("carrera_academica:detalle_ca", pk=ca.pk)

    # Si el formulario no es válido o no es POST, redirigimos
    # (podríamos pasar el form con errores, pero por ahora es más simple así)
    return redirect("carrera_academica:detalle_ca", pk=ca.pk)


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
                    return redirect("carrera_academica:dashboard_ca")

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
                        request,
                        "Error al crear la Carrera Académica. Contacte al administrador.",
                    )
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
                    return redirect("carrera_academica:dashboard_ca")

                except ValidationError as e:
                    logger.warning(f"Error de validación al crear cargo y CA: {e}")
                    for field, errors in e.message_dict.items():
                        for error in errors:
                            messages.error(request, f"{field}: {error}")
                    cargo_form = form

                except Exception as e:
                    logger.error(f"Error inesperado al crear cargo y CA: {e}")
                    messages.error(
                        request, "Error al crear el cargo. Contacte al administrador."
                    )
                    cargo_form = form
            else:
                cargo_form = form

    contexto = {
        "ca_form": ca_form,
        "cargo_form": cargo_form,
    }
    return render(request, "carrera_academica/ca_create.html", contexto)


@login_required
def editar_junta_view(request, pk):
    """Vista optimizada para editar junta."""
    # ✅ OPTIMIZACIÓN: Precargar relaciones necesarias
    ca = get_object_or_404(
        CarreraAcademica.objects.select_related("cargo__docente", "cargo__asignatura"),
        pk=pk,
    )

    junta, created = JuntaEvaluadora.objects.get_or_create(carrera_academica=ca)

    if request.method == "POST":
        form = JuntaEvaluadoraForm(request.POST, instance=junta)
        if form.is_valid():
            form.save()
            messages.success(
                request, "La Junta Evaluadora ha sido actualizada exitosamente."
            )
            return redirect("carrera_academica:detalle_ca", pk=ca.pk)
    else:
        form = JuntaEvaluadoraForm(instance=junta)

    contexto = {
        "form": form,
        "ca": ca,
        "categoria_choices": Cargo.CATEGORIA_CHOICES,
        "dedicacion_choices": Cargo.DEDICACION_CHOICES,
    }
    return render(request, "carrera_academica/junta_update.html", contexto)


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
    return redirect("carrera_academica:detalle_ca", pk=ca.pk)


def docentes_filtrados_api_view(request):
    """API optimizada para filtrar docentes."""
    # ✅ OPTIMIZACIÓN: select_related para evitar queries adicionales
    queryset = (
        Docente.objects.filter(cargo_docente__caracter__in=["ord", "reg"])
        .select_related()
        .distinct()
    )

    categoria_seleccionada = request.GET.get("categoria")
    dedicacion_seleccionada = request.GET.get("dedicacion")

    # Lógica de Filtro Jerárquico para CATEGORÍA
    if categoria_seleccionada:
        categorias_orden = ["jtp", "adj", "aso", "tit"]
        try:
            start_index = categorias_orden.index(categoria_seleccionada)
            categorias_validas = categorias_orden[start_index:]
            queryset = queryset.filter(cargo_docente__categoria__in=categorias_validas)
        except ValueError:
            pass

    # Lógica de Filtro Jerárquico para DEDICACIÓN
    if dedicacion_seleccionada:
        dedicaciones_orden = ["ds", "se", "de"]
        try:
            start_index = dedicaciones_orden.index(dedicacion_seleccionada)
            dedicaciones_validas = dedicaciones_orden[start_index:]
            queryset = queryset.filter(
                cargo_docente__dedicacion__in=dedicaciones_validas
            )
        except ValueError:
            pass

    # ✅ OPTIMIZACIÓN: only() para traer solo los campos necesarios
    docentes_list = list(
        queryset.only("id", "apellido", "nombre").values("id", "apellido", "nombre")
    )

    for docente in docentes_list:
        docente["full_name"] = (
            f"{docente['apellido'].upper()}, {docente['nombre'].title()}"
        )

    return JsonResponse({"docentes": docentes_list})


@login_required
def finalizar_ca_view(request, pk):
    """
    Finaliza la CA con workflow automático según el resultado.
    """
    from django.db import transaction

    ca = get_object_or_404(CarreraAcademica, pk=pk)

    if request.method == "POST":
        resultado = request.POST.get('resultado_cierre')
        observaciones = request.POST.get('observaciones_cierre', '')

        if not resultado:
            messages.error(request, 'Debe seleccionar un resultado de cierre')
            return redirect('carrera_academica:detalle_ca', pk=pk)

        # Validaciones específicas por resultado
        if resultado == 'aprobada_redesigna':
            nueva_fecha_vencimiento_str = request.POST.get(
                'nueva_fecha_vencimiento')
            if not nueva_fecha_vencimiento_str:
                messages.error(
                    request, 'Debe especificar la nueva fecha de vencimiento para la redesignación')
                return redirect('carrera_academica:finalizar_ca', pk=pk)

            from datetime import datetime
            nueva_fecha_vencimiento = datetime.strptime(
                nueva_fecha_vencimiento_str, '%Y-%m-%d').date()

        # ✅ Usar transacción atómica para evitar inconsistencias
        try:
            with transaction.atomic():
                # Actualizar CA actual
                ca.estado = "FIN"
                ca.fecha_finalizacion = timezone.now()
                ca.resultado_cierre = resultado
                ca.observaciones_cierre = observaciones
                ca.save()

                cargo_actual = ca.cargo

                if resultado == 'aprobada_redesigna':
                    # Crear nuevo cargo
                    nuevo_cargo = Cargo.objects.create(
                        docente=cargo_actual.docente,
                        asignatura=cargo_actual.asignatura,
                        categoria=cargo_actual.categoria,
                        dedicacion=cargo_actual.dedicacion,
                        caracter=cargo_actual.caracter,
                        cantidad_horas=cargo_actual.cantidad_horas,
                        cantidad_comisiones=cargo_actual.cantidad_comisiones,
                        fecha_inicio=timezone.now().date(),
                        fecha_vencimiento=nueva_fecha_vencimiento,
                        estado='activo',
                        estado_continuidad='activo'
                    )

                    # Vincular continuidad de cargos
                    exito, mensaje = cargo_actual.finalizar_con_continuidad(
                        cargo_siguiente=nuevo_cargo,
                        tipo_continuidad='mismo_cargo',
                        observaciones=f'Redesignación por aprobación de CA. {observaciones}',
                        usuario=request.user
                    )

                    if not exito:
                        raise Exception(
                            f"Error al vincular continuidad de cargos: {mensaje}")

                    # Crear nueva CA y vincular con la anterior
                    nueva_ca = CarreraAcademica.objects.create(
                        cargo=nuevo_cargo,
                        fecha_inicio=nuevo_cargo.fecha_inicio,
                        fecha_vencimiento_original=nueva_fecha_vencimiento,
                        fecha_vencimiento_actual=nueva_fecha_vencimiento,
                        estado='ACT',
                        ca_anterior=ca  # ✅ Vincular con CA anterior
                    )

                    messages.success(
                        request,
                        f"CA Aprobada y redesignada. Nuevo expediente #{nueva_ca.pk} creado con vencimiento {nueva_fecha_vencimiento.strftime('%d/%m/%Y')}."
                    )

                    # Redirigir a la nueva CA
                    return redirect('carrera_academica:detalle_ca', pk=nueva_ca.pk)

                elif resultado == 'aprobada_rechaza':
                    # Convertir a interino
                    cargo_actual.caracter = 'int'
                    cargo_actual.save()
                    messages.warning(
                        request,
                        f"CA Aprobada pero rechaza redesignación. Cargo convertido a Interino."
                    )

                elif resultado == 'renuncia':
                    # Dar de baja el cargo
                    exito, mensaje = cargo_actual.finalizar_sin_continuidad(
                        razon='renuncia',
                        observaciones=observaciones,
                        usuario=request.user
                    )
                    messages.info(
                        request,
                        f"Docente {cargo_actual.docente} renunció. Cargo dado de baja."
                    )

                elif resultado == 'no_aprobada':
                    # Convertir a interino
                    cargo_actual.caracter = 'int'
                    cargo_actual.save()
                    messages.warning(
                        request,
                        f"CA No Aprobada. Cargo convertido a Interino."
                    )

                elif resultado == 'jubilacion':
                    # Dar de baja cargo y marcar docente como jubilado
                    exito, mensaje = cargo_actual.finalizar_sin_continuidad(
                        razon='jubilacion',
                        observaciones=observaciones,
                        usuario=request.user
                    )

                    docente = cargo_actual.docente
                    docente.jubilado = True
                    docente.fecha_jubilacion = timezone.now().date()
                    docente.save()

                    messages.info(
                        request,
                        f"Docente {docente} jubilado. Cargo dado de baja."
                    )

                messages.success(
                    request,
                    f"Expediente de {ca.cargo.docente} finalizado como '{ca.get_resultado_cierre_display()}'."
                )

        except Exception as e:
            messages.error(request, f'Error al finalizar CA: {str(e)}')
            return redirect('carrera_academica:finalizar_ca', pk=pk)

        return redirect('carrera_academica:detalle_ca', pk=pk)

    # GET - Mostrar formulario de cierre
    context = {
        'ca': ca,
        'resultado_choices': CarreraAcademica.RESULTADO_CIERRE_CHOICES,
    }
    return render(request, 'carrera_academica/finalizar_ca.html', context)


@login_required
def consolidar_pdf_view(request, pk):
    """Vista para consolidar expediente en PDF."""
    ca = get_object_or_404(CarreraAcademica, pk=pk)

    output_buffer, errores = PDFService.consolidar_expediente(ca)

    if not output_buffer:
        messages.error(request, "No se pudo generar el PDF consolidado")
        return redirect("carrera_academica:detalle_ca", pk=ca.pk)

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
        return redirect("carrera_academica:detalle_ca", pk=ca.pk)

    response = HttpResponse(pdf_file, content_type="application/pdf")
    response["Content-Disposition"] = (
        f'attachment; filename="propuesta_jurado_{slugify(ca.cargo.docente)}.pdf"'
    )
    return response


@login_required
def notificar_pendientes_view(request, pk):
    """Vista para notificar formularios pendientes."""
    ca = get_object_or_404(CarreraAcademica, pk=pk)

    exito, mensaje = EmailService.enviar_recordatorio_formularios_pendientes(ca)

    if exito:
        messages.success(request, mensaje)
    else:
        messages.error(request, mensaje)

    return redirect("carrera_academica:detalle_ca", pk=ca.pk)


@login_required
def descargar_plantilla_view(request, pk):
    """Vista para descargar plantilla de formulario."""
    formulario = get_object_or_404(Formulario, pk=pk)
    tipos_dinamicos = ["F06", "F07", "F13", "ENC", "F04", "F05"]

    if formulario.tipo_formulario in tipos_dinamicos:
        buffer, filename = DocumentService.generar_documento_dinamico(formulario)

        if buffer:
            return FileResponse(buffer, as_attachment=True, filename=filename)
        else:
            messages.error(
                request,
                "No se pudo generar el documento. Verifique plantillas y membretes.",
            )
            return redirect("carrera_academica:detalle_ca", pk=formulario.carrera_academica.pk)
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
                request, f"No se encontró plantilla para {formulario.tipo_formulario}."
            )
            return redirect("carrera_academica:detalle_ca", pk=formulario.carrera_academica.pk)


@login_required
def notificar_junta_view(request, pk):
    """Vista para notificar a la junta evaluadora."""
    evaluacion = get_object_or_404(Evaluacion, pk=pk)
    ca = evaluacion.carrera_academica

    emails_enviados, errores = EmailService.enviar_notificacion_junta(evaluacion)

    if emails_enviados > 0:
        messages.success(
            request,
            f"Se han enviado {emails_enviados} correos a los miembros de la junta.",
        )

    for error in errores:
        messages.warning(request, error)

    return redirect("carrera_academica:detalle_ca", pk=ca.pk)


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
    return redirect("carrera_academica:detalle_ca", pk=evaluacion.carrera_academica.pk)


@login_required
def gestionar_anios_ca_view(request, pk):
    """
    Vista unificada para:
    - Ver estado de años (pendiente/pausado/evaluado)
    - Pausar/Reactivar años
    - Agregar años nuevos al expediente
    """
    ca = get_object_or_404(CarreraAcademica, pk=pk)

    if request.method == 'POST':
        accion = request.POST.get('accion')

        # ===== PAUSAR AÑO =====
        if accion == 'pausar':
            anio = int(request.POST.get('anio'))
            motivo = request.POST.get('motivo', '').strip()

            if not motivo:
                messages.error(
                    request, "Debe proporcionar un motivo para pausar el año")
                return redirect('carrera_academica:gestionar_anios_ca', pk=pk)

            exito, mensaje = ca.pausar_anio(
                anio, motivo, request.user.username)

            if exito:
                messages.success(request, mensaje)
            else:
                messages.error(request, mensaje)

        # ===== REACTIVAR AÑO =====
        elif accion == 'reactivar':
            anio = int(request.POST.get('anio'))
            exito, mensaje = ca.reactivar_anio(anio)

            if exito:
                messages.success(request, mensaje)
            else:
                messages.error(request, mensaje)

        # ===== AGREGAR AÑOS NUEVOS =====
        elif accion == 'agregar_anios':
            anios_seleccionados = request.POST.getlist('anios')

            if not anios_seleccionados:
                messages.error(request, "Debe seleccionar al menos un año")
                return redirect('carrera_academica:gestionar_anios_ca', pk=pk)

            total_formularios = 0
            anios_agregados = []

            for anio_str in anios_seleccionados:
                anio = int(anio_str)
                creados, mensaje = ca.agregar_formularios_para_anio(anio)
                total_formularios += creados
                anios_agregados.append(anio)

            messages.success(
                request,
                f"Se agregaron {len(anios_agregados)} año(s) con {total_formularios} formularios"
            )

        return redirect('carrera_academica:gestionar_anios_ca', pk=pk)

    # ===== GET: Preparar contexto =====
    resumen = ca.get_resumen_anios()

    # Calcular años disponibles para agregar
    start_year = ca.fecha_inicio.year
    current_year = timezone.now().year
    max_year = current_year + 5  # Permitir agregar hasta 5 años adelante

    # Años que ya tienen formularios o están en el resumen
    anios_existentes = {item['anio'] for item in resumen}

    # Años disponibles = todos - los que ya existen
    anios_disponibles = []
    for anio in range(start_year, max_year + 1):
        if anio not in anios_existentes:
            anios_disponibles.append({
                'anio': anio,
                'es_actual': anio == current_year,
                'es_pasado': anio < current_year,
                'es_futuro': anio > current_year,
            })

    context = {
        'ca': ca,
        'resumen': resumen,
        'anios_disponibles': anios_disponibles,
        'anio_actual': current_year,
        'tiene_anios_disponibles': len(anios_disponibles) > 0,
    }

    return render(request, 'carrera_academica/gestionar_anios.html', context)


@login_required
def gestionar_formularios_anio_view(request, pk, anio):
    """
    Vista para gestionar formularios de un año específico.
    Permite agregar formularios a años nuevos.
    """
    ca = get_object_or_404(CarreraAcademica, pk=pk)

    # Verificar que el año esté en rango
    start_year = ca.fecha_inicio.year
    current_year = timezone.now().year

    if not (start_year <= anio <= current_year):
        messages.error(request, f"El año {anio} está fuera del rango de la CA")
        return redirect('carrera_academica:detalle_ca', pk=pk)

    if request.method == 'POST':
        # Crear formularios faltantes para este año
        tipos_seleccionados = request.POST.getlist('tipos_formularios')

        for tipo in tipos_seleccionados:
            # Verificar que no exista ya
            existe = Formulario.objects.filter(
                carrera_academica=ca,
                tipo_formulario=tipo,
                anio_correspondiente=anio
            ).exists()

            if not existe:
                Formulario.objects.create(
                    carrera_academica=ca,
                    tipo_formulario=tipo,
                    anio_correspondiente=anio
                )

        messages.success(request, f"Formularios agregados para el año {anio}")
        return redirect('carrera_academica:gestionar_formularios_anio', pk=pk, anio=anio)

    # GET - Obtener formularios existentes para este año
    formularios_anio = ca.formularios.filter(
        anio_correspondiente=anio
    ).order_by('tipo_formulario')

    # Tipos de formularios anuales
    tipos_anuales = ['F04', 'F05', 'F06', 'F07', 'F13', 'ENC']

    # Verificar cuáles faltan
    tipos_existentes = set(f.tipo_formulario for f in formularios_anio)
    tipos_faltantes = [t for t in tipos_anuales if t not in tipos_existentes]

    context = {
        'ca': ca,
        'anio': anio,
        'formularios': formularios_anio,
        'tipos_faltantes': tipos_faltantes,
    }

    return render(request, 'carrera_academica/gestionar_formularios_anio.html', context)

@login_required
def archivar_ca_view(request, pk):
    """
    Archiva una CA sin workflow formal de cierre.
    Para casos como jubilación cercana o renuncia condicional.
    El cargo se gestiona cuando la CA efectivamente venza.
    """
    from django.db import transaction
    
    ca = get_object_or_404(CarreraAcademica, pk=pk)
    
    # Solo se pueden archivar CAs activas o vencidas
    if ca.estado not in ['ACT', 'VEN']:
        messages.error(request, 'Solo se pueden archivar CAs activas o vencidas')
        return redirect('carrera_academica:detalle_ca', pk=pk)
    
    if request.method == "POST":
        motivo = request.POST.get('motivo_archivo')
        observaciones = request.POST.get('observaciones_archivo', '')
        
        if not motivo:
            messages.error(request, 'Debe seleccionar un motivo de archivo')
            return redirect('carrera_academica:archivar_ca', pk=pk)
        
        try:
            with transaction.atomic():
                # Archivar CA
                ca.estado = "ARCH"
                ca.motivo_archivo = motivo
                ca.observaciones_archivo = observaciones
                ca.fecha_archivo = timezone.now()
                ca.save()
                
                messages.success(
                    request,
                    f"CA archivada: {ca.get_motivo_archivo_display()}. "
                    f"El cargo se gestionará cuando la CA venza el {ca.fecha_vencimiento_actual.strftime('%d/%m/%Y')}."
                )
        
        except Exception as e:
            messages.error(request, f'Error al archivar CA: {str(e)}')
            return redirect('carrera_academica:archivar_ca', pk=pk)
        
        return redirect('carrera_academica:detalle_ca', pk=pk)
    
    # GET - Mostrar formulario
    context = {
        'ca': ca,
        'motivo_choices': CarreraAcademica.MOTIVO_ARCHIVO_CHOICES,
    }
    return render(request, 'carrera_academica/archivar_ca.html', context)
