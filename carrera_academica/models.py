# carrera_academica/models.py
import os
import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.text import slugify

from planta_docente.models import *

from .managers import CarreraAcademicaManager, EvaluacionManager

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
    anios_pausados = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Años Pausados",
        help_text="Lista de años que no se evaluarán. Formato: [{'anio': 2022, 'motivo': '...', 'fecha': '2022-03-15', 'usuario': 'admin'}]"
    )
    objects = CarreraAcademicaManager()

    def clean(self):
        """Validaciones a nivel de modelo."""
        super().clean()
        errors = {}

        # Validación 1: Solo cargos regulares u ordinarios pueden tener CA
        if self.cargo.caracter not in ["reg", "ord"]:
            errors["cargo"] = ValidationError(
                "Solo los cargos Regulares u Ordinarios pueden tener Carrera Académica.",
                code="invalid_caracter",
            )

        # Validación 2: Fecha de vencimiento debe ser posterior al inicio
        if self.fecha_vencimiento_original and self.fecha_inicio:
            if self.fecha_vencimiento_original <= self.fecha_inicio:
                errors["fecha_vencimiento_original"] = ValidationError(
                    "La fecha de vencimiento debe ser posterior a la fecha de inicio.",
                    code="invalid_date_range",
                )

        # Validación 3: Fecha de vencimiento actual no puede ser anterior al inicio
        if self.fecha_vencimiento_actual and self.fecha_inicio:
            if self.fecha_vencimiento_actual < self.fecha_inicio:
                errors["fecha_vencimiento_actual"] = ValidationError(
                    "La fecha de vencimiento actual no puede ser anterior a la fecha de inicio.",
                    code="invalid_current_date",
                )

        # Validación 4: La duración debe ser al menos de 2 años
        if self.fecha_inicio and self.fecha_vencimiento_original:
            duracion = self.fecha_vencimiento_original - self.fecha_inicio
            if duracion.days < 730:  # 2 años = ~730 días
                errors["fecha_vencimiento_original"] = ValidationError(
                    "La Carrera Académica debe tener una duración mínima de 2 años.",
                    code="duration_too_short",
                )

        # Validación 5: Si está finalizada, debe tener fecha de finalización
        if self.estado == "FIN" and not self.fecha_finalizacion:
            errors["fecha_finalizacion"] = ValidationError(
                "Una Carrera Académica finalizada debe tener fecha de finalización.",
                code="missing_finalization_date",
            )

        # Validación 6: No puede haber otra CA activa para el mismo cargo
        if self.estado == "ACT":
            otras_ca_activas = CarreraAcademica.objects.filter(
                cargo=self.cargo, estado="ACT"
            ).exclude(pk=self.pk)

            if otras_ca_activas.exists():
                errors["cargo"] = ValidationError(
                    "Ya existe una Carrera Académica activa para este cargo.",
                    code="duplicate_active_ca",
                )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        """Override save para ejecutar validaciones."""
        # Solo validar si no es una instancia nueva o si se están modificando campos críticos
        if self.pk or not kwargs.get("skip_validation", False):
            self.full_clean()

        if not self.pk:
            self.fecha_vencimiento_actual = self.fecha_vencimiento_original

        super().save(*args, **kwargs)

    def puede_iniciar_evaluacion(self):
        """Verifica si se puede iniciar una nueva evaluación."""
        if self.estado != "ACT":
            return False, "La Carrera Académica no está activa"

        # Verificar que haya años pendientes de evaluar
        start_year = self.fecha_inicio.year
        end_year = timezone.now().year
        todos_los_anios = set(range(start_year, end_year + 1))

        anios_evaluados = set()
        for ev in self.evaluaciones.all():
            anios_evaluados.update(ev.anios_evaluados)

        anios_pendientes = todos_los_anios - anios_evaluados

        if not anios_pendientes:
            return False, "No hay años pendientes de evaluación"

        return True, ""
    
    def get_anios_activos(self):
        """
        Retorna lista de años disponibles para iniciar una nueva evaluación.
        Excluye: pausados, en evaluación, y evaluados con acta.
        """
        start_year = self.fecha_inicio.year
        end_year = self.fecha_vencimiento_actual.year

        # Años pausados
        pausados = {item['anio'] for item in self.get_anios_pausados()}

        # Años ya evaluados (con acta) o en evaluación
        anios_no_disponibles = set()

        for ev in self.evaluaciones.all():
            # Verificar si tiene F12 subido
            tiene_acta = ev.formularios_evaluacion.filter(
                tipo_formulario='F12',
                archivo__isnull=False
            ).exclude(archivo='').exists()

            # Si tiene acta O está en evaluación, no disponible
            for anio in ev.anios_evaluados:
                anios_no_disponibles.add(anio)

        # Años activos = todos - (pausados + no_disponibles)
        anios_activos = []
        for anio in range(start_year, end_year + 1):
            if anio not in pausados and anio not in anios_no_disponibles:
                anios_activos.append(anio)

        return sorted(anios_activos)

    def get_anios_pausados(self):
        """Retorna lista de años pausados con info"""
        return sorted(self.anios_pausados, key=lambda x: x['anio'], reverse=True)

    def pausar_anio(self, anio, motivo, usuario):
        """
        Pausa un año específico.
        No se pueden pausar años en evaluación o ya evaluados.
        """
        # Validar que el año esté en el rango
        start_year = self.fecha_inicio.year
        end_year = self.fecha_vencimiento_actual.year

        if not (start_year <= anio <= end_year):
            return False, f"El año {anio} está fuera del rango de la CA ({start_year}-{end_year})"

        # Verificar estado del año
        resumen = self.get_resumen_anios()
        estado_anio = None
        for item in resumen:
            if item['anio'] == anio:
                estado_anio = item['estado']
                break

        # No permitir pausar años evaluados
        if estado_anio == 'evaluado':
            evaluacion_num = next((item['info']['evaluacion']
                                  for item in resumen if item['anio'] == anio), None)
            return False, f"No se puede pausar el año {anio}. Ya fue evaluado en la Evaluación N°{evaluacion_num}"

        # No permitir pausar años en evaluación
        if estado_anio == 'en_evaluacion':
            evaluacion_num = next((item['info']['evaluacion']
                                  for item in resumen if item['anio'] == anio), None)
            return False, f"No se puede pausar el año {anio}. Está incluido en la Evaluación N°{evaluacion_num} en curso"

        # Verificar si ya está pausado
        if estado_anio == 'pausado':
            return False, f"El año {anio} ya está pausado"

        # Pausar el año
        pausa = {
            'anio': anio,
            'motivo': motivo,
            'fecha': timezone.now().strftime('%Y-%m-%d'),
            'usuario': usuario
        }

        self.anios_pausados.append(pausa)
        self.save()

        return True, f"Año {anio} pausado exitosamente"

    def reactivar_anio(self, anio):
        """Reactiva un año pausado"""
        # Buscar y eliminar
        original_len = len(self.anios_pausados)
        self.anios_pausados = [
            item for item in self.anios_pausados
            if item['anio'] != anio
        ]

        if len(self.anios_pausados) == original_len:
            return False, f"El año {anio} no está pausado"

        self.save()
        return True, f"Año {anio} reactivado exitosamente"

    def get_resumen_anios(self):
        """
        Retorna lista con estado de cada año: pendiente, pausado, en_evaluacion, evaluado.
        Un año está 'evaluado' solo cuando existe un F12 (acta) subido.
        """
        start_year = self.fecha_inicio.year
        end_year = self.fecha_vencimiento_actual.year

        # Años pausados
        pausados = {item['anio']: item for item in self.get_anios_pausados()}

        # Años en evaluaciones
        evaluaciones = self.evaluaciones.all()
        anios_en_evaluacion = {}  # {año: evaluacion_id}
        anios_evaluados = {}  # {año: {'evaluacion': N, 'fecha': date, 'tiene_acta': bool}}

        for ev in evaluaciones:
            tiene_acta = ev.formularios.filter(
                tipo_formulario='F12',
                archivo__isnull=False
            ).exclude(archivo='').exists()

            for anio in ev.anios_evaluados:
                if tiene_acta:
                    # Evaluación cerrada con acta
                    anios_evaluados[anio] = {
                        'evaluacion': ev.numero_evaluacion,
                        'fecha': ev.fecha_iniciada.strftime('%d/%m/%Y'),
                        'tiene_acta': True
                    }
                else:
                    # Evaluación en curso (sin acta todavía)
                    anios_en_evaluacion[anio] = ev.numero_evaluacion

        # Construir resumen
        resumen = []
        for anio in range(start_year, end_year + 1):
            if anio in anios_evaluados:
                # Año con evaluación cerrada (tiene acta)
                resumen.append({
                    'anio': anio,
                    'estado': 'evaluado',
                    'info': anios_evaluados[anio]
                })
            elif anio in anios_en_evaluacion:
                # Año en evaluación (sin acta todavía)
                resumen.append({
                    'anio': anio,
                    'estado': 'en_evaluacion',
                    'info': {
                        'evaluacion': anios_en_evaluacion[anio],
                        'mensaje': 'En proceso de evaluación'
                    }
                })
            elif anio in pausados:
                # Año pausado
                resumen.append({
                    'anio': anio,
                    'estado': 'pausado',
                    'info': pausados[anio]
                })
            else:
                # Año pendiente
                resumen.append({
                    'anio': anio,
                    'estado': 'pendiente',
                    'info': None
                })

        return resumen
    
    def agregar_formularios_para_anio(self, anio):
        """
        Crea formularios para un año específico según la dedicación del cargo.
        Retorna cantidad de formularios creados.
        """
        # Validar que el año esté en el rango de la CA
        start_year = self.fecha_inicio.year
        end_year = self.fecha_vencimiento_actual.year

        if not (start_year <= anio <= end_year):
            return 0, f"El año {anio} está fuera del rango de la CA ({start_year}-{end_year})"

        # Tipos de formularios anuales base
        tipos_anuales = ['F04', 'F05', 'F06', 'F07', 'ENC']

        # Agregar F13 si es DE o SE
        if self.cargo.dedicacion in ['de', 'se']:
            tipos_anuales.append('F13')

        # Crear formularios que no existan
        creados = 0
        for tipo in tipos_anuales:
            # Verificar si ya existe
            existe = Formulario.objects.filter(
                carrera_academica=self,
                tipo_formulario=tipo,
                anio_correspondiente=anio
            ).exists()

            if not existe:
                Formulario.objects.create(
                    carrera_academica=self,
                    tipo_formulario=tipo,
                    anio_correspondiente=anio
                )
                creados += 1

        return creados, f"Se crearon {creados} formularios para el año {anio}"

    def agregar_anios_por_prorroga(self, nueva_fecha_vencimiento):
        """
        Agrega formularios para años nuevos cuando se prorroga la CA.
        Retorna (años_agregados, formularios_creados, mensaje).
        """
        anio_actual_vencimiento = self.fecha_vencimiento_actual.year
        anio_nuevo_vencimiento = nueva_fecha_vencimiento.year

        if anio_nuevo_vencimiento <= anio_actual_vencimiento:
            return [], 0, "La nueva fecha no extiende el período de la CA"

        # Calcular años nuevos
        anios_nuevos = list(
            range(anio_actual_vencimiento + 1, anio_nuevo_vencimiento + 1))

        total_formularios = 0
        for anio in anios_nuevos:
            creados, _ = self.agregar_formularios_para_anio(anio)
            total_formularios += creados

        return (
            anios_nuevos,
            total_formularios,
            f"Se agregaron {len(anios_nuevos)} año(s) con {total_formularios} formularios"
        )

    class Meta:
        verbose_name = "Carrera Académica"
        verbose_name_plural = "Carreras Académicas"
        # Agregar índices
        indexes = [
            # Índice para filtrado por estado (usado en dashboard)
            models.Index(fields=["estado"], name="ca_estado_idx"),
            # Índice para ordenamiento por fecha de vencimiento
            models.Index(
                fields=["fecha_vencimiento_actual"], name="ca_venc_actual_idx"
            ),
            # Índice para búsqueda por expediente
            models.Index(fields=["numero_expediente"], name="ca_expediente_idx"),
            # Índice compuesto: estado + fecha (query común en dashboard)
            models.Index(
                fields=["estado", "fecha_vencimiento_actual"],
                name="ca_estado_fecha_idx",
            ),
            # Índice para búsquedas por cargo
            models.Index(fields=["cargo"], name="ca_cargo_idx"),
        ]
        ordering = ["fecha_vencimiento_actual"]

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
    objects = EvaluacionManager()

    def clean(self):
        """Validaciones a nivel de modelo."""
        super().clean()
        errors = {}

        # Validación 1: Los años evaluados deben estar dentro del rango de la CA
        if self.anios_evaluados:
            ca_start_year = self.carrera_academica.fecha_inicio.year
            ca_current_year = timezone.now().year

            for anio in self.anios_evaluados:
                if anio < ca_start_year:
                    errors["anios_evaluados"] = ValidationError(
                        f"El año {anio} es anterior al inicio de la Carrera Académica ({ca_start_year}).",
                        code="year_before_ca_start",
                    )
                    break

                if anio > ca_current_year:
                    errors["anios_evaluados"] = ValidationError(
                        f"El año {anio} es futuro. Solo se pueden evaluar años hasta {ca_current_year}.",
                        code="future_year",
                    )
                    break

        # Validación 2: No puede haber solapamiento de años con otras evaluaciones
        if self.anios_evaluados:
            otras_evaluaciones = Evaluacion.objects.filter(
                carrera_academica=self.carrera_academica
            ).exclude(pk=self.pk)

            for eval in otras_evaluaciones:
                solapamiento = set(self.anios_evaluados) & set(eval.anios_evaluados)
                if solapamiento:
                    errors["anios_evaluados"] = ValidationError(
                        f"Los años {solapamiento} ya fueron evaluados en la Evaluación N°{eval.numero_evaluacion}.",
                        code="overlapping_years",
                    )
                    break

        # Validación 3: Si está realizada, debe tener fecha
        if self.estado == "REA" and not self.fecha_evaluacion:
            errors["fecha_evaluacion"] = ValidationError(
                "Una evaluación realizada debe tener fecha y hora.",
                code="missing_evaluation_date",
            )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        """Override save para ejecutar validaciones."""
        self.full_clean()
        super().save(*args, **kwargs)

    class Meta:
        unique_together = ("carrera_academica", "numero_evaluacion")
        ordering = ["numero_evaluacion"]
        verbose_name = "Evaluación"
        verbose_name_plural = "Evaluaciones"
        # Agregar índices
        indexes = [
            # Índice para filtrar por CA
            models.Index(fields=["carrera_academica"], name="eval_ca_idx"),
            # Índice para filtrar por estado
            models.Index(fields=["estado"], name="eval_estado_idx"),
            # Índice para ordenar por fecha
            models.Index(fields=["fecha_evaluacion"], name="eval_fecha_idx"),
            # Índice compuesto: CA + número (query común)
            models.Index(
                fields=["carrera_academica", "numero_evaluacion"],
                name="eval_ca_num_idx",
            ),
        ]

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

    def clean(self):
        """Validaciones a nivel de modelo."""
        super().clean()
        errors = {}

        # Validación 1: Formularios anuales deben tener año correspondiente
        tipos_anuales = ["F04", "F05", "F06", "F07", "ENC", "F13"]
        if self.tipo_formulario in tipos_anuales and not self.anio_correspondiente:
            errors["anio_correspondiente"] = ValidationError(
                f"El formulario {self.tipo_formulario} debe tener un año correspondiente.",
                code="missing_year",
            )

        # Validación 2: El año correspondiente debe estar en el rango de la CA
        if self.anio_correspondiente:
            ca_start_year = self.carrera_academica.fecha_inicio.year
            ca_end_year = self.carrera_academica.fecha_vencimiento_original.year

            if not (ca_start_year <= self.anio_correspondiente <= ca_end_year):
                errors["anio_correspondiente"] = ValidationError(
                    f"El año {self.anio_correspondiente} está fuera del rango de la CA ({ca_start_year}-{ca_end_year}).",
                    code="year_out_of_range",
                )

        # Validación 3: Si está entregado, debe tener archivo
        if self.estado == "ENT" and not self.archivo:
            errors["archivo"] = ValidationError(
                "Un formulario entregado debe tener un archivo adjunto.",
                code="missing_file",
            )

        # Validación 4: Si está entregado, debe tener fecha de entrega
        if self.estado == "ENT" and not self.fecha_entrega:
            errors["fecha_entrega"] = ValidationError(
                "Un formulario entregado debe tener fecha de entrega.",
                code="missing_delivery_date",
            )

        # Validación 5: Si requiere PC, debe tener detalle
        if (
            self.tipo_formulario == "F08"
            and self.estado == "OBS"
            and not hasattr(self, "detalle_observacion")
        ):
            # Esta es solo una advertencia conceptual, F08 no tiene campo detalle_observacion
            pass

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        """Override save para ejecutar validaciones y auto-completar campos."""
        # Auto-completar fecha de entrega si se marca como entregado
        if self.estado == "ENT" and not self.fecha_entrega:
            self.fecha_entrega = timezone.now()

        self.full_clean()
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Formulario"
        verbose_name_plural = "Formularios"
        # Agregar índices
        indexes = [
            # Índice para filtrar por CA
            models.Index(fields=["carrera_academica"], name="form_ca_idx"),
            # Índice para filtrar por tipo
            models.Index(fields=["tipo_formulario"], name="form_tipo_idx"),
            # Índice para filtrar por estado
            models.Index(fields=["estado"], name="form_estado_idx"),
            # Índice para filtrar por año
            models.Index(fields=["anio_correspondiente"], name="form_anio_idx"),
            # Índice compuesto: CA + estado (query muy común)
            models.Index(
                fields=["carrera_academica", "estado"], name="form_ca_estado_idx"
            ),
            # Índice compuesto: CA + tipo + año (para separar formularios)
            models.Index(
                fields=["carrera_academica", "tipo_formulario", "anio_correspondiente"],
                name="form_ca_tipo_anio_idx",
            ),
        ]

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

    def clean(self):
        """Validaciones a nivel de modelo."""
        super().clean()
        errors = {}

        # Validación 1: Debe haber al menos un miembro interno
        if not self.miembro_interno_titular and not self.miembro_interno_suplente:
            errors["miembro_interno_titular"] = ValidationError(
                "Debe haber al menos un miembro interno (titular o suplente).",
                code="missing_internal_member",
            )

        # Validación 2: Titular y suplente no pueden ser la misma persona
        if (
            self.miembro_interno_titular
            and self.miembro_interno_suplente
            and self.miembro_interno_titular == self.miembro_interno_suplente
        ):
            errors["miembro_interno_suplente"] = ValidationError(
                "El miembro interno suplente no puede ser la misma persona que el titular.",
                code="duplicate_internal_member",
            )

        # Validación 3: Los veedores alumnos deben ser del claustro correcto
        # Esto ya está manejado con limit_choices_to en el modelo

        if errors:
            raise ValidationError(errors)

    def tiene_quorum_minimo(self):
        """Verifica si la junta tiene el quórum mínimo para funcionar."""
        miembros_count = 0

        if self.miembro_interno_titular or self.miembro_interno_suplente:
            miembros_count += 1

        miembros_count += self.miembros_externos_titulares.count()

        return miembros_count >= 3  # Mínimo 3 miembros

    class Meta:
        verbose_name = "Junta Evaluadora"
        verbose_name_plural = "Juntas Evaluadoras"
        # Agregar índices
        indexes = [
            # Índice para búsqueda por CA (relación 1-1)
            models.Index(fields=["carrera_academica"], name="junta_ca_idx"),
        ]

    def __str__(self):
        return f"Junta para {self.carrera_academica}"


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
