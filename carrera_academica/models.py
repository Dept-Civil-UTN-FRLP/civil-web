# carrera_academica/models.py
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.utils import timezone
from django.utils.text import slugify

from planta_docente.models import Cargo, Docente, Resolucion, Asignatura

from .managers import CarreraAcademicaManager, EvaluacionManager



def get_ca_upload_path(instance, filename):
    """
    Genera una ruta única y descriptiva para los archivos de CA.
    Formato: ca/{apellido-nombre}/{ca_id}-{tipo}-{año}-{apellido}.ext
    """
    try:
        docente = instance.carrera_academica.cargo.docente
    except AttributeError:
        docente = instance.cargo.docente

    nombre_completo = f"{docente.apellido} {docente.nombre}"
    docente_slug = slugify(nombre_completo)

    # Extensión del archivo original
    import os
    extension = os.path.splitext(filename)[1]

    # ID de la CA
    ca_id = instance.carrera_academica.pk

    # Tipo de formulario
    tipo_form = instance.tipo_formulario

    # Año si aplica
    año_str = f"-{instance.anio_correspondiente}" if instance.anio_correspondiente else ""

    # Apellido
    apellido = docente.apellido

    # Construir nombre: {ca_id}-{tipo}-{año}-{apellido}.ext
    new_filename = f"{ca_id}-{tipo_form}{año_str}-{apellido}{extension}"

    # Devuelve: ca/apellido-nombre/{ca_id}-F04-2025-Ronconi.pdf
    return f"private/ca/{docente_slug}/{new_filename}"


