from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.utils import timezone
from django.utils.text import slugify

from .managers import CargoManager, DocenteManager
from .validators import validar_extension_planificacion, validar_tamaño_planificacion


# Create your models here.

def get_programa_upload_path(instance, filename):
    import os
    extension = os.path.splitext(filename)[1]
    nombre = slugify(instance.nombre)
    return f"private/programas/{timezone.now().year}/{nombre}{extension}"


class Area(models.Model):
    nombre = models.CharField(max_length=50)

    def save(self, *args, **kwargs):
        self.nombre = self.nombre.lower()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.nombre.title()


class Bloque(models.Model):
    nombre = models.CharField(max_length=50)

    def save(self, *args, **kwargs):
        self.nombre = self.nombre.lower()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.nombre.title()


class Asignatura(models.Model):
    # <<< CORRECCIÓN: CHOICES deben ser listas de tuplas
    DEPTO_CHOICES = [
        ("civil", "Dpto. de Civil"),
        ("electrica", "Dpto. de Electrica"),
        ("industrial", "Dpto. de Industrial"),
        ("mecanica", "Dpto. de Mecanica"),
        ("quimica", "Dpto. de Quimica"),
        ("sistema", "Dpto. de Sistema de Informacion"),
        ("basicas", "Dpto de Ciencias Basicas"),
    ]
    ESPECIALIDAD_CHOICES = [
        ("civil", "Ing. Civil"),
        ("electrica", "Ing. Electrica"),
        ("industrial", "Ing. Industrial"),
        ("mecanica", "Ing. Mecanica"),
        ("quimica", "Ing. Quimica"),
        ("sistema", "Ing. en Sistema de Informacion"),
    ]
    DICTADO_CHOICES = [
        ("a", "Anual"),
        ("c1", "1er. Cuatrimestre"),
        ("c2", "2do. Cuatrimestre"),
    ]
    NIVEL_CHOICES = [
        ("i", "I"),
        ("ii", "II"),
        ("iii", "III"),
        ("iv", "IV"),
        ("v", "V"),
        ("vi", "VI"),
        ("-", "-"),
    ]
    TIPO_CHOICES = [
        ('asignatura', 'Asignatura'),
        ('laboratorio', 'Laboratorio'),
        ('grupo', 'Grupo'),
        ('centro', 'Centro'),
        ('area', 'Área'),
    ]

    nombre = models.CharField(max_length=50)
    tipo = models.CharField(
        choices=TIPO_CHOICES,
        max_length=11,
        default='asignatura',
        verbose_name="Tipo"
    )
    nivel = models.CharField(choices=NIVEL_CHOICES, max_length=3)
    puntaje = models.IntegerField(default=0)
    departamento = models.CharField(choices=DEPTO_CHOICES, max_length=11)
    especialidad = models.CharField(choices=ESPECIALIDAD_CHOICES, max_length=11)
    obligatoria = models.BooleanField(default=True)
    area = models.ManyToManyField("Area", related_name="area_asignatura", blank=True)
    bloque = models.ManyToManyField(
        "Bloque", related_name="bloque_asignatura", blank=True
    )
    hora_semanal = models.PositiveIntegerField()
    hora_total = models.PositiveIntegerField()
    dictado = models.CharField(choices=DICTADO_CHOICES, max_length=2)
    numero_orden = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Número de Orden",
        help_text="Número de orden en el plan de estudios (ej: 16)"
    )
    competencias = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Competencias",
        help_text="Competencias específicas separadas por guiones (ej: CE01-CE03-CE08)"
    )
    objetivos = models.TextField(
        blank=True,
        verbose_name="Objetivos",
        help_text="Objetivos de la asignatura (uno por línea)"
    )
    contenidos_minimos = models.TextField(
        blank=True,
        verbose_name="Contenidos Mínimos",
        help_text="Contenidos mínimos de la asignatura"
    )
    numero_comisiones = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Número de Comisiones",
        help_text="Cantidad de comisiones en las que se divide la asignatura"
    )
    numero_estudiantes = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Número de Estudiantes",
        help_text="Promedio histórico de estudiantes en la asignatura"
    )
    bibliografia_basica = models.TextField(
        blank=True,
        verbose_name="Bibliografía Básica",
        help_text="Formato IEEE. Ejemplo: [1] A. Autor, \"Título del libro\", Editorial, Año. (un ítem por línea)"
    )
    
    bibliografia_complementaria = models.TextField(
        blank=True,
        verbose_name="Bibliografía Complementaria",
        help_text="Formato IEEE. Ejemplo: [1] A. Autor, \"Título del libro\", Editorial, Año. (un ítem por línea)"
    )
    programa = models.FileField(
        upload_to=get_programa_upload_path,
        blank=True,
        null=True,
        verbose_name="Programa",
        help_text="Archivo PDF del programa de la asignatura"
    )

    def __str__(self) -> str:
        return self.nombre.title()

    def save(self, *args, **kwargs):
        self.nombre = self.nombre.lower()
        super().save(*args, **kwargs)

    class Meta:
        ordering = ["-obligatoria", "nivel"]
        verbose_name = "Asignatura"
        verbose_name_plural = "Asignaturas"
        # Agregar índices
        indexes = [
            # Índice para filtrar por nivel
            models.Index(fields=["nivel"], name="asig_nivel_idx"),
            # Índice para filtrar por departamento
            models.Index(fields=["departamento"], name="asig_depto_idx"),
            # Índice para filtrar por especialidad
            models.Index(fields=["especialidad"], name="asig_especialidad_idx"),
            # Índice para ordenar: obligatoria + nivel
            models.Index(fields=["-obligatoria", "nivel"], name="asig_oblig_nivel_idx"),
        ]


class Docente(models.Model):
    nombre = models.CharField(max_length=50)
    apellido = models.CharField(max_length=50)
    documento = models.IntegerField(unique=True)
    legajo = models.IntegerField(unique=True)
    fecha_nacimiento = models.DateField(default="1900-01-01")
    objects = DocenteManager()
    jubilado = models.BooleanField(
        default=False,
        verbose_name="Jubilado",
        help_text="Marcar si el docente está jubilado. Se excluirá de reportes de planta activa.",
    )
    fecha_jubilacion = models.DateField(
        null=True,
        blank=True,
        verbose_name="Fecha de Jubilación",
        help_text="Fecha en que el docente se jubiló",
    )

    def clean(self):
        """Validaciones a nivel de modelo."""
        super().clean()
        errors = {}

        # Validación 1: Fecha de nacimiento no puede ser futura
        if self.fecha_nacimiento and self.fecha_nacimiento > timezone.now().date():
            errors["fecha_nacimiento"] = ValidationError(
                "La fecha de nacimiento no puede ser futura.", code="future_birth_date"
            )

        # Validación 2: El docente debe tener al menos 18 años
        if self.fecha_nacimiento:
            today = timezone.now().date()
            age = (
                today.year
                - self.fecha_nacimiento.year
                - (
                    (today.month, today.day)
                    < (self.fecha_nacimiento.month, self.fecha_nacimiento.day)
                )
            )
            if age < 18:
                errors["fecha_nacimiento"] = ValidationError(
                    "El docente debe tener al menos 18 años.", code="underage"
                )
            # Si está jubilado, debe tener fecha
            if self.jubilado and not self.fecha_jubilacion:
                errors["fecha_jubilacion"] = ValidationError(
                    "Si marca como jubilado, debe especificar la fecha de jubilación.",
                    code="missing_jubilacion_date",
                )

            # Fecha de jubilación no puede ser futura
            if self.fecha_jubilacion and self.fecha_jubilacion > timezone.now().date():
                errors["fecha_jubilacion"] = ValidationError(
                    "La fecha de jubilación no puede ser futura.",
                    code="future_jubilacion_date",
                )

        if errors:
            raise ValidationError(errors)
    
    @property
    def email(self):
        """
        Retorna el email principal del docente, o el primero disponible.
        
        Returns:
            str|None: Email del docente o None si no tiene emails configurados
        
        Example:
            >>> docente = Docente.objects.get(pk=1)
            >>> print(docente.email)
            'jperez@frlp.utn.edu.ar'
        """
        # Intentar obtener email principal
        email_principal = self.correos.filter(principal=True).first()
        if email_principal:
            return email_principal.email
        
        # Si no hay principal, retornar el primero disponible
        primer_email = self.correos.first()
        if primer_email:
            return primer_email.email
        
        return None
    
    @property
    def tiene_email(self):
        """
        Indica si el docente tiene al menos un email configurado.
        
        Returns:
            bool: True si tiene emails, False si no
        
        Example:
            >>> if docente.tiene_email:
            >>>     enviar_notificacion(docente.email)
        """
        return self.correos.exists()
    
    def save(self, *args, **kwargs):
        """Override save para ejecutar validaciones."""
        self.full_clean()
        super().save(*args, **kwargs)
        
    def get_full_name(self):
        """
        Retorna el nombre completo del docente en formato: APELLIDO, Nombre.
        
        Returns:
            str: Nombre completo formateado
        
        Example:
            >>> docente.get_full_name()
            'PÉREZ, Juan Carlos'
        """
        if self.apellido and self.nombre:
            return f"{self.apellido.upper()}, {self.nombre.title()}"
        elif self.apellido:
            return self.apellido.upper()
        elif self.nombre:
            return self.nombre.title()
        return "Sin nombre"
    
    def get_short_name(self):
        """
        Retorna solo el apellido del docente.
        
        Returns:
            str: Apellido en mayúsculas
        
        Example:
            >>> docente.get_short_name()
            'PÉREZ'
        """
        return self.apellido.upper() if self.apellido else "Sin apellido"
    
    class Meta:
        verbose_name = "Docente"
        verbose_name_plural = "Docentes"
        # Agregar índices
        indexes = [
            models.Index(fields=["legajo"], name="doc_legajo_idx"),
            models.Index(fields=["documento"], name="doc_documento_idx"),
            models.Index(fields=["apellido"], name="doc_apellido_idx"),
            models.Index(fields=["apellido", "nombre"], name="doc_apellido_nombre_idx"),
            models.Index(fields=["jubilado"], name="doc_jubilado_idx"),
        ]

    def __str__(self) -> str:
        sufijo = " (JUBILADO)" if self.jubilado else ""
        return self.get_full_name() + sufijo


