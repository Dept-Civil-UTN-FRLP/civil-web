# carrera_academica/models.py

from django.db import models
from django.utils import timezone
from django.utils.text import slugify
import os
import uuid

from planta_docente.models import *


# ==============================================================================
# TUS MODELOS (CON PEQUEÑAS CORRECCIONES)
# ==============================================================================


def get_ca_upload_path(instance, filename):
    """
    Genera una ruta de guardado con un nombre de archivo hasheado (UUID).
    Funciona tanto para Formularios como para Resoluciones.
    Ej: media/ca/apellido-nombre/uuid4().pdf
    """
    try:
        docente = instance.carrera_academica.cargo.docente
    except AttributeError:
        docente = instance.cargo.docente

    nombre_completo = f"{docente.apellido} {docente.nombre}"
    docente_slug = slugify(nombre_completo)

    # Obtenemos la extensión del archivo original
    extension = os.path.splitext(filename)[1]
    # Creamos un nuevo nombre de archivo único
    new_filename = f"{uuid.uuid4()}{extension}"

    # Devuelve la ruta final
    return f"ca/{docente_slug}/{new_filename}"


# ==============================================================================
# MODELOS DE CARRERA ACADÉMICA (ADAPTADOS Y REINTEGRADOS)
# ==============================================================================


def get_ca_upload_path(instance, filename):
    """Genera una ruta única para los archivos de cada CA"""
    # Obtenemos el objeto docente
    docente = instance.carrera_academica.cargo.docente
    # Construimos el nombre completo a partir de los campos correctos
    nombre_completo = f"{docente.apellido} {docente.nombre}"

    # Creamos el nombre de la carpeta seguro
    docente_slug = slugify(nombre_completo)

    return f"carrera_academica/{docente_slug}/{filename}"


class CarreraAcademica(models.Model):
    ESTADO_CHOICES = [
        ("ACT", "Activa"),
        ("STB", "En Standby (Licencia)"),
        ("FIN", "Finalizada"),
        ("VEN", "Vencida"),
    ]

    cargo = models.OneToOneField(
        Cargo, on_delete=models.CASCADE, related_name="carrera_academica"
    )
    numero_expediente = models.CharField(
        max_length=50, blank=True, unique=True, null=True, help_text="Ej: 12345/2024"
    )
    fecha_inicio = models.DateField()
    fecha_vencimiento_original = models.DateField()
    fecha_vencimiento_actual = models.DateField(
        help_text="Se actualiza con las prórrogas"
    )
    estado = models.CharField(max_length=3, choices=ESTADO_CHOICES, default="ACT")
    resolucion_designacion = models.ForeignKey(
        Resolucion,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ca_designacion",
        help_text="Resolución de designación del cargo (CSU o CD)",
    )
    resolucion_puesta_en_funcion = models.ForeignKey(
        Resolucion,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ca_puesta_en_funcion",
        help_text="Resolución de puesta en función (Decano)",
    )
    fecha_finalizacion = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.pk:
            self.fecha_vencimiento_actual = self.fecha_vencimiento_original
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Expediente de {self.cargo}"


class Evaluacion(models.Model):
    ESTADO_EVAL_CHOICES = [
        ("PRO", "Programada"),
        ("REA", "Realizada"),
        ("CAN", "Cancelada"),
    ]
    carrera_academica = models.ForeignKey(
        CarreraAcademica, on_delete=models.CASCADE, related_name="evaluaciones"
    )
    numero_evaluacion = models.PositiveIntegerField()
    fecha_iniciada = models.DateField(default=timezone.now)
    # Usamos un JSONField para guardar la lista de años, es muy flexible.
    anios_evaluados = models.JSONField(
        default=list,
        help_text="Lista de años que cubre esta evaluación, ej: [2022, 2023]",
    )
    fecha_evaluacion = models.DateTimeField(
        verbose_name="Fecha y Hora de la Evaluación", null=True, blank=True
    )
    estado = models.CharField(max_length=3, choices=ESTADO_EVAL_CHOICES, default="PRO")

    class Meta:
        # Nos aseguramos de que no haya dos "Evaluación 1" para la misma CA
        unique_together = ("carrera_academica", "numero_evaluacion")
        ordering = ["numero_evaluacion"]

    def __str__(self):
        return f"Evaluación N°{self.numero_evaluacion} de {self.carrera_academica.cargo.docente}"