class CarreraAcademica(models.Model):
    ESTADO_CHOICES = [
        ("ACT", "Activa"),
        ("STB", "En Standby (Licencia)"),
        ("ARCH", "Archivada"),
        ("FIN", "Finalizada"),
        ("VEN", "Vencida"),
    ]
    
    RESULTADO_CIERRE_CHOICES = [
        ('aprobada_redesigna', 'Aprobada - Acepta Redesignación'),
        ('aprobada_rechaza', 'Aprobada - Rechaza Redesignación'),
        ('renuncia', 'Renuncia'),
        ('no_aprobada', 'No Aprobada'),
        ('jubilacion', 'Jubilación'),
    ]

    MOTIVO_ARCHIVO_CHOICES = [
        ('jubilacion_cercana', 'Jubilación Cercana'),
        ('renuncia_condicional', 'Renuncia Condicional'),
        ('administrativo', 'Motivo Administrativo'),
        ('otro', 'Otro'),
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
    estado = models.CharField(max_length=4, choices=ESTADO_CHOICES, default="ACT")
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
    motivo_archivo = models.CharField(
        max_length=30,
        choices=MOTIVO_ARCHIVO_CHOICES,
        null=True,
        blank=True,
        verbose_name="Motivo de Archivo",
        help_text="Motivo por el cual se archivó la CA sin workflow formal de cierre"
    )

    fecha_archivo = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Fecha de Archivo"
    )

    observaciones_archivo = models.TextField(
        blank=True,
        verbose_name="Observaciones del Archivo"
    )
    ca_anterior = models.OneToOneField(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ca_siguiente',
        verbose_name="CA Anterior",
        help_text="Expediente de CA del cual este es continuación"
    )
    anios_pausados = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Años Pausados",
        help_text="Lista de años que no se evaluarán. Formato: [{'anio': 2022, 'motivo': '...', 'fecha': '2022-03-15', 'usuario': 'admin'}]"
    )
    resultado_cierre = models.CharField(
        max_length=30,
        choices=RESULTADO_CIERRE_CHOICES,
        null=True,
        blank=True,
        verbose_name="Resultado del Cierre",
        help_text="Resultado al finalizar la Carrera Académica"
    )
    observaciones_cierre = models.TextField(
        blank=True,
        verbose_name="Observaciones del Cierre"
    )
    
    jurado = models.ForeignKey(
        'Jurado',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='carreras_academicas',
        verbose_name="Jurado Evaluador",
        help_text="Jurado asignado para la evaluación de esta CA"
    )
    
    fecha_ultima_notificacion = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Fecha de Última Notificación",
        help_text="Última vez que se envió una notificación al docente sobre documentación pendiente",
    )
    cantidad_notificaciones = models.PositiveIntegerField(
        default=0,
        verbose_name="Cantidad de Notificaciones",
        help_text="Número de notificaciones enviadas al docente",
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
    
        # Validación 5: La duración debe ser al menos de 2 años
        if self.fecha_inicio and self.fecha_vencimiento_original:
            duracion = self.fecha_vencimiento_original - self.fecha_inicio
            if duracion.days < 730:  # 2 años = ~730 días
                errors["fecha_vencimiento_original"] = ValidationError(
                    "La Carrera Académica debe tener una duración mínima de 2 años.",
                    code="duration_too_short",
                )
    
        # Validación 6: Si está finalizada, debe tener fecha de finalización
        if self.estado == "FIN" and not self.fecha_finalizacion:
            errors["fecha_finalizacion"] = ValidationError(
                "Una Carrera Académica finalizada debe tener fecha de finalización.",
                code="missing_finalization_date",
            )
    
        # Validación 7: No puede haber otra CA activa para el mismo cargo
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

        if anio < start_year:
            return 0, f"El año {anio} es anterior al inicio de la CA ({start_year})"

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
        
    def obtener_cadena_ca(self):
        """
        Obtiene la cadena completa de CAs (anteriores y siguiente).
        Retorna: {'anteriores': [cas], 'siguiente': ca}
        """
        cadena = {
            'anteriores': [],
            'siguiente': None
        }

        # Buscar todas las CA anteriores
        ca_actual = self
        while ca_actual.ca_anterior:
            cadena['anteriores'].insert(0, ca_actual.ca_anterior)
            ca_actual = ca_actual.ca_anterior

        # Buscar CA siguiente
        if hasattr(self, 'ca_siguiente') and self.ca_siguiente:
            cadena['siguiente'] = self.ca_siguiente

        return cadena

    def get_ca_activa_del_docente(self):
        """
        Retorna la CA activa actual del docente (la más reciente en la cadena).
        """
        # Si esta CA tiene siguiente, seguir la cadena
        if hasattr(self, 'ca_siguiente') and self.ca_siguiente:
            return self.ca_siguiente.get_ca_activa_del_docente()

        # Si no tiene siguiente, esta es la última
        return self if self.estado == 'ACT' else None

    def get_info_continuidad_ca(self):
        """
        Retorna información detallada sobre la continuidad de las CA.
        """
        info = {
            'tiene_anterior': self.ca_anterior is not None,
            'tiene_siguiente': hasattr(self, 'ca_siguiente') and self.ca_siguiente is not None,
            'es_activa': self.estado == 'ACT',
            'numero_en_cadena': 1,
        }

        # Contar posición en la cadena
        ca_actual = self
        while ca_actual.ca_anterior:
            info['numero_en_cadena'] += 1
            ca_actual = ca_actual.ca_anterior

        if self.ca_anterior:
            info['ca_anterior'] = {
                'id': self.ca_anterior.pk,
                'numero_expediente': self.ca_anterior.numero_expediente,
                'periodo': f"{self.ca_anterior.fecha_inicio.strftime('%Y')} - {self.ca_anterior.fecha_vencimiento_original.strftime('%Y')}",
                'resultado': self.ca_anterior.get_resultado_cierre_display() if self.ca_anterior.resultado_cierre else None,
            }

        if hasattr(self, 'ca_siguiente') and self.ca_siguiente:
            info['ca_siguiente'] = {
                'id': self.ca_siguiente.pk,
                'numero_expediente': self.ca_siguiente.numero_expediente,
                'periodo': f"{self.ca_siguiente.fecha_inicio.strftime('%Y')} - {self.ca_siguiente.fecha_vencimiento_original.strftime('%Y')}",
                'estado': self.ca_siguiente.get_estado_display(),
            }

        if self.resultado_cierre:
            info['cierre'] = {
                'resultado': self.get_resultado_cierre_display(),
                'observaciones': self.observaciones_cierre,
                'fecha': self.fecha_finalizacion,
            }

        return info

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
    CALIFICACION_CHOICES = [
        ("INS", "Insuficiente"),
        ("REG", "Regular"),
        ("BUE", "Bueno"),
        ("MBU", "Muy Bueno"),
        ("EXC", "Excelente"),
    ]
    carrera_academica = models.ForeignKey(
        CarreraAcademica, on_delete=models.CASCADE, related_name="evaluaciones"
    )
    numero_evaluacion = models.PositiveIntegerField()
    fecha_iniciada = models.DateField(default=timezone.now)
    anios_evaluados = models.JSONField(
        default=list,
        help_text="Lista de años que cubre esta evaluación, ej: [2022, 2023]",
    )
    fecha_evaluacion = models.DateTimeField(
        verbose_name="Fecha y Hora de la Evaluación", null=True, blank=True
    )
    estado = models.CharField(max_length=3, choices=ESTADO_EVAL_CHOICES, default="PRO")
    calificacion = models.CharField(
        max_length=3, choices=CALIFICACION_CHOICES, null=True, blank=True
    )
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
    archivo = models.FileField(upload_to=get_ca_upload_path, blank=True, null=True, max_length=500)
    comprimido = models.BooleanField(default=False)
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


class MembreteAnual(models.Model):
    anio = models.IntegerField(
        unique=True, help_text="Año al que corresponde este membrete"
    )
    logo = models.ImageField(upload_to="private/membretes/logos/")
    frase = models.CharField(
        max_length=255, help_text="Frase del encabezado para este año"
    )

    def __str__(self):
        return f"Membrete para el año {self.anio}"

    class Meta:
        verbose_name = "Membrete Anual"
        verbose_name_plural = "Membretes Anuales"


class TipoFormulario(models.Model):
    codigo = models.CharField(max_length=4, unique=True)
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True)

    class Meta:
        verbose_name = "Tipo de Formulario"
        verbose_name_plural = "Tipos de Formulario"
        ordering = ["codigo"]

    def __str__(self):
        return f"{self.codigo} – {self.nombre}"


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
    archivo = models.FileField(upload_to="private/plantillas_documentos/")
    descripcion = models.CharField(max_length=255, blank=True)

    class Meta:
        # Nos aseguramos de que solo haya una plantilla F04 para el 2024, por ejemplo.
        verbose_name = "Plantilla de Documento"
        verbose_name_plural = "Plantillas de Documentos"

    def __str__(self):
        return f"Plantilla para {self.tipo_formulario}"