class Correo(models.Model):
    email = models.EmailField()
    principal = models.BooleanField(default=True)
    docente = models.ForeignKey(
        "Docente", related_name="correos", on_delete=models.CASCADE
    )

    def __str__(self) -> str:
        return f"{self.docente.apellido.upper()}, {self.docente.nombre.title()} <{self.email.lower()}>"

    class Meta:
        verbose_name = "Correo"
        verbose_name_plural = "Correos"
        # Agregar índices
        indexes = [
            # Índice para filtrar por docente
            models.Index(fields=["docente"], name="correo_docente_idx"),
            # Índice compuesto: docente + principal (query muy común)
            models.Index(
                fields=["docente", "principal"], name="correo_doc_principal_idx"
            ),
        ]

    def save(self, *args, **kwargs):
        self.email = self.email.lower()
        super().save(*args, **kwargs)


@receiver(pre_save, sender=Correo)
def ensure_only_one_principal_email(sender, instance, **kwargs):
    if instance.principal:
        Correo.objects.filter(docente=instance.docente, principal=True).exclude(
            id=instance.id
        ).update(principal=False)


class Cargo(models.Model):
    CARACTER_CHOICES = [
        ("ord", "Ordinario"),
        ("reg", "Regular"),
        ("int", "Interino"),
        ("adh", "Ad-Honorem"),
    ]
    CATEGORIA_CHOICES = [
        ("tit", "Titular"),
        ("aso", "Asociado"),
        ("adj", "Adjunto"),
        ("jtp", "Jefe de Trabajos Practicos"),
        ("atp1", "Ayudante de 1ra"),
        ("atp2", "Ayudante de 2da"),
        ("ads", "Adscripto"),
    ]
    DEDICACION_CHOICES = [
        ("ms", "0.5 Simple"),
        ("ds", "Simple"),
        ("se", "Semi-Exclusiva"),
        ("de", "Exclusiva"),
    ]
    UNIDADES_DEDICACION = {
        'ms': 0.5,
        'ds': 1,
        'se': 2,
        'de': 4,
    }
    CARACTERES_SIN_UNIDADES = ['adh', 'ads']

    MAX_UNIDADES = 5

    ESTADO_CHOICES = [("activo", "Activo"), ("licencia", "Licencia"), ("baja", "Baja")]
    
    CONTINUIDAD_CHOICES = [
        ('activo', 'Activo (en curso)'),
        ('finalizado_sin_continuidad', 'Finalizado sin continuidad'),
        ('finalizado_con_continuidad', 'Finalizado con continuidad'),
    ]
    
    RAZON_FINALIZACION_CHOICES = [
        ('renuncia', 'Renuncia'),
        ('jubilacion', 'Jubilación'),
        ('no_renovacion', 'No Renovación'),
        ('vencimiento', 'Vencimiento'),
        ('cambio_cargo', 'Cambio de Cargo'),
        ('promocion', 'Promoción'),
        ('redistribucion', 'Redistribución'),
        ('otro', 'Otro'),
    ]
    
    TIPO_CONTINUIDAD_CHOICES = [
        ('mismo_cargo', 'Renovación en mismo cargo'),
        ('promocion', 'Promoción (misma asignatura)'),
        ('cambio_asignatura', 'Cambio de asignatura'),
        ('cambio_dedicacion', 'Cambio de dedicación'),
        ('otro', 'Otro'),
    ]
    
    TIPO_CARGO_MJ_CHOICES = [
        ('docente', 'Cargo Docente'),
        ('gestion_facultad', 'Gestión en Facultad'),
        ('gestion_universidad', 'Gestión en Universidad'),
        ('gestion_dpto', 'Gestión en Departamento'),
        ('externo', 'Cargo Externo'),
        ('otro', 'Otro'),
    ]
    
    docente = models.ForeignKey(
        "Docente", related_name="cargo_docente", on_delete=models.CASCADE
    )
    caracter = models.CharField(choices=CARACTER_CHOICES, max_length=3)
    categoria = models.CharField(choices=CATEGORIA_CHOICES, max_length=4)
    dedicacion = models.CharField(choices=DEDICACION_CHOICES, max_length=2)
    cantidad_horas = models.FloatField(default=1)
    asignatura = models.ForeignKey(
        "Asignatura", related_name="cargo_asignatura", on_delete=models.CASCADE
    )
    fecha_inicio = models.DateField()
    fecha_final = models.DateField(blank=True, null=True)
    fecha_vencimiento = models.DateField(
        blank=True, null=True, verbose_name="Fecha de Vencimiento"
    )
    estado = models.CharField(choices=ESTADO_CHOICES, max_length=10, default="activo")
    renovacion_solicitada = models.BooleanField(
        default=False,
        verbose_name="Renovación Solicitada",
        help_text="Marca si se solicitó la renovación para este cargo",
    )
    fecha_renovacion = models.DateField(
        null=True,
        blank=True,
        verbose_name="Fecha de Solicitud de Renovación",
        help_text="Fecha en que se solicitó la renovación",
    )
    fecha_vencimiento_anterior = models.DateField(
        null=True,
        blank=True,
        verbose_name="Fecha de Vencimiento Anterior",
        help_text="Fecha de vencimiento antes de la renovación (para poder revertir)",
    )
    usuario_renovacion = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Usuario que Renovó",
        related_name="cargos_renovados",
    )
    # Licencia Normal
    en_licencia_normal = models.BooleanField(
        default=False,
        verbose_name="En Licencia Normal",
        help_text="Indica si el cargo está en licencia normal (no suspende vencimiento)"
    )
    fecha_inicio_licencia_normal = models.DateField(
        null=True,
        blank=True,
        verbose_name="Fecha Inicio Licencia Normal"
    )
    fecha_fin_licencia_normal = models.DateField(
        null=True,
        blank=True,
        verbose_name="Fecha Fin Licencia Normal"
    )

    # Licencia por Mayor Jerarquía (con prórroga)
    en_licencia_mayor_jerarquia = models.BooleanField(
        default=False,
        verbose_name="En Licencia por Mayor Jerarquía",
        help_text="Indica si está en licencia por mayor jerarquía (suspende y extiende vencimiento)"
    )
    fecha_inicio_licencia_mj = models.DateField(
        null=True,
        blank=True,
        verbose_name="Fecha Inicio Licencia M.J."
    )
    fecha_vencimiento_original_pre_licencia = models.DateField(
        null=True,
        blank=True,
        verbose_name="Fecha Vencimiento Original (pre-licencia)",
        help_text="Guarda el vencimiento antes de la licencia M.J. para calcular prórroga"
    )
    dias_acumulados_licencia_mj = models.IntegerField(
        default=0,
        verbose_name="Días Acumulados en Licencia M.J.",
        help_text="Total de días en licencia por mayor jerarquía"
    )
    estado_continuidad = models.CharField(
        max_length=30,
        choices=CONTINUIDAD_CHOICES,
        default='activo',
        verbose_name="Estado de Continuidad",
        help_text="Indica si el cargo está activo o cómo finalizó"
    )
    razon_finalizacion = models.CharField(
        max_length=20,
        choices=RAZON_FINALIZACION_CHOICES,
        null=True,
        blank=True,
        verbose_name="Razón de Finalización"
    )
    
    observaciones_finalizacion = models.TextField(
        null=True,
        blank=True,
        verbose_name="Observaciones de Finalización",
        help_text="Información adicional sobre la finalización"
    )
    
    cargo_anterior = models.OneToOneField(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cargo_siguiente',
        verbose_name="Cargo Anterior",
        help_text="Cargo del cual este es continuación"
    )
    
    tipo_continuidad = models.CharField(
        max_length=20,
        choices=TIPO_CONTINUIDAD_CHOICES,
        null=True,
        blank=True,
        verbose_name="Tipo de Continuidad",
        help_text="Tipo de relación con el cargo anterior"
    )
    
    usuario_registro_continuidad = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cargos_continuidad_registrada',
        verbose_name="Usuario que Registró Continuidad"
    )
    
    fecha_registro_continuidad = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Fecha de Registro de Continuidad"
    )
    cargo_base = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cargo_temporal_mj',
        verbose_name="Cargo Base",
        help_text="Cargo del cual salió en licencia por mayor jerarquía para tomar este cargo temporal"
    )

    es_cargo_mayor_jerarquia = models.BooleanField(
        default=False,
        verbose_name="Es Cargo de Mayor Jerarquía",
        help_text="Indica si este cargo es temporal por mayor jerarquía"
    )

    fecha_inicio_cargo_mj = models.DateField(
        null=True,
        blank=True,
        verbose_name="Fecha Inicio Cargo M.J."
    )

    fecha_fin_cargo_mj = models.DateField(
        null=True,
        blank=True,
        verbose_name="Fecha Fin Cargo M.J."
    )
    tipo_cargo_mj = models.CharField(
        max_length=30,
        choices=TIPO_CARGO_MJ_CHOICES,
        null=True,
        blank=True,
        verbose_name="Tipo de Cargo M.J.",
        help_text="Tipo de cargo de mayor jerarquía"
    )

    descripcion_cargo_mj = models.CharField(
        max_length=200,
        null=True,
        blank=True,
        verbose_name="Descripción Cargo M.J.",
        help_text="Descripción del cargo de mayor jerarquía (si no es cargo docente)"
    )

    institucion_cargo_mj = models.CharField(
        max_length=200,
        null=True,
        blank=True,
        verbose_name="Institución",
        help_text="Institución donde ejerce el cargo de mayor jerarquía"
    )
    cantidad_comisiones = models.PositiveIntegerField(
        default=1,
        verbose_name="Cantidad de Comisiones",
        help_text="Número de comisiones que atiende este cargo"
    )
    es_responsable_planificacion = models.BooleanField(
        default=False,
        help_text="Marca este cargo como responsable de recibir notificaciones de planificación"
    )
    cantidad_dedicaciones = models.PositiveIntegerField(
        default=1,
        verbose_name="Cantidad de Dedicaciones",
        help_text="Cantidad de dedicaciones de este tipo. Ej: 2 DS = 2 unidades"
    )
    objects = CargoManager()

    def solicitar_renovacion(self, usuario):
        """Solicita la renovación del cargo."""
        from django.utils import timezone

        if self.caracter not in ["int", "adh"]:
            return False, "Solo se pueden renovar cargos interinos o ad-honorem"

        if self.estado != "activo":
            return False, "Solo se pueden renovar cargos activos"

        # Guardar fecha anterior
        self.fecha_vencimiento_anterior = self.fecha_vencimiento

        # Calcular próximo 31 de marzo
        hoy = timezone.now().date()
        año_actual = hoy.year
        fecha_31_marzo = timezone.datetime(año_actual, 3, 31).date()

        if hoy > fecha_31_marzo:
            self.fecha_vencimiento = timezone.datetime(año_actual + 1, 3, 31).date()
        else:
            self.fecha_vencimiento = fecha_31_marzo

        # Marcar como renovado
        self.renovacion_solicitada = True
        self.fecha_renovacion = hoy
        self.usuario_renovacion = usuario
        self.save()

        return (
            True,
            f"Renovación solicitada. Nueva fecha: {self.fecha_vencimiento.strftime('%d/%m/%Y')}",
        )

    def cancelar_renovacion(self):
        """Cancela la renovación."""
        if not self.renovacion_solicitada:
            return False, "Este cargo no tiene una renovación solicitada"

        if self.fecha_vencimiento_anterior:
            self.fecha_vencimiento = self.fecha_vencimiento_anterior

        self.renovacion_solicitada = False
        self.fecha_renovacion = None
        self.fecha_vencimiento_anterior = None
        self.usuario_renovacion = None
        self.save()

        return True, "Renovación cancelada exitosamente"
    
    def get_categoria_display_abreviada(self):
        """Retorna nombre abreviado de categoría para PDFs."""
        abreviaturas = {
            'tit': 'Titular',
            'aso': 'Asociado',
            'adj': 'Adjunto',
            'jtp': 'JTP',
            'atp1': 'ATP1',
            'atp2': 'ATP2',
            'ads': 'Adscripto',
        }
        return abreviaturas.get(self.categoria, self.get_categoria_display())

    def get_jerarquia_display(self):
        """Retorna jerarquía formateada."""
        categoria_map = {
            "tit": "Profesor Titular",
            "aso": "Profesor Asociado",
            "adj": "Profesor Adjunto",
            "jtp": "Jefe de Trabajos Prácticos",
            "atp1": "Ayudante de Primera",
            "atp2": "Ayudante de Segunda",
        }
        return categoria_map.get(self.categoria, self.get_categoria_display())

    def dar_alta_licencia_normal(self, fecha_inicio, fecha_fin, usuario=None):
        """
        Da de alta una licencia normal.
        No afecta el vencimiento del cargo.
        """
        if self.en_licencia_normal:
            return False, "El cargo ya está en licencia normal"

        if self.en_licencia_mayor_jerarquia:
            return False, "El cargo está en licencia por mayor jerarquía. Debe dar de baja esa licencia primero."

        if self.estado not in ["activo", "licencia"]:
            return False, "Solo se pueden licenciar cargos activos"

        if fecha_fin <= fecha_inicio:
            return False, "La fecha de fin debe ser posterior a la fecha de inicio"

        # Aplicar licencia
        self.en_licencia_normal = True
        self.fecha_inicio_licencia_normal = fecha_inicio
        self.fecha_fin_licencia_normal = fecha_fin
        self.estado = "licencia"
        self.save()

        duracion = (fecha_fin - fecha_inicio).days
        return True, f"Licencia normal aplicada del {fecha_inicio.strftime('%d/%m/%Y')} al {fecha_fin.strftime('%d/%m/%Y')} ({duracion} días). No afecta vencimiento."

    def dar_baja_licencia_normal(self):
        """
        Da de baja una licencia normal.
        """
        if not self.en_licencia_normal:
            return False, "El cargo no está en licencia normal"

        # Limpiar campos
        self.en_licencia_normal = False
        self.fecha_inicio_licencia_normal = None
        self.fecha_fin_licencia_normal = None

        # Volver a activo si no hay otra licencia
        if not self.en_licencia_mayor_jerarquia:
            self.estado = "activo"

        self.save()

        return True, "Licencia normal finalizada."

    def dar_alta_licencia_mayor_jerarquia(self, fecha_inicio, tipo_cargo=None, descripcion_cargo=None, institucion=None, usuario=None):
        """
        Da de alta una licencia por mayor jerarquía.
        Puede ser para cargo docente (vinculado) o cargo de gestión (descriptivo).
        """
        if self.en_licencia_mayor_jerarquia:
            return False, "El cargo ya está en licencia por mayor jerarquía"

        if self.estado not in ["activo", "licencia"]:
            return False, "Solo se pueden licenciar cargos activos"

        if not self.fecha_vencimiento:
            return False, "El cargo no tiene fecha de vencimiento"

        if fecha_inicio >= self.fecha_vencimiento:
            return False, "La fecha de inicio de licencia no puede ser posterior al vencimiento del cargo"

        # Guardar estado anterior
        self.fecha_vencimiento_original_pre_licencia = self.fecha_vencimiento
        self.fecha_inicio_licencia_mj = fecha_inicio

        # Guardar info del cargo de gestión si se proporciona
        if tipo_cargo:
            self.tipo_cargo_mj = tipo_cargo
        if descripcion_cargo:
            self.descripcion_cargo_mj = descripcion_cargo
        if institucion:
            self.institucion_cargo_mj = institucion

        # Aplicar licencia
        self.en_licencia_mayor_jerarquia = True
        self.estado = "licencia"
        self.save()

        return True, f"Licencia por mayor jerarquía iniciada el {fecha_inicio.strftime('%d/%m/%Y')}. Vencimiento suspendido."

    def dar_baja_licencia_mayor_jerarquia(self, fecha_fin, usuario=None):
        """
        Da de baja una licencia por mayor jerarquía.
        Calcula y aplica la prórroga de vencimiento.
        """
        from datetime import timedelta

        if not self.en_licencia_mayor_jerarquia:
            return False, "El cargo no está en licencia por mayor jerarquía"

        if not self.fecha_inicio_licencia_mj:
            return False, "No hay fecha de inicio de licencia registrada"

        # Validar que la fecha fin sea posterior al inicio
        if fecha_fin <= self.fecha_inicio_licencia_mj:
            return False, "La fecha de fin debe ser posterior al inicio de la licencia"

        # Calcular duración de la licencia
        duracion_licencia = (fecha_fin - self.fecha_inicio_licencia_mj).days

        # Calcular nueva fecha de vencimiento
        if self.fecha_vencimiento_original_pre_licencia:
            nueva_fecha_vencimiento = self.fecha_vencimiento_original_pre_licencia + \
                timedelta(days=duracion_licencia)
        else:
            # Fallback: extender desde la fecha actual de vencimiento
            nueva_fecha_vencimiento = self.fecha_vencimiento + \
                timedelta(days=duracion_licencia)

        # Actualizar campos
        self.fecha_vencimiento = nueva_fecha_vencimiento
        self.dias_acumulados_licencia_mj += duracion_licencia

        # Resetear estado de licencia M.J.
        self.en_licencia_mayor_jerarquia = False
        self.fecha_inicio_licencia_mj = None
        self.fecha_vencimiento_original_pre_licencia = None

        # Volver a activo si no hay licencia normal
        if not self.en_licencia_normal:
            self.estado = "activo"

        self.save()

        mensaje = (
            f"Licencia por mayor jerarquía finalizada. Duración: {duracion_licencia} días. "
            f"Nueva fecha de vencimiento: {nueva_fecha_vencimiento.strftime('%d/%m/%Y')}"
        )

        # Agregar info de CA si existe
        if hasattr(self, 'carrera_academica') and self.carrera_academica:
            mensaje += f" (CA sincronizada automáticamente)"

        return True, mensaje
    
    def prorrogar_vencimiento(self, dias, observaciones=None, usuario=None):
        """
        Prorroga la fecha de vencimiento del cargo.
        La CA se sincroniza automáticamente.
        """
        from datetime import timedelta

        if not self.fecha_vencimiento:
            return False, "El cargo no tiene fecha de vencimiento"

        if dias <= 0:
            return False, "Los días de prórroga deben ser positivos"

        fecha_anterior = self.fecha_vencimiento
        self.fecha_vencimiento = self.fecha_vencimiento + timedelta(days=dias)
        self.save()
        # ↑ Signal sincroniza automáticamente la CA

        mensaje = (
            f"Prórroga de {dias} días aplicada. "
            f"Vencimiento: {fecha_anterior.strftime('%d/%m/%Y')} → {self.fecha_vencimiento.strftime('%d/%m/%Y')}"
        )

        if hasattr(self, 'carrera_academica') and self.carrera_academica:
            mensaje += " (CA sincronizada)"

        return True, mensaje

    def get_estado_licencia_display(self):
        """Retorna información sobre el estado de licencia del cargo."""
        from django.utils import timezone

        if self.en_licencia_mayor_jerarquia:
            dias = (timezone.now().date(
            ) - self.fecha_inicio_licencia_mj).days if self.fecha_inicio_licencia_mj else 0
            return {
                'tipo': 'mayor_jerarquia',
                'en_licencia': True,
                'fecha_inicio': self.fecha_inicio_licencia_mj,
                'dias_transcurridos': dias,
                'fecha_vencimiento_suspendido': self.fecha_vencimiento_original_pre_licencia,
                'mensaje': f'Licencia por Mayor Jerarquía desde {self.fecha_inicio_licencia_mj.strftime("%d/%m/%Y")} ({dias} días)',
                'clase_badge': 'bg-warning text-dark',
                'icono': 'bi-pause-circle'
            }

        if self.en_licencia_normal:
            dias_totales = (self.fecha_fin_licencia_normal -
                            self.fecha_inicio_licencia_normal).days if self.fecha_fin_licencia_normal and self.fecha_inicio_licencia_normal else 0
            dias_transcurridos = (timezone.now().date(
            ) - self.fecha_inicio_licencia_normal).days if self.fecha_inicio_licencia_normal else 0

            return {
                'tipo': 'normal',
                'en_licencia': True,
                'fecha_inicio': self.fecha_inicio_licencia_normal,
                'fecha_fin': self.fecha_fin_licencia_normal,
                'dias_transcurridos': dias_transcurridos,
                'dias_totales': dias_totales,
                'mensaje': f'Licencia Normal del {self.fecha_inicio_licencia_normal.strftime("%d/%m/%Y")} al {self.fecha_fin_licencia_normal.strftime("%d/%m/%Y")}',
                'clase_badge': 'bg-info',
                'icono': 'bi-calendar-event'
            }

        return {
            'tipo': None,
            'en_licencia': False,
            'mensaje': 'Sin licencia',
            'clase_badge': 'bg-success',
            'icono': 'bi-check-circle'
        }
    
    def finalizar_sin_continuidad(self, razon, observaciones=None, usuario=None):
        """
        Finaliza el cargo sin continuidad (termina definitivamente).
        """
        from django.utils import timezone

        if self.estado_continuidad != 'activo':
            return False, "El cargo ya fue finalizado"

        self.estado_continuidad = 'finalizado_sin_continuidad'
        self.estado = 'baja'
        self.razon_finalizacion = razon
        self.observaciones_finalizacion = observaciones
        self.fecha_final = timezone.now().date()
        self.usuario_registro_continuidad = usuario
        self.fecha_registro_continuidad = timezone.now()

        self.save()

        return True, f"Cargo finalizado sin continuidad. Razón: {self.get_razon_finalizacion_display()}"

    def finalizar_con_continuidad(self, cargo_siguiente, tipo_continuidad, observaciones=None, usuario=None):
        """
        Finaliza el cargo estableciendo continuidad con un cargo siguiente.
        """
        from django.utils import timezone

        if self.estado_continuidad != 'activo':
            return False, "El cargo ya fue finalizado"

        if cargo_siguiente.cargo_anterior is not None:
            return False, "El cargo siguiente ya tiene un cargo anterior asignado"

        # Actualizar este cargo
        self.estado_continuidad = 'finalizado_con_continuidad'
        self.estado = 'baja'
        self.razon_finalizacion = 'cambio_cargo'
        self.observaciones_finalizacion = observaciones
        self.fecha_final = timezone.now().date()
        self.usuario_registro_continuidad = usuario
        self.fecha_registro_continuidad = timezone.now()
        self.save()

        # Vincular cargo siguiente
        cargo_siguiente.cargo_anterior = self
        cargo_siguiente.tipo_continuidad = tipo_continuidad
        cargo_siguiente.usuario_registro_continuidad = usuario
        cargo_siguiente.fecha_registro_continuidad = timezone.now()
        cargo_siguiente.save()

        return True, f"Cargo finalizado con continuidad en {cargo_siguiente}"

    def desvincular_continuidad(self):
        """
        Desvincula la continuidad (útil si se cometió un error).
        """
        if self.estado_continuidad == 'activo':
            return False, "El cargo está activo, no tiene continuidad que desvincular"

        # Si este cargo tiene un siguiente, desvincularlo
        if hasattr(self, 'cargo_siguiente') and self.cargo_siguiente:
            cargo_sig = self.cargo_siguiente
            cargo_sig.cargo_anterior = None
            cargo_sig.tipo_continuidad = None
            cargo_sig.usuario_registro_continuidad = None
            cargo_sig.fecha_registro_continuidad = None
            cargo_sig.save()

        # Resetear este cargo
        self.estado_continuidad = 'activo'
        self.razon_finalizacion = None
        self.observaciones_finalizacion = None
        self.usuario_registro_continuidad = None
        self.fecha_registro_continuidad = None
        self.save()

        return True, "Continuidad desvinculada exitosamente"

    def obtener_cadena_continuidad(self):
        """
        Obtiene la cadena completa de continuidad (anterior y siguiente).
        Retorna: {'anteriores': [cargos], 'siguiente': cargo}
        """
        cadena = {
            'anteriores': [],
            'siguiente': None
        }

        # Buscar todos los cargos anteriores
        cargo_actual = self
        while cargo_actual.cargo_anterior:
            cadena['anteriores'].insert(0, cargo_actual.cargo_anterior)
            cargo_actual = cargo_actual.cargo_anterior

        # Buscar cargo siguiente
        if hasattr(self, 'cargo_siguiente') and self.cargo_siguiente:
            cadena['siguiente'] = self.cargo_siguiente

        return cadena

    def get_info_continuidad(self):
        """
        Retorna información detallada sobre la continuidad del cargo.
        """
        info = {
            'estado': self.estado_continuidad,
            'estado_display': self.get_estado_continuidad_display(),
            'tiene_anterior': self.cargo_anterior is not None,
            'tiene_siguiente': hasattr(self, 'cargo_siguiente') and self.cargo_siguiente is not None,
        }

        if self.cargo_anterior:
            info['cargo_anterior'] = {
                'id': self.cargo_anterior.pk,
                'descripcion': str(self.cargo_anterior),
                'periodo': f"{self.cargo_anterior.fecha_inicio.strftime('%d/%m/%Y')} - {self.cargo_anterior.fecha_final.strftime('%d/%m/%Y') if self.cargo_anterior.fecha_final else 'Actual'}",
                'tipo_continuidad': self.get_tipo_continuidad_display() if self.tipo_continuidad else None,
            }

        if hasattr(self, 'cargo_siguiente') and self.cargo_siguiente:
            info['cargo_siguiente'] = {
                'id': self.cargo_siguiente.pk,
                'descripcion': str(self.cargo_siguiente),
                'periodo': f"{self.cargo_siguiente.fecha_inicio.strftime('%d/%m/%Y')} - {self.cargo_siguiente.fecha_final.strftime('%d/%m/%Y') if self.cargo_siguiente.fecha_final else 'Actual'}",
                'tipo_continuidad': self.cargo_siguiente.get_tipo_continuidad_display() if self.cargo_siguiente.tipo_continuidad else None,
            }

        if self.razon_finalizacion:
            info['finalizacion'] = {
                'razon': self.get_razon_finalizacion_display(),
                'observaciones': self.observaciones_finalizacion,
                'fecha': self.fecha_final,
            }

        return info
    
    def vincular_cargo_mayor_jerarquia(self, cargo_mj=None, fecha_inicio=None,
                                       tipo_cargo=None, descripcion_cargo=None,
                                       institucion=None, usuario=None):
        """
        Vincula este cargo (base) con un cargo de mayor jerarquía.
        
        Dos modalidades:
        1. cargo_mj: Vincular con otro cargo docente del sistema
        2. tipo_cargo + descripcion: Describir cargo de gestión/externo
        """
        from django.utils import timezone

        if not fecha_inicio:
            fecha_inicio = timezone.now().date()

        # Validación: debe proporcionar cargo docente O descripción
        if not cargo_mj and not descripcion_cargo:
            return False, "Debe vincular con un cargo docente o proporcionar descripción del cargo de gestión"

        if cargo_mj and descripcion_cargo:
            return False, "No puede vincular cargo docente y cargo de gestión simultáneamente"

        # CASO 1: Vinculación con cargo docente
        if cargo_mj:
            # Validaciones existentes
            if self.docente != cargo_mj.docente:
                return False, "Ambos cargos deben ser del mismo docente"

            if self.en_licencia_mayor_jerarquia:
                return False, "Este cargo ya está en licencia por mayor jerarquía"

            if self == cargo_mj:
                return False, "No se puede vincular un cargo consigo mismo"

            # Dar de alta licencia M.J. en cargo base
            exito, mensaje = self.dar_alta_licencia_mayor_jerarquia(
                fecha_inicio=fecha_inicio,
                tipo_cargo='docente',
                usuario=usuario
            )

            if not exito:
                return False, mensaje

            # Marcar el cargo de mayor jerarquía como temporal
            cargo_mj.es_cargo_mayor_jerarquia = True
            cargo_mj.cargo_base = self
            cargo_mj.fecha_inicio_cargo_mj = fecha_inicio
            cargo_mj.estado = 'activo'
            cargo_mj.save()

            return True, (
                f"Vinculación exitosa. {self.get_categoria_display()} en licencia M.J. "
                f"para tomar {cargo_mj.get_categoria_display()}"
            )

        # CASO 2: Cargo de gestión (no docente)
        else:
            exito, mensaje = self.dar_alta_licencia_mayor_jerarquia(
                fecha_inicio=fecha_inicio,
                tipo_cargo=tipo_cargo or 'otro',
                descripcion_cargo=descripcion_cargo,
                institucion=institucion,
                usuario=usuario
            )

            if not exito:
                return False, mensaje

            cargo_display = descripcion_cargo
            if institucion:
                cargo_display += f" ({institucion})"

            return True, (
                f"Licencia M.J. registrada exitosamente. "
                f"{self.get_categoria_display()} en licencia para: {cargo_display}"
            )

    def desvincular_cargo_mayor_jerarquia(self, fecha_fin=None, usuario=None):
        """
        Desvincula cargo de mayor jerarquía de su cargo base.
        Cargo base vuelve a activo, cargo M.J. se finaliza.
        Se llama desde el cargo de MAYOR JERARQUÍA.
        """
        from django.utils import timezone

        if not self.es_cargo_mayor_jerarquia:
            return False, "Este cargo no es un cargo de mayor jerarquía"

        if not self.cargo_base:
            return False, "Este cargo no tiene un cargo base vinculado"

        if not fecha_fin:
            fecha_fin = timezone.now().date()

        cargo_base = self.cargo_base

        # Dar de baja licencia M.J. en cargo base
        exito, mensaje_baja = cargo_base.dar_baja_licencia_mayor_jerarquia(
            fecha_fin=fecha_fin,
            usuario=usuario
        )

        if not exito:
            return False, mensaje_baja

        # Marcar este cargo (M.J.) como finalizado
        self.fecha_fin_cargo_mj = fecha_fin
        self.estado = 'baja'
        self.save()

        return True, (
            f"Desvinculación exitosa. Vuelve a {cargo_base.get_categoria_display()} "
            f"({cargo_base.asignatura.nombre}). {mensaje_baja}"
        )

    def get_cargo_efectivo_docente(self):
        """
        Retorna el cargo efectivo actual del docente.
        Si está en licencia M.J., retorna el cargo temporal.
        """
        if self.en_licencia_mayor_jerarquia and hasattr(self, 'cargo_temporal_mj'):
            cargo_temp = self.cargo_temporal_mj.filter(
                es_cargo_mayor_jerarquia=True,
                estado='activo'
            ).first()
            return cargo_temp if cargo_temp else self

        return self

    def get_info_mayor_jerarquia(self):
        """
        Retorna información sobre la situación de mayor jerarquía.
        """
        info = {
            'es_cargo_mj': self.es_cargo_mayor_jerarquia,
            'tiene_cargo_temporal': False,
            'es_cargo_gestion': False,
            'cargo_base': None,
            'cargo_temporal': None,
            'cargo_gestion': None,
        }

        # Si este cargo es de mayor jerarquía (temporal docente)
        if self.es_cargo_mayor_jerarquia and self.cargo_base:
            info['cargo_base'] = {
                'id': self.cargo_base.pk,
                'descripcion': str(self.cargo_base),
                'categoria': self.cargo_base.get_categoria_display(),
                'asignatura': self.cargo_base.asignatura.nombre,
                'fecha_inicio_licencia': self.cargo_base.fecha_inicio_licencia_mj,
            }

        # Si este cargo tiene un temporal docente activo
        if hasattr(self, 'cargo_temporal_mj'):
            cargo_temp = self.cargo_temporal_mj.filter(
                es_cargo_mayor_jerarquia=True,
                estado='activo'
            ).first()

            if cargo_temp:
                info['tiene_cargo_temporal'] = True
                info['cargo_temporal'] = {
                    'id': cargo_temp.pk,
                    'descripcion': str(cargo_temp),
                    'categoria': cargo_temp.get_categoria_display(),
                    'asignatura': cargo_temp.asignatura.nombre,
                    'fecha_inicio': cargo_temp.fecha_inicio_cargo_mj,
                }

        # Si este cargo está en licencia por cargo de gestión
        if self.en_licencia_mayor_jerarquia and self.tipo_cargo_mj and self.tipo_cargo_mj != 'docente':
            info['es_cargo_gestion'] = True
            info['cargo_gestion'] = {
                'tipo': self.get_tipo_cargo_mj_display(),
                'descripcion': self.descripcion_cargo_mj,
                'institucion': self.institucion_cargo_mj,
                'fecha_inicio': self.fecha_inicio_licencia_mj,
            }

        return info
    
    def requiere_funciones_sustantivas(self):
        """
        Verifica si el cargo requiere funciones sustantivas según normativa.
        Considera: dedicación, horas de asignatura y cantidad de comisiones.

        NORMATIVA:
        - Exclusiva (40hs): Mínimo 10hs dictado
        - Semi-Exclusiva (20hs): Mínimo 10hs dictado
        - Simple (10hs): Mínimo 4hs dictado
        - Media Simple (5hs): Mínimo 1 curso
        - Ad-Honorem: NO requiere (sin remuneración)

        Horas efectivas = horas_asignatura × cantidad_comisiones
        """
        if not self.asignatura:
            return False, "No tiene asignatura asignada"
        
        # Cargos Ad-Honorem NO requieren funciones sustantivas
        if self.caracter == 'adh':
            return False, "Los cargos Ad-Honorem no requieren funciones sustantivas"

        # Horas efectivas = horas asignatura × comisiones que atiende
        horas_asignatura = self.asignatura.hora_semanal or 0
        horas_efectivas = horas_asignatura * self.cantidad_comisiones

        # Horas mínimas de dictado según dedicación
        minimos_dictado = {
            'ms': {'horas': 0, 'descripcion': '1 curso (sin mínimo de horas)'},
            'ds': {'horas': 4, 'descripcion': '4hs de dictado'},
            'se': {'horas': 10, 'descripcion': '10hs de dictado'},
            'de': {'horas': 10, 'descripcion': '10hs de dictado'},
        }

        config = minimos_dictado.get(self.dedicacion, {'horas': 4, 'descripcion': '4hs'})
        minimo = config['horas']

        # Caso especial: Media Simple (solo requiere 1 curso, sin importar horas)
        if self.dedicacion == 'ms':
            return False, f"Media Simple cumple con 1 curso ({horas_efectivas}hs efectivas)"

        # Verificar si cumple mínimo de dictado
        if horas_efectivas >= minimo:
            mensaje = (
                f"Cumple mínimo de {config['descripcion']}. "
                f"Horas efectivas: {horas_efectivas}hs "
                f"({horas_asignatura}hs/semana × {self.cantidad_comisiones} comisión/es)"
            )
            return False, mensaje

        # Necesita funciones sustantivas para completar
        horas_faltantes = minimo - horas_efectivas

        mensaje = (
            f"Dedicación {self.get_dedicacion_display()} requiere mínimo {minimo}hs de dictado. "
            f"Horas efectivas actuales: {horas_efectivas}hs "
            f"({horas_asignatura}hs/semana × {self.cantidad_comisiones} comisión/es). "
            f"Requiere {horas_faltantes}hs adicionales mediante funciones sustantivas."
        )

        return True, mensaje

    def get_funciones_sustantivas_activas(self):
        """Retorna las funciones sustantivas actualmente vigentes"""
        return self.actividades_sustantivas.filter(activa=True)

    def resumen_funciones_sustantivas(self):
        """Genera un resumen de funciones sustantivas por categoría"""
        funciones = self.get_funciones_sustantivas_activas()

        resumen = {
            'docencia_grado': [],
            'docencia_posgrado': [],
            'investigacion': [],
            'extension': [],
        }

        for funcion in funciones:
            resumen[funcion.categoria].append(funcion)

        return resumen

    def tiene_funciones_sustantivas_completas(self):
        """
        Verifica si las funciones sustantivas completan el mínimo de dictado requerido.
        """
        requiere, razon = self.requiere_funciones_sustantivas()
        
        # Si no requiere, está completo
        if not requiere:
            return True, razon
        
        # Calcular horas efectivas actuales
        horas_asignatura = self.asignatura.hora_semanal or 0
        horas_efectivas = horas_asignatura * self.cantidad_comisiones
        
        # Obtener horas de funciones sustantivas (solo docencia cuenta para dictado)
        horas_funciones = self.get_horas_funciones_sustantivas()
        # Solo considerar docencia para completar mínimo de dictado
        horas_docencia_funciones = horas_funciones['docencia_grado'] + horas_funciones['docencia_posgrado']
        
        # Mínimo requerido de dictado
        minimos = {
            'ds': 4,
            'se': 10,
            'de': 10,
        }
        minimo = minimos.get(self.dedicacion, 4)
        
        # Total de horas de dictado
        total_dictado = horas_efectivas + horas_docencia_funciones
        
        if total_dictado >= minimo:
            mensaje = (
                f"Cumple mínimo de {minimo}hs de dictado: "
                f"{horas_efectivas}hs (asignatura principal) + "
                f"{horas_docencia_funciones}hs (funciones sustantivas) = {total_dictado}hs"
            )
            
            # Mencionar otras funciones si existen
            otras = horas_funciones['investigacion'] + horas_funciones['extension']
            if otras > 0:
                mensaje += f". Además: {otras}hs en investigación/extensión"
            
            return True, mensaje
        
        faltante = minimo - total_dictado
        mensaje = (
            f"Incompleto: {total_dictado}hs de {minimo}hs requeridas de dictado. "
            f"Faltan {faltante}hs de docencia por completar con funciones sustantivas."
        )
        
        return False, mensaje

    def get_horas_funciones_sustantivas(self):
        """
        Calcula el total de horas dedicadas a funciones sustantivas.
        Retorna diccionario con totales por categoría.
        """
        funciones = self.get_funciones_sustantivas_activas()

        totales = {
            'docencia_grado': 0,
            'docencia_posgrado': 0,
            'investigacion': 0,
            'extension': 0,
            'total': 0,
        }

        for funcion in funciones:
            if funcion.horas_semanales:
                totales[funcion.categoria] += funcion.horas_semanales
                totales['total'] += funcion.horas_semanales

        return totales
        
    def get_fecha_inicio_real(self):
        """
        Retorna la fecha de inicio original considerando la cadena de continuidad.
        Para calcular antigüedad real en el cargo.
        """
        cargo_actual = self
        while cargo_actual.cargo_anterior:
            cargo_actual = cargo_actual.cargo_anterior
        
        return cargo_actual.fecha_inicio
    
    def get_antiguedad_cargo(self):
        """
        Calcula la antigüedad real en el cargo considerando toda la cadena.
        Retorna años, meses, días.
        """
        from django.utils import timezone
        
        fecha_inicio_real = self.get_fecha_inicio_real()
        hoy = timezone.now().date()
        
        # Calcular diferencia
        total_dias = (hoy - fecha_inicio_real).days
        
        # Calcular años y meses manualmente
        años = 0
        meses = 0
        
        # Años completos
        años = (hoy.year - fecha_inicio_real.year)
        
        # Ajustar si aún no cumplió años este año
        if (hoy.month, hoy.day) < (fecha_inicio_real.month, fecha_inicio_real.day):
            años -= 1
        
        # Calcular meses
        if hoy.month >= fecha_inicio_real.month:
            meses = hoy.month - fecha_inicio_real.month
        else:
            meses = 12 - fecha_inicio_real.month + hoy.month
        
        # Ajustar meses si el día no ha llegado
        if hoy.day < fecha_inicio_real.day:
            meses -= 1
            if meses < 0:
                meses = 11
                años -= 1
        
        # Calcular días del mes actual
        import calendar
        if hoy.day >= fecha_inicio_real.day:
            dias = hoy.day - fecha_inicio_real.day
        else:
            # Días del mes anterior
            mes_anterior = hoy.month - 1 if hoy.month > 1 else 12
            año_mes_anterior = hoy.year if hoy.month > 1 else hoy.year - 1
            dias_mes_anterior = calendar.monthrange(año_mes_anterior, mes_anterior)[1]
            dias = dias_mes_anterior - fecha_inicio_real.day + hoy.day
        
        return {
            'años': años,
            'meses': meses,
            'dias': dias,
            'fecha_inicio': fecha_inicio_real,
            'total_dias': total_dias
        }
        
    def get_unidades_dedicacion(self):
        """
        Retorna las unidades de dedicación ocupadas y disponibles del docente.
        """
        cargos = Cargo.objects.filter(
            docente=self.docente,
            estado='activo',
        ).exclude(pk=self.pk).exclude(caracter__in=self.CARACTERES_SIN_UNIDADES)

        ocupadas = sum(self.UNIDADES_DEDICACION.get(c.dedicacion, 0) * c.cantidad_cargos for c in cargos)
        ocupadas += self.UNIDADES_DEDICACION.get(self.dedicacion, 0) * self.cantidad_cargos

        return {
            'ocupadas': ocupadas,
            'disponibles': self.MAX_UNIDADES - ocupadas,
            'maximo': self.MAX_UNIDADES,
        }
    
    def get_antiguedad_display(self):
        """
        Retorna la antigüedad formateada para mostrar.
        """
        ant = self.get_antiguedad_cargo()
        
        partes = []
        if ant['años'] > 0:
            partes.append(f"{ant['años']} año{'s' if ant['años'] != 1 else ''}")
        if ant['meses'] > 0:
            partes.append(f"{ant['meses']} mes{'es' if ant['meses'] != 1 else ''}")
        
        if not partes:
            partes.append(f"{ant['dias']} día{'s' if ant['dias'] != 1 else ''}")
        
        return ' y '.join(partes)
    
    def clean(self):
        """Validaciones a nivel de modelo."""
        super().clean()
        errors = {}

        # Validación 1: Fecha final debe ser posterior a fecha inicio
        if self.fecha_final and self.fecha_inicio:
            if self.fecha_final <= self.fecha_inicio:
                errors["fecha_final"] = ValidationError(
                    "La fecha final debe ser posterior a la fecha de inicio.",
                    code="invalid_date_range",
                )

        # Validación 2: Fecha de vencimiento debe ser posterior a fecha inicio
        if self.fecha_vencimiento and self.fecha_inicio:
            if self.fecha_vencimiento <= self.fecha_inicio:
                errors["fecha_vencimiento"] = ValidationError(
                    "La fecha de vencimiento debe ser posterior a la fecha de inicio.",
                    code="invalid_vencimiento",
                )

        # Validación: Cantidad de comisiones no puede exceder las de la asignatura
        if self.asignatura and self.cantidad_comisiones:
            comisiones_asignatura = self.asignatura.numero_comisiones or 1

            if self.cantidad_comisiones > comisiones_asignatura:
                errors['cantidad_comisiones'] = ValidationError(
                    f"La asignatura '{self.asignatura.nombre}' tiene {comisiones_asignatura} comisión/es. "
                    f"No se pueden asignar {self.cantidad_comisiones} comisiones a este cargo.",
                    code='excede_comisiones_asignatura'
                )

            if self.cantidad_comisiones < 1:
                errors['cantidad_comisiones'] = ValidationError(
                    'Debe asignar al menos 1 comisión al cargo.',
                    code='minimo_comisiones'
                )

        # Validación 4: Cargos Ad-Honorem no pueden tener dedicación exclusiva o semi
        if self.caracter == "adh" and self.dedicacion in ["de", "se"]:
            errors["dedicacion"] = ValidationError(
                "Los cargos Ad-Honorem no pueden tener dedicación exclusiva o semi-exclusiva.",
                code="invalid_dedication_for_adhonorem",
            )

        # Validación: unidades de dedicación no pueden superar 5
        # Se evalúa contra la fecha de inicio del cargo (no "hoy"), para que un cargo
        # futuro no choque con uno que ya venció para esa fecha (ej: redesignación).
        if self.caracter not in self.CARACTERES_SIN_UNIDADES and self.estado == 'activo':
            check_date = self.fecha_inicio if self.fecha_inicio else timezone.now().date()
            unidades_cargo_actual = self.UNIDADES_DEDICACION.get(self.dedicacion, 0) * self.cantidad_dedicaciones

            cargos_activos = Cargo.objects.filter(
                docente=self.docente,
                estado='activo',
                fecha_inicio__lte=check_date,
            ).filter(
                Q(fecha_vencimiento__isnull=True) | Q(fecha_vencimiento__gte=check_date)
            ).exclude(pk=self.pk).exclude(caracter__in=self.CARACTERES_SIN_UNIDADES)

            unidades_ocupadas = sum(
                self.UNIDADES_DEDICACION.get(c.dedicacion, 0) * c.cantidad_dedicaciones for c in cargos_activos
            )

            if unidades_ocupadas + unidades_cargo_actual > self.MAX_UNIDADES:
                errors['dedicacion'] = ValidationError(
                    f"El docente ya tiene {unidades_ocupadas} unidades de dedicación ocupadas. "
                    f"Agregar {self.get_dedicacion_display()} ({unidades_cargo_actual} unidades) "
                    f"superaría el máximo de {self.MAX_UNIDADES}.",
                    code='max_unidades_dedicacion'
                )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        """Override save para ejecutar validaciones."""
        self.full_clean()
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Cargo"
        verbose_name_plural = "Cargos"
        constraints = [
            models.UniqueConstraint(
                fields=['asignatura'],
                condition=models.Q(es_responsable_planificacion=True),
                name='unique_responsable_planificacion_por_asignatura_año'
            )
        ]
        # Agregar índices
        indexes = [
            # Índice para filtrar por docente
            models.Index(fields=["docente"], name="cargo_docente_idx"),
            # Índice para filtrar por asignatura
            models.Index(fields=["asignatura"], name="cargo_asignatura_idx"),
            # Índice para filtrar por estado
            models.Index(fields=["estado"], name="cargo_estado_idx"),
            # Índice para filtrar por carácter
            models.Index(fields=["caracter"], name="cargo_caracter_idx"),
            # Índice compuesto: estado + carácter (query común para CA)
            models.Index(
                fields=["estado", "caracter"], name="cargo_estado_caracter_idx"
            ),
            # Índice compuesto: docente + asignatura (evitar duplicados)
            models.Index(fields=["docente", "asignatura"], name="cargo_doc_asig_idx"),
            # Índice para ordenar por fecha de inicio
            models.Index(fields=["fecha_inicio"], name="cargo_fecha_inicio_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.docente.apellido.upper()} ({self.get_caracter_display()} en {self.asignatura.nombre.title()})"


class ActividadSustantiva(models.Model):
    """
    Funciones sustantivas vinculadas al cargo según normativa de concursos.
    Obligatorias cuando la asignatura prioritaria tiene 2-3hs cátedra.
    Deben estar incluidas en Resolución de Consejo Directivo.
    """

    TIPO_ACTIVIDAD_CHOICES = [
        # Docencia - Grado
        ('doc_grado_segundo', 'Docencia - Segundo curso de grado'),
        ('doc_grado_electiva', 'Docencia - Asignatura electiva'),
        ('doc_grado_pf_dir', 'Docencia - Dirección de proyecto final'),
        ('doc_grado_pf_codir', 'Docencia - Codirección de proyecto final'),
        ('doc_grado_tutoria', 'Docencia - Tutorías de estudiantes'),
        ('doc_grado_ps_dir', 'Docencia - Dirección de prácticas supervisadas'),
        ('doc_grado_ps_sup', 'Docencia - Supervisión de prácticas supervisadas'),
        ('doc_grado_tc_dir', 'Docencia - Dirección de trabajos de campo'),
        ('doc_grado_tc_sup', 'Docencia - Supervisión de trabajos de campo'),

        # Docencia - Posgrado
        ('doc_pos_curso', 'Docencia - Curso o seminario de posgrado'),
        ('doc_pos_tesis_dir', 'Docencia - Dirección de tesis de posgrado'),
        ('doc_pos_tesis_codir', 'Docencia - Codirección de tesis de posgrado'),
        ('doc_pos_pi_dir', 'Docencia - Dirección de proyecto integrador'),
        ('doc_pos_pi_codir', 'Docencia - Codirección de proyecto integrador'),

        # Investigación
        ('inv_pid', 'Investigación - Participación en PID UTN'),

        # Extensión
        ('ext_curso', 'Extensión - Curso o seminario'),
        ('ext_capacitacion', 'Extensión - Capacitación'),
        ('ext_voluntariado', 'Extensión - Voluntariado universitario'),
        ('ext_servicio', 'Extensión - Servicio al medio'),
        ('ext_transferencia', 'Extensión - Transferencia al medio'),
    ]

    CATEGORIA_CHOICES = [
        ('docencia_grado', 'Docencia - Grado'),
        ('docencia_posgrado', 'Docencia - Posgrado'),
        ('investigacion', 'Investigación'),
        ('extension', 'Extensión'),
    ]

    cargo = models.ForeignKey(
        'Cargo',
        on_delete=models.CASCADE,
        related_name='actividades_sustantivas',
        verbose_name="Cargo"
    )

    categoria = models.CharField(
        max_length=20,
        choices=CATEGORIA_CHOICES,
        verbose_name="Categoría"
    )

    tipo_actividad = models.CharField(
        max_length=30,
        choices=TIPO_ACTIVIDAD_CHOICES,
        verbose_name="Tipo de Actividad"
    )

    asignatura_vinculada = models.ForeignKey(
        'Asignatura',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='actividades_docentes_vinculadas',
        verbose_name="Asignatura Vinculada",
        help_text="Si es docencia en otra asignatura, especificarla aquí"
    )

    descripcion = models.TextField(
        verbose_name="Descripción Detallada",
        help_text="Detalle específico de la función sustantiva"
    )

    horas_semanales = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Horas Semanales Estimadas",
        help_text="Cantidad aproximada de horas dedicadas"
    )

    codigo_proyecto = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Código de Proyecto/Curso",
        help_text="Ej: PID UTN, código de asignatura electiva, etc."
    )

    nombre_proyecto = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Nombre del Proyecto/Curso"
    )

    resolucion_cd = models.ForeignKey(
        'Resolucion',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='actividades_sustantivas_establecidas',
        verbose_name="Resolución de Consejo Directivo",
        help_text="Resolución CD de llamado a concurso que incluye esta función"
    )

    fecha_inicio = models.DateField(
        verbose_name="Fecha de Inicio",
        help_text="Inicio de la función sustantiva"
    )

    fecha_fin = models.DateField(
        null=True,
        blank=True,
        verbose_name="Fecha de Finalización",
        help_text="Fin de la función (dejar vacío si es indefinida)"
    )

    activa = models.BooleanField(
        default=True,
        verbose_name="Activa",
        help_text="Si la función sustantiva está actualmente vigente"
    )

    observaciones = models.TextField(
        blank=True,
        verbose_name="Observaciones"
    )

    fecha_carga = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de Carga"
    )

    ultima_modificacion = models.DateTimeField(
        auto_now=True,
        verbose_name="Última Modificación"
    )

    class Meta:
        verbose_name = "Actividad Sustantiva"
        verbose_name_plural = "Actividades Sustantivas"
        ordering = ['-activa', 'categoria', 'fecha_inicio']
        indexes = [
            models.Index(fields=['cargo', 'activa'],
                         name='actsust_cargo_act_idx'),
            models.Index(fields=['categoria', 'tipo_actividad'],
                         name='actsust_cat_tipo_idx'),
            models.Index(fields=['asignatura_vinculada'],
                         name='actsust_asig_idx'),
            models.Index(fields=['resolucion_cd'], name='actsust_resol_idx'),
        ]

    def clean(self):
        """Validaciones personalizadas"""
        super().clean()
        errors = {}

        tipos_con_asignatura = ['doc_grado_segundo', 'doc_grado_electiva']
        if self.tipo_actividad in tipos_con_asignatura and not self.asignatura_vinculada:
            errors['asignatura_vinculada'] = ValidationError(
                'Este tipo de actividad requiere especificar la asignatura vinculada.',
                code='missing_asignatura'
            )

        if self.tipo_actividad == 'inv_pid' and not self.codigo_proyecto:
            errors['codigo_proyecto'] = ValidationError(
                'Para PID se recomienda incluir el código del proyecto.',
                code='missing_codigo'
            )

        if self.fecha_fin and self.fecha_fin < self.fecha_inicio:
            errors['fecha_fin'] = ValidationError(
                'La fecha de fin no puede ser anterior a la fecha de inicio.',
                code='invalid_dates'
            )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.tipo_actividad.startswith('doc_grado'):
            self.categoria = 'docencia_grado'
        elif self.tipo_actividad.startswith('doc_pos'):
            self.categoria = 'docencia_posgrado'
        elif self.tipo_actividad.startswith('inv'):
            self.categoria = 'investigacion'
        elif self.tipo_actividad.startswith('ext'):
            self.categoria = 'extension'

        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        base = f"{self.get_tipo_actividad_display()}"
        if self.asignatura_vinculada:
            base += f" - {self.asignatura_vinculada.nombre}"
        elif self.nombre_proyecto:
            base += f" - {self.nombre_proyecto}"
        return base

    @property
    def vigente(self):
        """Verifica si la actividad está vigente en la fecha actual"""
        if not self.activa:
            return False

        hoy = timezone.now().date()
        if hoy < self.fecha_inicio:
            return False

        if self.fecha_fin and hoy > self.fecha_fin:
            return False

        return True