class Formulario(models.Model):
    TIPO_FORMULARIO_CHOICES = (
        [("CV", "Curriculum Vitae")]
        + [(f"F{i:02d}", f"F{i:02d}") for i in range(1, 14)]
        + [("ENC", "Encuesta")]
    )
    ESTADO_FORMULARIO_CHOICES = [
        ("PEN", "Pendiente"),
        ("ENT", "Entregado"),
        ("OBS", "Observado"),
    ]

    carrera_academica = models.ForeignKey(
        CarreraAcademica, on_delete=models.CASCADE, related_name="formularios"
    )
    tipo_formulario = models.CharField(max_length=4, choices=TIPO_FORMULARIO_CHOICES)
    estado = models.CharField(
        max_length=3, choices=ESTADO_FORMULARIO_CHOICES, default="PEN"
    )
    fecha_entrega = models.DateField(blank=True, null=True)
    archivo = models.FileField(upload_to=get_ca_upload_path, blank=True, null=True)
    anio_correspondiente = models.IntegerField(
        blank=True, null=True, help_text="Ej: 2024 (para F04-F07, F13)"
    )
    anio_correspondiente = models.IntegerField(
        blank=True, null=True, help_text="Ej: 2024 (para F04-F07, F13)"
    )
    evaluacion = models.ForeignKey(
        Evaluacion,
        on_delete=models.CASCADE,
        related_name="formularios",
        null=True,
        blank=True,
    )

    def __str__(self):
        return f"{self.tipo_formulario} de {self.carrera_academica.cargo.docente}"


class MiembroExterno(models.Model):
    nombre_completo = models.CharField(max_length=255)
    email = models.EmailField()
    universidad_origen = models.CharField(
        max_length=255, help_text="Ej: Universidad Nacional de Buenos Aires"
    )
    cargo_info = models.CharField(
        max_length=255, help_text="Ej: Titular con Dedicación Exclusiva"
    )
    resolucion_designacion = models.CharField(
        max_length=100,
        blank=True,
        help_text="Nro. de resolución de designación a la junta",
    )

    def __str__(self):
        return f"{self.nombre_completo} ({self.universidad_origen})"

    class Meta:
        verbose_name = "Miembro Externo"
        verbose_name_plural = "Miembros Externos"


class Veedor(models.Model):
    CLAUSTRO_CHOICES = [
        ("ALU", "Alumno"),
        ("GRA", "Graduado"),
    ]
    nombre_completo = models.CharField(max_length=255, unique=True)
    email = models.EmailField(blank=True, null=True)
    claustro = models.CharField(max_length=3, choices=CLAUSTRO_CHOICES)

    def __str__(self):
        return f"{self.nombre_completo} ({self.get_claustro_display()})"


class JuntaEvaluadora(models.Model):
    carrera_academica = models.OneToOneField(
        CarreraAcademica, on_delete=models.CASCADE, related_name="junta_evaluadora"
    )

    # Miembros Internos (locales)
    miembro_interno_titular = models.ForeignKey(
        Docente,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="juntas_titular_interno",
    )
    miembro_interno_suplente = models.ForeignKey(
        Docente,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="juntas_suplente_interno",
    )

    # Miembros Externos
    miembros_externos_titulares = models.ManyToManyField(
        MiembroExterno, related_name="juntas_titular_externo", blank=True
    )
    miembros_externos_suplentes = models.ManyToManyField(
        MiembroExterno, related_name="juntas_suplente_externo", blank=True
    )

    # Veedores
    veedor_alumno_titular = models.ForeignKey(
        Veedor,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="veedor_alumno_tit",
        limit_choices_to={"claustro": "ALU"},
    )
    veedor_alumno_suplente = models.ForeignKey(
        Veedor,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="veedor_alumno_sup",
        limit_choices_to={"claustro": "ALU"},
    )
    veedor_graduado_titular = models.ForeignKey(
        Veedor,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="veedor_graduado_tit",
        limit_choices_to={"claustro": "GRA"},
    )
    veedor_graduado_suplente = models.ForeignKey(
        Veedor,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="veedor_graduado_sup",
        limit_choices_to={"claustro": "GRA"},
    )

    asistencia_status = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"Junta para {self.evaluacion}"


class MembreteAnual(models.Model):
    anio = models.IntegerField(
        unique=True, help_text="Año al que corresponde este membrete"
    )
    logo = models.ImageField(upload_to="membretes/logos/")
    frase = models.CharField(
        max_length=255, help_text="Frase del encabezado para este año"
    )

    def __str__(self):
        return f"Membrete para el año {self.anio}"

    class Meta:
        verbose_name = "Membrete Anual"
        verbose_name_plural = "Membretes Anuales"


class PlantillaDocumento(models.Model):
    TIPO_FORMULARIO_CHOICES = [
        ("F02", "F02"),
        ("F04", "F04"),
        ("F05", "F05"),
        ("F06", "F06"),
        ("F07", "F07"),
        ("F13", "F13"),
    ]

    tipo_formulario = models.CharField(max_length=4, choices=TIPO_FORMULARIO_CHOICES)
    archivo = models.FileField(upload_to="plantillas_documentos/")
    descripcion = models.CharField(max_length=255, blank=True)

    class Meta:
        # Nos aseguramos de que solo haya una plantilla F04 para el 2024, por ejemplo.
        verbose_name = "Plantilla de Documento"
        verbose_name_plural = "Plantillas de Documentos"

    def __str__(self):
        return f"Plantilla para {self.tipo_formulario}"