class VeedorGraduado(models.Model):
    """Graduado que actúa como veedor en evaluaciones de CA."""
    apellido = models.CharField(max_length=100)
    nombre = models.CharField(max_length=100)
    email = models.EmailField()
    telefono = models.CharField(max_length=20, blank=True)
    titulo = models.CharField(max_length=200, help_text="Ej: Ingeniero Civil")
    año_egreso = models.IntegerField(null=True, blank=True)
    dni = models.IntegerField(
        null=True, blank=True, unique=True,
        verbose_name="DNI",
        help_text="Usado para verificar identidad en el Portal de Jurados",
    )

    def __str__(self):
        return f"{self.apellido}, {self.nombre}"

    class Meta:
        verbose_name = "Veedor Graduado"
        verbose_name_plural = "Veedores Graduados"
        ordering = ['apellido', 'nombre']


class VeedorEstudiante(models.Model):
    """Estudiante que actúa como veedor en evaluaciones de CA."""
    apellido = models.CharField(max_length=100)
    nombre = models.CharField(max_length=100)
    email = models.EmailField()
    legajo = models.CharField(max_length=20)
    dni = models.IntegerField(
        null=True, blank=True, unique=True,
        verbose_name="DNI",
        help_text="Usado para verificar identidad en el Portal de Jurados",
    )

    def __str__(self):
        return f"{self.apellido}, {self.nombre} (Leg. {self.legajo})"

    class Meta:
        verbose_name = "Veedor Estudiante"
        verbose_name_plural = "Veedores Estudiantes"
        ordering = ['apellido', 'nombre']