class Resolucion(models.Model):
    OBJETO_CHOICES = [
        ("alta", "Alta en el Cargo"),
        ("baja", "Baja en el Cargo"),
        ("designacion", "Designacion"),
        ("puesta_funcion", "Puesta en Funcion"),
        ("licencia_alta", "Alta de Licencia"),
        ("licencia_baja", "Baja de Licencia"),
        ("prorroga_ca", "Prorroga de Carrera Academica"),
    ]
    ORIGEN_CHOICES = [
        ("dec", "Decano"),
        ("cd", "Consejo Directivo"),
        ("rec", "Rector"),
        ("csu", "Consejo Superior"),
    ]

    cargo = models.ForeignKey(
        Cargo, on_delete=models.CASCADE, related_name="resoluciones"
    )
    numero = models.IntegerField()
    año = models.IntegerField()
    objeto = models.CharField(choices=OBJETO_CHOICES, max_length=15)
    origen = models.CharField(choices=ORIGEN_CHOICES, max_length=4)
    file = models.FileField(upload_to="private/resoluciones/", blank=True, null=True)
    # === NUEVOS CAMPOS PARA LICENCIAS ===
    fecha_inicio_licencia = models.DateField(
        "Fecha de Inicio de Licencia",
        null=True,
        blank=True,
        help_text="Solo para resoluciones de tipo 'Alta de Licencia'.",
    )
    fecha_fin_licencia = models.DateField(
        "Fecha de Fin de Licencia",
        null=True,
        blank=True,
        help_text="Solo para resoluciones de tipo 'Alta de Licencia' o 'Baja de Licencia'.",
    )
    genera_prorroga_ca = models.BooleanField(
        "Genera Prórroga en C.A.",
        default=False,
        help_text="Marcar si esta licencia debe extender la fecha de vencimiento de la Carrera Académica.",
    )

    def clean(self):
        """Validaciones a nivel de modelo."""
        super().clean()
        errors = {}

        # Validación 1: Año no puede ser futuro
        current_year = timezone.now().year
        if self.año > current_year:
            errors["año"] = ValidationError(
                f"El año no puede ser futuro. Año actual: {current_year}.",
                code="future_year",
            )

        # Validación 2: Año debe ser razonable (no muy antiguo)
        if self.año < 1950:
            errors["año"] = ValidationError(
                "El año debe ser posterior a 1950.", code="year_too_old"
            )

        # Validación 3: Número de resolución debe ser positivo
        if self.numero <= 0:
            errors["numero"] = ValidationError(
                "El número de resolución debe ser positivo.", code="invalid_numero"
            )

        # Validación 4: Si es prórroga de CA, debe estar asociado a un cargo con CA
        if self.objeto == "prorroga_ca":
            try:
                if not hasattr(self.cargo, "carrera_academica"):
                    errors["objeto"] = ValidationError(
                        "No se puede crear una prórroga para un cargo sin Carrera Académica.",
                        code="no_ca_for_prorroga",
                    )
            except:
                pass  # Si el cargo aún no está asignado, se validará después

        # Validación 5: Validaciones específicas para licencias
        #if self.objeto == "licencia_alta":
        #    if not self.fecha_inicio_licencia:
        #        errors["fecha_inicio_licencia"] = ValidationError(
        #            "Debe especificar la fecha de inicio de la licencia.",
        #            code="missing_license_start",
        #        )
