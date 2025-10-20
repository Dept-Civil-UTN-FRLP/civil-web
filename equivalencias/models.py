# equivalencias/models.py

from django.db import models
from django.utils.text import slugify
from django.utils import timezone
import os, uuid

# <-- Apunta a la nueva app
from planta_docente.models import Asignatura as AsignaturaCA, Docente as DocenteCA


def get_equivalencias_upload_path(instance, filename):
    """
    Genera una ruta de guardado con un nombre de archivo hasheado (UUID).
    Ej: media/equivalencias/nombre-del-estudiante/uuid4().pdf
    """
    try:
        student_name = instance.solicitud.id_estudiante.nombre_completo
    except AttributeError:
        student_name = instance.id_estudiante.nombre_completo

    student_folder = slugify(student_name)

    # Obtenemos la extensión del archivo original
    extension = os.path.splitext(filename)[1]
    # Creamos un nuevo nombre de archivo único
    new_filename = f"{uuid.uuid4()}{extension}"

    # Devolvemos la ruta final
    return f"equivalencias/{student_folder}/{new_filename}"


class AsignaturaParaEquivalencia(models.Model):
    # Vinculamos con la asignatura detallada de la app carrera_academica
    asignatura = models.OneToOneField(
        AsignaturaCA, on_delete=models.CASCADE, verbose_name="Asignatura"
    )

    # Vinculamos con el docente responsable de la app carrera_academica
    docente_responsable = models.ForeignKey(
        DocenteCA,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Docente Responsable",
    )

    def __str__(self):
        return self.asignatura.nombre.title()

    class Meta:
        verbose_name = "Asignatura para Equivalencia"
        verbose_name_plural = "Asignaturas para Equivalencias"


class Estudiante(models.Model):
    nombre_completo = models.CharField(max_length=200)
    email_estudiante = models.EmailField(blank=True, null=True)
    dni_pasaporte = models.CharField(
        "DNI o Pasaporte", max_length=50, unique=True, blank=True, null=True
    )

    def __str__(self):
        return self.nombre_completo


class SolicitudEquivalencia(models.Model):
    ESTADO_CHOICES = [
        ("En Proceso", "En Proceso"),
        ("Completada", "Completada"),
        ("Cancelada", "Cancelada"),
    ]
    id_estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE)
    fecha_inicio = models.DateTimeField(default=timezone.now)
    estado_general = models.CharField(
        max_length=20, choices=ESTADO_CHOICES, default="En Proceso"
    )
    acta_firmada = models.FileField(
        upload_to=get_equivalencias_upload_path, blank=True, null=True
    )
    fecha_completada = models.DateTimeField(null=True, blank=True)

    @property
    def progreso(self):
        """
        Calcula y devuelve el progreso de la solicitud como un string.
        Ejemplo: "3 de 5".
        """
        # Contamos el total de asignaturas en esta solicitud
        total_asignaturas = self.detallesolicitud_set.count()

        if total_asignaturas == 0:
            return "0 de 0"

        # Contamos cuántas ya tienen un dictamen final
        estados_finales = ["Aprobada", "Denegada", "Requiere PC"]
        asignaturas_respondidas = self.detallesolicitud_set.filter(
            estado_asignatura__in=estados_finales
        ).count()

        return f"{asignaturas_respondidas} de {total_asignaturas}"

    def __str__(self):
        return (
            f"Solicitud de {self.id_estudiante.nombre_completo} - {self.fecha_inicio}"
        )


class DocumentoAdjunto(models.Model):
    solicitud = models.ForeignKey(SolicitudEquivalencia, on_delete=models.CASCADE)
    archivo = models.FileField(upload_to=get_equivalencias_upload_path)

    def __str__(self):
        # Muestra el nombre del archivo en el admin
        return self.archivo.name


class DetalleSolicitud(models.Model):
    ESTADO_ASIGNATURA_CHOICES = [
        ("Pendiente de envío", "Pendiente de envío"),
        ("Enviada a Cátedra", "Enviada a Cátedra"),
        ("Aprobada", "Aprobada"),
        ("Denegada", "Denegada"),
        ("Requiere PC", "Requiere Programa Complementario"),
    ]
    id_solicitud = models.ForeignKey(SolicitudEquivalencia, on_delete=models.CASCADE)
    id_asignatura = models.ForeignKey(
        AsignaturaParaEquivalencia, on_delete=models.CASCADE
    )
    estado_asignatura = models.CharField(
        max_length=20, choices=ESTADO_ASIGNATURA_CHOICES, default="Pendiente de envío"
    )
    detalle_pc = models.TextField(
        blank=True, null=True, help_text="Detallar temas del Programa Complementario"
    )
    fecha_dictamen = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"{self.id_asignatura.asignatura.nombre} para {self.id_solicitud.id_estudiante.nombre_completo}"