class Jurado(models.Model):
    """Jurado evaluador reutilizable para Carreras Académicas."""
    nombre = models.CharField(
        max_length=300,
        editable=False,
        help_text="Se genera automáticamente con los apellidos de los 3 titulares"
    )
    departamento = models.CharField(
        max_length=15,
        choices=Asignatura.DEPTO_CHOICES,
        help_text="Departamento al que pertenece este jurado"
    )

    # PROFESOR 1: Interno obligatorio (Docente de UTN-FRLP)
    profesor_titular_1 = models.ForeignKey(
        'planta_docente.Docente',
        on_delete=models.PROTECT,
        related_name='jurados_como_titular_1',
        verbose_name="Profesor Titular 1 (Interno)",
        help_text="Debe ser docente de la planta de UTN-FRLP"
    )
    profesor_suplente_1 = models.ForeignKey(
        'planta_docente.Docente',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='jurados_como_suplente_1',
        verbose_name="Suplente 1"
    )

    # PROFESOR 2: Externo (puede ser UTN otra regional u otra universidad)
    profesor_titular_2 = models.ForeignKey(
        'JuradoExterno',
        on_delete=models.PROTECT,
        related_name='jurados_como_titular_2',
        verbose_name="Profesor Titular 2 (Externo)",
        help_text="Puede ser de otra regional UTN u otra universidad"
    )
    profesor_suplente_2 = models.ForeignKey(
        'JuradoExterno',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='jurados_como_suplente_2',
        verbose_name="Suplente 2"
    )

    # PROFESOR 3: Externo obligatorio de Universidad Nacional (no UTN)
    profesor_titular_3 = models.ForeignKey(
        'JuradoExterno',
        on_delete=models.PROTECT,
        related_name='jurados_como_titular_3',
        verbose_name="Profesor Titular 3 (Universidad Externa)",
        help_text="Debe ser de otra Universidad Nacional (UBA, UNLP, etc.)"
    )
    profesor_suplente_3 = models.ForeignKey(
        'JuradoExterno',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='jurados_como_suplente_3',
        verbose_name="Suplente 3"
    )

    # Veedores (sin cambios)
    veedor_graduado_titular = models.ForeignKey(
        'VeedorGraduado',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='jurados_como_graduado_titular',
        verbose_name="Veedor Graduado Titular"
    )
    veedor_graduado_suplente = models.ForeignKey(
        'VeedorGraduado',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='jurados_como_graduado_suplente',
        verbose_name="Veedor Graduado Suplente"
    )
    veedor_estudiante_titular = models.ForeignKey(
        'VeedorEstudiante',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='jurados_como_estudiante_titular',
        verbose_name="Veedor Estudiante Titular"
    )
    veedor_estudiante_suplente = models.ForeignKey(
        'VeedorEstudiante',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='jurados_como_estudiante_suplente',
        verbose_name="Veedor Estudiante Suplente"
    )

    notas = models.TextField(blank=True, verbose_name="Notas")
    activo = models.BooleanField(default=True, verbose_name="Activo")
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Jurado"
        verbose_name_plural = "Jurados"
        ordering = ['-fecha_creacion']

    def __str__(self):
        return self.nombre

    def save(self, *args, **kwargs):
        # Auto-generar nombre con apellidos de los 3 titulares
        if not self.nombre or self.nombre == '':
            apellidos = []
            if self.profesor_titular_1:
                apellidos.append(self.profesor_titular_1.apellido)
            if self.profesor_titular_2:
                apellidos.append(self.profesor_titular_2.apellido)
            if self.profesor_titular_3:
                apellidos.append(self.profesor_titular_3.apellido)

            self.nombre = ' - '.join(apellidos) if apellidos else 'Jurado sin nombre'

        super().save(*args, **kwargs)

    def clean(self):
        """Validaciones según ordenanza."""
        from django.core.exceptions import ValidationError

        errors = {}

        # Validar que profesor titular 1 (interno) exista
        if not getattr(self, 'profesor_titular_1_id', None):
            errors['profesor_titular_1'] = 'Profesor Titular 1 (Interno) es requerido'

        # Validar que profesor titular 2 (externo) exista
        if not getattr(self, 'profesor_titular_2_id', None):
            errors['profesor_titular_2'] = 'Profesor Titular 2 (Externo) es requerido'

        # Validar que profesor titular 3 (externo no-UTN) exista
        if not getattr(self, 'profesor_titular_3_id', None):
            errors['profesor_titular_3'] = 'Profesor Titular 3 (Universidad Externa) es requerido'

        # Validar que profesor 3 sea de universidad externa (no UTN)
        profesor_3 = getattr(self, 'profesor_titular_3', None)
        if profesor_3 and not profesor_3.es_universidad_externa():
            errors['profesor_titular_3'] = 'El Profesor Titular 3 debe ser de una Universidad Nacional externa (no UTN)'

        # Validar distribución: debe haber al menos 1 profesor de universidad NO UTN
        externos_no_utn = []
        prof_2 = getattr(self, 'profesor_titular_2', None)
        prof_3 = getattr(self, 'profesor_titular_3', None)
        prof_sup_2 = getattr(self, 'profesor_suplente_2', None)
        prof_sup_3 = getattr(self, 'profesor_suplente_3', None)

        if prof_2 and prof_2.es_universidad_externa():
            externos_no_utn.append(prof_2)
        if prof_3 and prof_3.es_universidad_externa():
            externos_no_utn.append(prof_3)
        if prof_sup_2 and prof_sup_2.es_universidad_externa():
            externos_no_utn.append(prof_sup_2)
        if prof_sup_3 and prof_sup_3.es_universidad_externa():
            externos_no_utn.append(prof_sup_3)

        if not externos_no_utn:
            errors['profesor_titular_2'] = 'Debe haber al menos un profesor de una Universidad Nacional (no UTN)'

        if errors:
            raise ValidationError(errors)

    def get_cantidad_cas(self):
        """Retorna cantidad de CAs asignadas a este jurado."""
        return self.carreras_academicas.count()