#
        #if self.objeto == "licencia_baja":
        #    if not self.fecha_fin_licencia:
        #        errors["fecha_fin_licencia"] = ValidationError(
        #            "Debe especificar la fecha de fin de la licencia.",
        #            code="missing_license_end",
        #        )

        # Validación 6: Fechas de licencia coherentes
        if self.fecha_inicio_licencia and self.fecha_fin_licencia:
            if self.fecha_fin_licencia <= self.fecha_inicio_licencia:
                errors["fecha_fin_licencia"] = ValidationError(
                    "La fecha de fin debe ser posterior a la fecha de inicio.",
                    code="invalid_license_dates",
                )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        """Override save para ejecutar validaciones."""
        self.full_clean()
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Resolución"
        verbose_name_plural = "Resoluciones"
        ordering = ["-año", "-numero"]
        # Agregar índices
        indexes = [
            # Índice para filtrar por cargo
            models.Index(fields=["cargo"], name="res_cargo_idx"),
            # Índice para filtrar por objeto
            models.Index(fields=["objeto"], name="res_objeto_idx"),
            # Índice para ordenar por año
            models.Index(fields=["año"], name="res_anio_idx"),
            # Índice compuesto para ordenamiento default
            models.Index(fields=["-año", "-numero"], name="res_anio_num_idx"),
            # Índice compuesto: cargo + objeto (búsquedas específicas)
            models.Index(fields=["cargo", "objeto"], name="res_cargo_objeto_idx"),
        ]

    def __str__(self):
        return f"Res. {self.get_origen_display()} {self.numero}/{self.año} - {self.cargo.docente.apellido.upper()}"


