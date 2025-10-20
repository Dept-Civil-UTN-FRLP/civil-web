# carrera_academica/services/pdf_service.py
"""
Servicio para generación de documentos PDF.
"""
import io
import logging
from typing import Optional, Tuple
from contextlib import redirect_stderr
import os

from django.template.loader import render_to_string
from pypdf import PdfWriter
from weasyprint import HTML

from carrera_academica.models import CarreraAcademica

logger = logging.getLogger(__name__)


class PDFService:
    """Servicio centralizado para generación de PDFs."""

    @staticmethod
    def consolidar_expediente(ca: CarreraAcademica) -> Tuple[Optional[io.BytesIO], list]:
        """
        Consolida todo el expediente de una CA en un único PDF.

        Args:
            ca: Instancia de CarreraAcademica

        Returns:
            tuple: (BytesIO con el PDF, lista de errores/advertencias)
        """
        archivos_a_unir = []
        errores = []

        # Recopilar archivos de formularios
        formularios_con_archivo = ca.formularios.exclude(
            archivo__isnull=True
        ).exclude(archivo="")

        for form in formularios_con_archivo:
            fecha_orden = PDFService._obtener_fecha_orden_formulario(form, ca)
            archivos_a_unir.append(
                {"fecha": fecha_orden, "ruta": form.archivo.path})

        # Recopilar archivos de resoluciones
        resoluciones_con_archivo = ca.cargo.resoluciones.exclude(
            file__isnull=True
        ).exclude(file="")

        for res in resoluciones_con_archivo:
            from datetime import date
            fecha_orden = date(res.año, 1, 1)
            archivos_a_unir.append(
                {"fecha": fecha_orden, "ruta": res.file.path})

        if not archivos_a_unir:
            logger.warning(f"No hay archivos para consolidar en CA {ca.pk}")
            return None, ["No hay archivos para consolidar"]

        # Ordenar por fecha
        archivos_a_unir.sort(key=lambda x: x["fecha"])

        # Unir PDFs
        merger = PdfWriter()
        for archivo in archivos_a_unir:
            try:
                merger.append(archivo["ruta"])
            except Exception as e:
                error_msg = f"Archivo omitido (corrupto o inválido): {archivo['ruta']}"
                logger.warning(f"{error_msg}. Error: {e}")
                errores.append(error_msg)

        # Guardar en memoria
        output_buffer = io.BytesIO()
        try:
            merger.write(output_buffer)
            merger.close()
            output_buffer.seek(0)

            logger.info(f"PDF consolidado exitosamente para CA {ca.pk}")
            return output_buffer, errores

        except Exception as e:
            logger.error(
                f"Error al escribir PDF consolidado para CA {ca.pk}: {e}")
            return None, [f"Error al generar PDF: {str(e)}"]

    @staticmethod
    def generar_propuesta_jurado(ca: CarreraAcademica, signature_path: str) -> Optional[bytes]:
        """
        Genera PDF de propuesta de jurado.

        Args:
            ca: Instancia de CarreraAcademica
            signature_path: Ruta a la imagen de firma

        Returns:
            bytes con el PDF o None si hay error
        """
        junta = getattr(ca, "junta_evaluadora", None)

        if not junta:
            logger.error(
                f"CA {ca.pk} no tiene junta evaluadora para generar PDF")
            return None

        # Preparar datos de jurados
        jurados_titulares = PDFService._preparar_datos_jurados_titulares(junta)
        jurados_suplentes = PDFService._preparar_datos_jurados_suplentes(junta)

        context = {
            "ca": ca,
            "junta": junta,
            "jurados_titulares": jurados_titulares,
            "jurados_suplentes": jurados_suplentes,
        }

        try:
            html_string = render_to_string(
                "carrera_academica/planilla_jurado.html",
                context
            )

            # Generar PDF silenciando stderr de WeasyPrint
            with open(os.devnull, "w") as f, redirect_stderr(f):
                pdf_file = HTML(string=html_string).write_pdf()

            logger.info(f"PDF de propuesta de jurado generado para CA {ca.pk}")
            return pdf_file

        except Exception as e:
            logger.error(f"Error generando PDF de jurado para CA {ca.pk}: {e}")
            return None

    @staticmethod
    def _obtener_fecha_orden_formulario(form, ca):
        """Obtiene la fecha para ordenar un formulario."""
        from datetime import date

        if form.fecha_entrega:
            return form.fecha_entrega

        anio = form.anio_correspondiente or ca.fecha_inicio.year
        return date(anio, 1, 1)

    @staticmethod
    def _preparar_datos_jurados_titulares(junta):
        """Prepara los datos de jurados titulares para el template."""
        jurados = []

        # Miembro interno titular
        if junta.miembro_interno_titular:
            docente = junta.miembro_interno_titular
            cargo = docente.cargo_docente.first()
            jurados.append({
                "nombre": str(docente),
                "dependencia": "UTN-FRLP",
                "cargo": cargo.get_categoria_display() if cargo else "N/A",
                "email": PDFService._obtener_email_docente(docente),
            })

        # Miembros externos titulares
        for externo in junta.miembros_externos_titulares.all():
            jurados.append({
                "nombre": externo.nombre_completo,
                "dependencia": externo.universidad_origen,
                "cargo": externo.cargo_info,
                "email": externo.email,
            })

        return jurados

    @staticmethod
    def _preparar_datos_jurados_suplentes(junta):
        """Prepara los datos de jurados suplentes para el template."""
        jurados = []

        # Miembro interno suplente
        if junta.miembro_interno_suplente:
            docente = junta.miembro_interno_suplente
            cargo = docente.cargo_docente.first()
            jurados.append({
                "nombre": str(docente),
                "dependencia": "UTN-FRLP",
                "cargo": cargo.get_categoria_display() if cargo else "N/A",
                "email": PDFService._obtener_email_docente(docente),
            })

        # Miembros externos suplentes
        for externo in junta.miembros_externos_suplentes.all():
            jurados.append({
                "nombre": externo.nombre_completo,
                "dependencia": externo.universidad_origen,
                "cargo": externo.cargo_info,
                "email": externo.email,
            })

        return jurados

    @staticmethod
    def _obtener_email_docente(docente):
        """Obtiene el email principal de un docente."""
        correo = docente.correos.filter(principal=True).first()
        return correo.email if correo else "N/A"