class Universidad(models.Model):
    """Universidades e instituciones académicas."""
    sigla = models.CharField(
        max_length=20,
        unique=True,
        help_text="Ej: UTN, UBA, UNLP, UNC, etc."
    )
    nombre_completo = models.CharField(max_length=200)

    # Para UTN, especificar regional
    es_utn = models.BooleanField(default=False)
    regional = models.CharField(
        max_length=100,
        blank=True,
        help_text="Ej: FRLP, FRC, FRA, etc. Solo para UTN"
    )

    class Meta:
        verbose_name = "Universidad"
        verbose_name_plural = "Universidades"
        ordering = ['sigla']

    def __str__(self):
        if self.es_utn and self.regional:
            return f"{self.sigla} - {self.regional}"
        return self.sigla


class JuradoExterno(models.Model):
    """Profesores externos a la planta docente de UTN-FRLP."""
    apellido = models.CharField(max_length=100)
    nombre = models.CharField(max_length=100)
    email = models.EmailField()
    telefono = models.CharField(max_length=20, blank=True)
    dni = models.IntegerField(
        null=True, blank=True, unique=True,
        verbose_name="DNI",
        help_text="Usado para verificar identidad en el Portal de Jurados",
    )

    # Origen institucional
    universidad = models.ForeignKey(
        Universidad,
        on_delete=models.PROTECT,
        related_name='jurados_externos'
    )

    # Características del cargo
    CATEGORIA_CHOICES = [
        ('titular', 'Profesor Titular'),
        ('asociado', 'Profesor Asociado'),
        ('adjunto', 'Profesor Adjunto'),
    ]
    categoria = models.CharField(max_length=20, choices=CATEGORIA_CHOICES)
    es_investigador = models.BooleanField(
        default=False,
        help_text="¿Es Docente Investigador?"
    )
    es_jubilado = models.BooleanField(default=False)

    # Resolución que avala el cargo
    archivo_resolucion = models.FileField(
        upload_to='jurados_externos/resoluciones/',
        blank=True,
        null=True,
        help_text="PDF de la resolución que avala el cargo"
    )

    notas = models.TextField(blank=True)
    activo = models.BooleanField(default=True)
    fecha_alta = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Jurado Externo"
        verbose_name_plural = "Jurados Externos"
        ordering = ['apellido', 'nombre']

    def __str__(self):
        return f"{self.apellido}, {self.nombre} ({self.universidad})"

    def es_utn_otra_regional(self):
        """Verifica si es de UTN pero no de FRLP."""
        return self.universidad.es_utn and self.universidad.regional != 'FRLP'

    def es_universidad_externa(self):
        """Verifica si es de universidad externa (no UTN)."""
        return not self.universidad.es_utn


class TokenPortalJurado(models.Model):
    """
    Link de acceso personal al Portal de Jurados para un ocupante de slot de `Jurado`.
    Se guarda solo el hash (sha256) del secreto — el valor crudo solo existe en el
    momento de creación (para incluirlo en el link del email) y nunca se persiste.
    """

    TIPO_PERSONA_CHOICES = [
        ("docente", "Docente (interno)"),
        ("jurado_externo", "Jurado Externo"),
        ("veedor_graduado", "Veedor Graduado"),
        ("veedor_estudiante", "Veedor Estudiante"),
    ]

    tipo_persona = models.CharField(max_length=20, choices=TIPO_PERSONA_CHOICES)
    persona_id = models.PositiveIntegerField()
    token_hash = models.CharField(max_length=64, unique=True, db_index=True)
    creado = models.DateTimeField(auto_now_add=True)
    creado_por = models.ForeignKey(
        "auth.User", on_delete=models.SET_NULL, null=True, blank=True
    )
    expira = models.DateTimeField()
    revocado = models.BooleanField(default=False)
    fecha_revocado = models.DateTimeField(null=True, blank=True)
    ultimo_uso = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Token Portal de Jurado"
        verbose_name_plural = "Tokens Portal de Jurados"
        indexes = [
            models.Index(fields=["tipo_persona", "persona_id"]),
        ]

    def __str__(self):
        return f"Token {self.tipo_persona}#{self.persona_id} ({'revocado' if self.revocado else 'activo'})"

    def esta_vigente(self):
        return not self.revocado and self.expira > timezone.now()