class PlanificacionAnual(models.Model):
    """
    Planificación anual de una asignatura.
    Mantiene historial año a año con control de versiones.
    """

    # Relación con asignatura
    asignatura = models.ForeignKey(
        'Asignatura',
        on_delete=models.CASCADE,
        related_name='planificaciones',
        verbose_name="Asignatura"
    )

    # Año lectivo
    año = models.PositiveIntegerField(
        verbose_name="Año lectivo",
        help_text="Año para el cual es válida esta planificación"
    )

    # Archivo
    archivo = models.FileField(
        upload_to='private/planificaciones/%Y/',
        verbose_name="Archivo de planificación",
        help_text="Formatos permitidos: PDF, DOCX (máx. 20MB)"
    )

    archivo_nombre_original = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Nombre original del archivo"
    )

    # Metadatos de carga
    fecha_subida = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de subida"
    )

    subido_por = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='planificaciones_subidas',
        verbose_name="Subido por"
    )

    # Estado del proceso
    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente de recepción'),
        ('enviada', 'Notificación enviada'),
        ('recibida', 'Planificación recibida'),
        ('aprobada', 'Aprobada'),
        ('observada', 'Con observaciones'),
    ]

    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default='pendiente',
        verbose_name="Estado"
    )

    # Docente responsable (al momento de la solicitud)
    docente_responsable = models.ForeignKey(
        'Docente',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='planificaciones_responsable',
        verbose_name="Docente responsable"
    )

    # Observaciones
    observaciones = models.TextField(
        blank=True,
        verbose_name="Observaciones"
    )

    # Aprobación (para uso futuro)
    fecha_aprobacion = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Fecha de aprobación"
    )

    aprobado_por = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='planificaciones_aprobadas',
        verbose_name="Aprobado por"
    )

    # Control de notificaciones
    fecha_ultima_notificacion = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Última notificación enviada"
    )

    cantidad_notificaciones = models.PositiveIntegerField(
        default=0,
        verbose_name="Cantidad de notificaciones enviadas"
    )
    
    archivo = models.FileField(
        upload_to='private/planificaciones/%Y/',
        verbose_name="Archivo de planificación",
        help_text="Formatos permitidos: PDF, DOCX (máx. 20MB)",
        validators=[validar_extension_planificacion,
                    validar_tamaño_planificacion]  # ✅ AGREGAR
    )

    class Meta:
        db_table = 'planta_docente_planificacion_anual'
        unique_together = [['asignatura', 'año']]
        ordering = ['-año', 'asignatura__nombre']
        verbose_name = "Planificación Anual"
        verbose_name_plural = "Planificaciones Anuales"
        indexes = [
            models.Index(fields=['año', 'estado']),
            models.Index(fields=['asignatura', 'año']),
        ]

    def __str__(self):
        return f"{self.asignatura.nombre} - {self.año}"

    def save(self, *args, **kwargs):
        """Override para guardar nombre original del archivo."""
        if self.archivo and not self.archivo_nombre_original:
            self.archivo_nombre_original = self.archivo.name
        super().save(*args, **kwargs)

    @property
    def extension_archivo(self):
        """Retorna la extensión del archivo."""
        import os
        if self.archivo:
            return os.path.splitext(self.archivo.name)[1].lower()
        return ''

    @property
    def tamaño_archivo_mb(self):
        """Retorna el tamaño del archivo en MB."""
        if self.archivo:
            return round(self.archivo.size / (1024 * 1024), 2)
        return 0

    @property
    def tiene_planificacion(self):
        """Indica si ya se subió la planificación."""
        return bool(self.archivo)

    @property
    def dias_desde_ultima_notificacion(self):
        """Calcula días desde la última notificación."""
        if not self.fecha_ultima_notificacion:
            return None
        from django.utils import timezone
        delta = timezone.now() - self.fecha_ultima_notificacion
        return delta.days


