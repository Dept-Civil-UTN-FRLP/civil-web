# carrera_academica/views.py
import io
import os
from contextlib import redirect_stderr
from datetime import date, timedelta

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


def _generar_documento_dinamico(formulario):
    """
    Recibe un objeto Formulario y devuelve un documento de Word personalizado
    en un buffer de memoria, junto con un nombre de archivo sugerido.
    Devuelve (None, None) si no se puede generar.
    """
    ca = formulario.carrera_academica
    plantilla_maestra = PlantillaDocumento.objects.filter(
        tipo_formulario=formulario.tipo_formulario
    ).first()
    membrete = MembreteAnual.objects.filter(
        anio=formulario.anio_correspondiente
    ).first()

    if not (plantilla_maestra and membrete):
        return None, None  # No se puede generar si falta la plantilla o el membrete

    try:
        doc = Document(plantilla_maestra.archivo.path)

        # Reemplazar datos del cuerpo
        contexto_remplazo = {
            "[DOCENTE_NOMBRE]": str(ca.cargo.docente),
            "[ASIGNATURA]": ca.cargo.asignatura.nombre.title(),
            "[CARGO]": f"{ca.cargo.get_categoria_display()} {ca.cargo.get_caracter_display()}",
            "[ANIO_LECTIVO]": str(formulario.anio_correspondiente),
            "[FECHA_GENERACION]": date.today().strftime("%d/%m/%Y"),
            "[DEDICACION]": ca.cargo.get_dedicacion_display(),
            "[COMISIONES]": "....................",  # Dejamos un espacio para completar a mano
        }
        replace_text_in_doc(doc, contexto_remplazo)

        # Reemplazar datos del encabezado
        header = doc.sections[0].header
        if header.tables:  # Verificamos que exista una tabla en el encabezado
            table = header.tables[0]

            # Celda izquierda para el logo (columna 0)
            cell_logo = table.cell(0, 0)
            for p in cell_logo.paragraphs:
                if "[LOGO_ANUAL]" in p.text:
                    p.text = ""  # Borramos el marcador
                    # Añadimos la imagen en esa misma posición
                    p.add_run().add_picture(membrete.logo.path, height=Inches(1.5))

            # Celda derecha para la frase (columna 1)
            cell_frase = table.cell(0, 1)
            for p in cell_frase.paragraphs:
                if "[FRASE_ANUAL]" in p.text:
                    p.text = p.text.replace("[FRASE_ANUAL]", membrete.frase)
                    # Nos aseguramos de que la alineación del párrafo sea a la derecha
                    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT

        # Guardar en memoria
        buffer = io.BytesIO()
        doc.save(buffer)
        buffer.seek(0)

        filename = f"{formulario.tipo_formulario}_{formulario.anio_correspondiente}_{slugify(ca.cargo.docente)}.docx"

        return buffer, filename
    except Exception:
        return None, None


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

    # --- Lógica para determinar años pendientes ---
    start_year = ca.fecha_inicio.year
    end_year = timezone.now().year  # Evaluamos hasta el año actual
    todos_los_anios = set(range(start_year, end_year + 1))

    anios_ya_evaluados = set()
    for ev in ca.evaluaciones.all():
        for anio in ev.anios_evaluados:
            anios_ya_evaluados.add(anio)

    anios_pendientes = sorted(list(todos_los_anios - anios_ya_evaluados))

    # --- Lógica del Formulario ---
    if request.method == "POST":
        form = EvaluacionForm(request.POST)
        # Volvemos a definir las opciones para la validación
        form.fields["anios_a_evaluar"].choices = [(y, y) for y in anios_pendientes]

        if form.is_valid():
            anios_seleccionados = form.cleaned_data["anios_a_evaluar"]

            # Creamos la nueva evaluación
            max_eval = ca.evaluaciones.aggregate(max_num=Max("numero_evaluacion"))[
                "max_num"
            ]
            nuevo_num = (max_eval or 0) + 1

            nueva_evaluacion = Evaluacion.objects.create(
                carrera_academica=ca,
                numero_evaluacion=nuevo_num,
                anios_evaluados=[int(a) for a in anios_seleccionados],
            )

            # Creamos los formularios asociados
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
    else:
        form = EvaluacionForm()
        # Definimos las opciones para mostrar en el formulario
        form.fields["anios_a_evaluar"].choices = [(y, y) for y in anios_pendientes]

    return render(
        request, "carrera_academica/iniciar_evaluacion.html", {"form": form, "ca": ca}
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
        # Verificamos qué formulario se envió
        if "submit_existente" in request.POST:
            form = CarreraAcademicaForm(request.POST)
            if form.is_valid():
                cargo_seleccionado = form.cleaned_data["cargo"]

                # Creamos la CA manualmente con las fechas del cargo
                nueva_ca = CarreraAcademica.objects.create(
                    cargo=cargo_seleccionado,
                    numero_expediente=form.cleaned_data["numero_expediente"],
                    fecha_inicio=cargo_seleccionado.fecha_inicio,
                    fecha_vencimiento_original=cargo_seleccionado.fecha_vencimiento,
                )
                # El signal se dispara aquí y crea los formularios
                messages.success(
                    request,
                    f"Carrera Académica iniciada para el cargo de {cargo_seleccionado}.",
                )
                return redirect("dashboard_ca")
            else:
                ca_form = form  # Devolvemos el form con errores

        elif "submit_nuevo" in request.POST:
            form = CargoForm(request.POST)
            if form.is_valid():
                # Creamos el nuevo cargo
                nuevo_cargo = form.save()

                # Creamos la CA asociada a este nuevo cargo
                nueva_ca = CarreraAcademica.objects.create(
                    cargo=nuevo_cargo,
                    fecha_inicio=nuevo_cargo.fecha_inicio,
                    fecha_vencimiento_original=nuevo_cargo.fecha_vencimiento,
                )
                messages.success(
                    request,
                    f"Nuevo cargo y Carrera Académica creados para {nuevo_cargo.docente}.",
                )
                return redirect("dashboard_ca")
            else:
                cargo_form = form  # Devolvemos el form con errores

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
    ca = get_object_or_404(CarreraAcademica, pk=pk)
    archivos_a_unir = []

    # 1. Recopilar archivos de los Formularios
    formularios_con_archivo = ca.formularios.exclude(archivo__isnull=True).exclude(
        archivo=""
    )
    for form in formularios_con_archivo:
        # Usamos la fecha de entrega si existe, si no, el 1ro de enero del año correspondiente
        fecha_orden = (
            form.fecha_entrega
            if form.fecha_entrega
            else date(form.anio_correspondiente or ca.fecha_inicio.year, 1, 1)
        )
        archivos_a_unir.append({"fecha": fecha_orden, "ruta": form.archivo.path})

    # 2. Recopilar archivos de las Resoluciones
    resoluciones_con_archivo = ca.cargo.resoluciones.exclude(file__isnull=True).exclude(
        file=""
    )
    for res in resoluciones_con_archivo:
        # Usamos el 1ro de enero del año de la resolución para ordenar
        fecha_orden = date(res.año, 1, 1)
        archivos_a_unir.append({"fecha": fecha_orden, "ruta": res.file.path})

    # 3. Ordenar la lista completa de archivos por fecha
    archivos_a_unir.sort(key=lambda x: x["fecha"])

    # 4. Unir los PDFs
    merger = PdfWriter()
    for archivo in archivos_a_unir:
        try:
            merger.append(archivo["ruta"])
        except Exception as e:
            # Si un PDF está corrupto o no es un PDF, lo saltamos y notificamos
            messages.warning(
                request,
                f"Se omitió un archivo por ser inválido o no ser un PDF: {archivo['ruta']}. Error: {e}",
            )

    # 5. Guardar el PDF unido en memoria
    output_buffer = io.BytesIO()
    merger.write(output_buffer)
    merger.close()
    output_buffer.seek(0)

    # 6. Devolver el archivo para su descarga
    response = HttpResponse(output_buffer, content_type="application/pdf")
    response["Content-Disposition"] = (
        f'attachment; filename="expediente_{slugify(ca.cargo.docente)}.pdf"'
    )
    return response


@login_required
def generar_propuesta_jurado_view(request, pk):
    ca = get_object_or_404(CarreraAcademica, pk=pk)
    # Usamos getattr para evitar error si no hay junta
    junta = getattr(ca, "junta_evaluadora", None)

    if not junta:
        messages.error(
            request,
            "No se puede generar la planilla porque no se ha asignado una Junta Evaluadora a este expediente.",
        )
        return redirect("detalle_ca", pk=pk)

    # Preparamos las listas de jurados para la plantilla
    jurados_titulares = []
    # Miembro interno titular
    if junta.miembro_interno_titular:
        docente = junta.miembro_interno_titular
        # Tomamos el primer cargo como representativo
        cargo = docente.cargo_docente.first()
        jurados_titulares.append(
            {
                "nombre": str(docente),
                "dependencia": "UTN-FRLP",
                "cargo": cargo.get_categoria_display() if cargo else "N/A",
                "email": (
                    docente.correos.filter(principal=True).first().email
                    if docente.correos.filter(principal=True).exists()
                    else "N/A"
                ),
            }
        )
    # Miembros externos titulares
    for externo in junta.miembros_externos_titulares.all():
        jurados_titulares.append(
            {
                "nombre": externo.nombre_completo,
                "dependencia": externo.universidad_origen,
                "cargo": externo.cargo_info,
                "email": externo.email,
            }
        )

    # Hacemos lo mismo para los suplentes
    jurados_suplentes = []
    if junta.miembro_interno_suplente:
        docente = junta.miembro_interno_suplente
        cargo = docente.cargo_docente.first()
        jurados_suplentes.append(
            {
                "nombre": str(docente),
                "dependencia": "UTN-FRLP",
                "cargo": cargo.get_categoria_display() if cargo else "N/A",
                "email": (
                    docente.correos.filter(principal=True).first().email
                    if docente.correos.filter(principal=True).exists()
                    else "N/A"
                ),
            }
        )
    for externo in junta.miembros_externos_suplentes.all():
        jurados_suplentes.append(
            {
                "nombre": externo.nombre_completo,
                "dependencia": externo.universidad_origen,
                "cargo": externo.cargo_info,
                "email": externo.email,
            }
        )

    contexto = {
        "ca": ca,
        "junta": junta,
        "jurados_titulares": jurados_titulares,
        "jurados_suplentes": jurados_suplentes,
    }

    # Renderizar la plantilla HTML a un string
    html_string = render_to_string("carrera_academica/planilla_jurado.html", contexto)

    # Generar el PDF
    with open(os.devnull, "w") as f, redirect_stderr(f):
        pdf_file = HTML(string=html_string).write_pdf()

    # Devolver el PDF para su descarga
    response = HttpResponse(pdf_file, content_type="application/pdf")
    response["Content-Disposition"] = (
        f'attachment; filename="propuesta_jurado_{slugify(ca.cargo.docente)}.pdf"'
    )
    return response


@login_required
def notificar_pendientes_view(request, pk):
    ca = get_object_or_404(CarreraAcademica, pk=pk)
    docente = ca.cargo.docente
    correo_principal = docente.correos.filter(principal=True).first()

    if not correo_principal:
        messages.error(
            request, f"El docente {docente} no tiene un correo principal asignado."
        )
        return redirect("detalle_ca", pk=ca.pk)

    tipos_a_notificar = ["F02", "F04", "F05"]
    formularios_pendientes = Formulario.objects.filter(
        carrera_academica=ca, estado="PEN", tipo_formulario__in=tipos_a_notificar
    )

    if not formularios_pendientes.exists():
        messages.info(
            request,
            "El docente no tiene formularios (F02, F04, F05) pendientes de entrega.",
        )
        return redirect("detalle_ca", pk=ca.pk)

    # Preparamos el correo
    info_cargo = f"{ca.cargo.get_categoria_display()} {ca.cargo.get_caracter_display()} en la asignatura {ca.cargo.asignatura.nombre.title()}"
    email_body_list = [
        "Estimado/a Docente,",
        f"\nLe recordamos que tiene documentación pendiente para su expediente de Carrera Académica correspondiente a su cargo de {info_cargo}.",
        "A continuación, se adjuntan las plantillas para los siguientes formularios:",
        "",
    ]
    email = EmailMessage(
        subject=f"Recordatorio de Documentación Pendiente - Carrera Académica",
        from_email=None,
        to=[correo_principal.email],
    )

    adjuntos_encontrados = 0
    email_body_list.append("- Curriculum Vitae (formato CONEAU).")

    # --- LÓGICA DE ADJUNTOS CORREGIDA ---
    for form in formularios_pendientes:
        # Si es un formulario dinámico (anual), lo generamos al momento
        if form.tipo_formulario in ["F04", "F05", "F06", "F07", "F13", "ENC"]:
            buffer, filename = _generar_documento_dinamico(form)
            if buffer:
                email.attach(
                    filename,
                    buffer.getvalue(),
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
                adjuntos_encontrados += 1
                email_body_list.append(
                    f"- {form.tipo_formulario} del año {form.anio_correspondiente} (Personalizado)"
                )
            else:
                email_body_list.append(
                    f"- {form.tipo_formulario} del año {form.anio_correspondiente} - ERROR: No se pudo generar (verifique plantillas y membretes)."
                )

        # Si es un formulario estático (como el F02), buscamos su plantilla maestra
        elif form.tipo_formulario == "F02":
            plantilla = PlantillaDocumento.objects.filter(tipo_formulario="F02").first()
            if plantilla and plantilla.archivo:
                email.attach_file(plantilla.archivo.path)
                adjuntos_encontrados += 1
                email_body_list.append("- Formulario F02")
            else:
                email_body_list.append(
                    "- Formulario F02 - PLANTILLA MAESTRA NO ENCONTRADA."
                )

    email_body_list.append("\nSaludos cordiales,")
    email_body_list.append("Departamento de Ing. Civil")
    email.body = "\n".join(email_body_list)

    email.send()

    messages.success(
        request,
        f"Correo de recordatorio enviado a {docente} con {adjuntos_encontrados} documentos adjuntos.",
    )
    return redirect("detalle_ca", pk=ca.pk)


@login_required
def descargar_plantilla_view(request, pk):
    formulario = get_object_or_404(Formulario, pk=pk)
    tipos_dinamicos = ["F06", "F07", "F13", "ENC", "F04", "F05"]

    if formulario.tipo_formulario in tipos_dinamicos:
        buffer, filename = _generar_documento_dinamico(formulario)
        if buffer:
            return FileResponse(buffer, as_attachment=True, filename=filename)
        else:
            messages.error(
                request,
                "No se pudo generar el documento dinámico. Verifique que la plantilla maestra y el membrete del año existan.",
            )
            return redirect("detalle_ca", pk=formulario.carrera_academica.pk)
    else:
        # Lógica anterior para plantillas estáticas (como F02)
        plantilla = PlantillaDocumento.objects.filter(
            tipo_formulario=formulario.tipo_formulario, anio__isnull=True
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
                f"No se encontró una plantilla para el formulario {formulario.tipo_formulario}.",
            )
            return redirect("detalle_ca", pk=formulario.carrera_academica.pk)


@login_required
def notificar_junta_view(request, pk):
    evaluacion = get_object_or_404(Evaluacion, pk=pk)
    junta = getattr(evaluacion, "junta_evaluadora", None)
    ca = evaluacion.carrera_academica

    if not junta:
        messages.error(request, "Esta evaluación no tiene una junta asignada.")
        return redirect("detalle_ca", pk=ca.pk)

    # === 1. DETERMINAR MIEMBROS ACTIVOS ===
    miembros_a_notificar = []

    # Miembro Interno
    if junta.asistencia_status.get("miembro_interno_titular") == "ausente":
        if junta.miembro_interno_suplente:
            miembros_a_notificar.append(junta.miembro_interno_suplente)
    else:
        if junta.miembro_interno_titular:
            miembros_a_notificar.append(junta.miembro_interno_titular)

    # Miembros Externos (aquí notificamos a todos los titulares por defecto)
    miembros_a_notificar.extend(junta.miembros_externos_titulares.all())

    # Veedores (notificamos a los titulares)
    if junta.veedor_alumno_titular:
        miembros_a_notificar.append(junta.veedor_alumno_titular)
    if junta.veedor_graduado_titular:
        miembros_a_notificar.append(junta.veedor_graduado_titular)

    if not miembros_a_notificar:
        messages.warning(request, "No hay miembros activos en la junta para notificar.")
        return redirect("detalle_ca", pk=ca.pk)

    # === 2. RECOPILAR DOCUMENTOS PERTINENTES ===
    # Formularios generales (no anuales) que ya fueron entregados
    documentos_generales = (
        ca.formularios.filter(estado="ENT", anio_correspondiente__isnull=True)
        .exclude(archivo__isnull=True)
        .exclude(archivo="")
    )

    # Formularios anuales de los años que cubre ESTA evaluación, que ya fueron entregados
    documentos_anuales = (
        ca.formularios.filter(
            estado="ENT", anio_correspondiente__in=evaluacion.anios_evaluados
        )
        .exclude(archivo__isnull=True)
        .exclude(archivo="")
    )

    # Unimos ambas listas de documentos
    documentos_a_adjuntar = list(documentos_generales) + list(documentos_anuales)

    if not documentos_a_adjuntar:
        messages.warning(
            request,
            "No hay documentos entregados en el expediente para enviar a la junta.",
        )
        return redirect("detalle_ca", pk=ca.pk)

    # === 3. ENVIAR CORREOS A CADA MIEMBRO ACTIVO ===
    email_subject = (
        f"Convocatoria y Documentación para Junta Evaluadora - {ca.cargo.docente}"
    )
    email_body = (
        f"Estimado/a Miembro de la Junta Evaluadora,\n\n"
        f"Se le convoca a participar en la evaluación para la Carrera Académica de {ca.cargo.docente}. "
        f"La misma está agendada para el {evaluacion.fecha_evaluacion.strftime('%d/%m/%Y a las %H:%Mhs') if evaluacion.fecha_evaluacion else 'a confirmar'}.\n\n"
        f"Se adjunta toda la documentación relevante del expediente para su análisis.\n\n"
        f"Saludos cordiales."
    )

    emails_enviados = 0
    for miembro in miembros_a_notificar:
        # Obtenemos el email sin importar si es Docente, MiembroExterno o Veedor
        email_destinatario = ""
        if isinstance(miembro, Docente):
            correo = miembro.correos.filter(principal=True).first()
            if correo:
                email_destinatario = correo.email
        else:  # Para MiembroExterno y Veedor, el email está en el propio objeto
            email_destinatario = miembro.email

        if email_destinatario:
            email = EmailMessage(
                subject=email_subject,
                body=email_body,
                from_email=None,
                to=[email_destinatario],
            )
            for doc in documentos_a_adjuntar:
                if doc.archivo:
                    email.attach_file(doc.archivo.path)

            email.send()
            emails_enviados += 1

    messages.success(
        request,
        f"Se han enviado {emails_enviados} correos a los miembros de la junta con la documentación adjunta.",
    )
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