class TokenPortalConcursos(models.Model):
    """
    Link + contraseña para compartir el expediente completo de UNA CarreraAcademica
    puntual con una casilla institucional (ej. Concursos) que no es una persona con
    DNI en el sistema. La contraseña la elige el staff al generar el link (no es
    parte del mail que se manda -- se comunica por otro medio), y se guarda solo su
    hash, igual que el token.
    """

    carrera_academica = models.ForeignKey(
        CarreraAcademica, on_delete=models.CASCADE, related_name="tokens_concursos"
    )
    token_hash = models.CharField(max_length=64, unique=True, db_index=True)
    password_hash = models.CharField(max_length=128)
    creado = models.DateTimeField(auto_now_add=True)
    creado_por = models.ForeignKey(
        "auth.User", on_delete=models.SET_NULL, null=True, blank=True
    )
    expira = models.DateTimeField()
    revocado = models.BooleanField(default=False)
    ultimo_uso = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Token Portal de Concursos"
        verbose_name_plural = "Tokens Portal de Concursos"
        indexes = [
            models.Index(fields=["carrera_academica"]),
        ]

    def __str__(self):
        return f"Token concursos CA {self.carrera_academica_id} ({'revocado' if self.revocado else 'activo'})"


class AccesoPortalJurado(models.Model):
    """
    Auditoría de accesos al Portal de Jurados: quién, cuándo, qué vio/descargó,
    con qué resultado. La identidad es polimórfica (no hay una tabla única de
    "personas"), por eso se guarda tipo_persona + persona_id en vez de una FK.
    """

    TIPO_PERSONA_CHOICES = TokenPortalJurado.TIPO_PERSONA_CHOICES

    ACCION_CHOICES = [
        ("link_ok", "Link verificado correctamente"),
        ("link_fail_token", "Token inválido/expirado/revocado"),
        ("link_fail_dni", "DNI incorrecto"),
        ("link_fail_password", "Contraseña incorrecta"),
        ("vista_dashboard", "Vio listado de CAs"),
        ("vista_detalle_ca", "Vio el detalle de un expediente"),
        ("vista_documento", "Vio/descargó un documento"),
        ("descarga_expediente", "Descargó expediente completo"),
    ]

    tipo_persona = models.CharField(
        max_length=20, choices=TIPO_PERSONA_CHOICES, blank=True
    )
    persona_id = models.PositiveIntegerField(null=True, blank=True)
    token = models.ForeignKey(
        TokenPortalJurado,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="accesos",
    )
    token_concursos = models.ForeignKey(
        "TokenPortalConcursos",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="accesos",
        help_text="Set en vez de 'token' cuando el acceso es del Portal de Concursos (una casilla, no una persona).",
    )
    carrera_academica = models.ForeignKey(
        CarreraAcademica,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="accesos_portal_jurado",
    )
    formulario = models.ForeignKey(
        Formulario, on_delete=models.SET_NULL, null=True, blank=True
    )
    accion = models.CharField(max_length=25, choices=ACCION_CHOICES)
    exitoso = models.BooleanField(default=True)
    detalle = models.CharField(max_length=255, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=300, blank=True)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Acceso Portal de Jurado"
        verbose_name_plural = "Accesos Portal de Jurados"
        ordering = ["-fecha"]
        indexes = [
            models.Index(fields=["tipo_persona", "persona_id", "-fecha"]),
            models.Index(fields=["carrera_academica", "-fecha"]),
        ]

    def __str__(self):
        quien = f"{self.tipo_persona}#{self.persona_id}" if self.tipo_persona else "Concursos"
        return f"{self.get_accion_display()} - {quien} ({self.fecha:%d/%m/%Y %H:%M})"


@receiver(post_delete, sender=Formulario)
def borrar_archivo_al_eliminar_formulario(sender, instance, **kwargs):
    if instance.archivo:
        instance.archivo.delete(save=False)