class HistorialNotificacionPlanificacion(models.Model):
    """
    Registro histórico de notificaciones enviadas para solicitar planificaciones.
    Permite auditoría completa de comunicaciones.
    """

    # Relación con planificación
    planificacion = models.ForeignKey(
        'PlanificacionAnual',
        on_delete=models.CASCADE,
        related_name='historial_notificaciones',
        verbose_name="Planificación"
    )

    # Destinatario
    destinatario = models.ForeignKey(
        'Docente',
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Docente destinatario"
    )

    email_destinatario = models.EmailField(
        verbose_name="Email destinatario"
    )

    # Contenido del email
    asunto = models.CharField(
        max_length=255,
        verbose_name="Asunto"
    )

    cuerpo = models.TextField(
        verbose_name="Cuerpo del mensaje"
    )

    # Tipo de mensaje
    TIPO_CHOICES = [
        ('generico', 'Mensaje genérico'),
        ('personalizado', 'Mensaje personalizado'),
        ('recordatorio', 'Recordatorio'),
    ]

    tipo_mensaje = models.CharField(
        max_length=20,
        choices=TIPO_CHOICES,
        default='generico',
        verbose_name="Tipo de mensaje"
    )

    # Archivos adjuntos (rutas relativas)
    archivos_adjuntos = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Archivos adjuntos",
        help_text="Lista de rutas de archivos adjuntados"
    )

    ficha_adjunta = models.BooleanField(
        default=False,
        verbose_name="Ficha de asignatura adjunta"
    )

    # Metadatos de envío
    fecha_envio = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de envío"
    )

    enviado_por = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Enviado por"
    )

    # Estado del envío
    enviado_exitosamente = models.BooleanField(
        default=False,
        verbose_name="Enviado exitosamente"
    )

    error_envio = models.TextField(
        blank=True,
        verbose_name="Error de envío"
    )

    class Meta:
        db_table = 'planta_docente_historial_notificacion'
        ordering = ['-fecha_envio']
        verbose_name = "Historial de Notificación"
        verbose_name_plural = "Historial de Notificaciones"
        indexes = [
            models.Index(fields=['planificacion', '-fecha_envio']),
        ]

    def __str__(self):
        return f"Notificación a {self.email_destinatario} - {self.fecha_envio.strftime('%d/%m/%Y')}"


class AsignaturaAnual(models.Model):
    """
    Control de asignaturas activas por año lectivo.
    Permite habilitar/deshabilitar asignaturas para años específicos.
    """
    asignatura = models.ForeignKey(
        'Asignatura',
        on_delete=models.CASCADE,
        related_name='config_anual'
    )

    año = models.PositiveIntegerField(
        verbose_name="Año lectivo"
    )

    activa = models.BooleanField(
        default=True,
        verbose_name="Asignatura activa este año",
        help_text="Desmarcar si la asignatura no se dicta este año"
    )

    motivo_deshabilitacion = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Motivo de deshabilitación",
        help_text="Ej: Plan de estudios discontinuado, asignatura fusionada, etc."
    )

    fecha_modificacion = models.DateTimeField(
        auto_now=True,
        verbose_name="Última modificación"
    )

    modificado_por = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Modificado por"
    )

    class Meta:
        db_table = 'planta_docente_asignatura_anual'
        unique_together = [['asignatura', 'año']]
        ordering = ['-año', 'asignatura__nombre']
        verbose_name = "Configuración Anual de Asignatura"
        verbose_name_plural = "Configuraciones Anuales de Asignaturas"
        indexes = [
            models.Index(fields=['año', 'activa']),
            models.Index(fields=['asignatura', 'año']),
        ]

    def __str__(self):
        estado = "Activa" if self.activa else "Deshabilitada"
        return f"{self.asignatura.nombre} - {self.año} ({estado})"
