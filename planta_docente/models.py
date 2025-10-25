from django.db import models
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.core.exceptions import ValidationError
from django.utils import timezone

# Create your models here.


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

    nombre = models.CharField(max_length=50)
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
            models.Index(fields=['nivel'], name='asig_nivel_idx'),

            # Índice para filtrar por departamento
            models.Index(fields=['departamento'], name='asig_depto_idx'),

            # Índice para filtrar por especialidad
            models.Index(fields=['especialidad'],
                         name='asig_especialidad_idx'),

            # Índice para ordenar: obligatoria + nivel
            models.Index(
                fields=['-obligatoria', 'nivel'],
                name='asig_oblig_nivel_idx'
            ),
        ]


class Docente(models.Model):
    nombre = models.CharField(max_length=50)
    apellido = models.CharField(max_length=50)
    documento = models.IntegerField(unique=True)
    legajo = models.IntegerField(unique=True)
    fecha_nacimiento = models.DateField(default="1900-01-01")

    def clean(self):
        """Validaciones a nivel de modelo."""
        super().clean()
        errors = {}

        # Validación 1: Fecha de nacimiento no puede ser futura
        if self.fecha_nacimiento and self.fecha_nacimiento > timezone.now().date():
            errors['fecha_nacimiento'] = ValidationError(
                'La fecha de nacimiento no puede ser futura.',
                code='future_birth_date'
            )

        # Validación 2: El docente debe tener al menos 18 años
        if self.fecha_nacimiento:
            today = timezone.now().date()
            age = today.year - self.fecha_nacimiento.year - (
                (today.month, today.day) < (
                    self.fecha_nacimiento.month, self.fecha_nacimiento.day)
            )
            if age < 18:
                errors['fecha_nacimiento'] = ValidationError(
                    'El docente debe tener al menos 18 años.',
                    code='underage'
                )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        """Override save para ejecutar validaciones."""
        self.full_clean()
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Docente"
        verbose_name_plural = "Docentes"
        # Agregar índices
        indexes = [
            # Índice para búsqueda por legajo (único, pero útil)
            models.Index(fields=['legajo'], name='doc_legajo_idx'),

            # Índice para búsqueda por documento (único, pero útil)
            models.Index(fields=['documento'], name='doc_documento_idx'),

            # Índice para búsqueda por apellido (muy común en búsquedas)
            models.Index(fields=['apellido'], name='doc_apellido_idx'),

            # Índice compuesto: apellido + nombre (búsqueda completa)
            models.Index(
                fields=['apellido', 'nombre'],
                name='doc_apellido_nombre_idx'
            ),
        ]

    def __str__(self) -> str:
        return f"{self.apellido.upper()}, {self.nombre.title()}"    


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
            models.Index(fields=['docente'], name='correo_docente_idx'),

            # Índice compuesto: docente + principal (query muy común)
            models.Index(
                fields=['docente', 'principal'],
                name='correo_doc_principal_idx'
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
    ]
    DEDICACION_CHOICES = [
        ("ds", "Simple"),
        ("se", "Semi-Exclusiva"),
        ("de", "Exclusiva"),
    ]
    ESTADO_CHOICES = [("activo", "Activo"), ("licencia", "Licencia"), ("baja", "Baja")]

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
    fecha_vencimiento = models.DateField(blank=True, null=True)
    estado = models.CharField(choices=ESTADO_CHOICES, max_length=10, default="activo")

    def clean(self):
        """Validaciones a nivel de modelo."""
        super().clean()
        errors = {}

        # Validación 1: Fecha final debe ser posterior a fecha inicio
        if self.fecha_final and self.fecha_inicio:
            if self.fecha_final <= self.fecha_inicio:
                errors['fecha_final'] = ValidationError(
                    'La fecha final debe ser posterior a la fecha de inicio.',
                    code='invalid_date_range'
                )

        # Validación 2: Fecha de vencimiento debe ser posterior a fecha inicio
        if self.fecha_vencimiento and self.fecha_inicio:
            if self.fecha_vencimiento <= self.fecha_inicio:
                errors['fecha_vencimiento'] = ValidationError(
                    'La fecha de vencimiento debe ser posterior a la fecha de inicio.',
                    code='invalid_vencimiento'
                )

        # Validación 3: Solo cargos regulares u ordinarios pueden tener fecha de vencimiento
        if self.fecha_vencimiento and self.caracter not in ['reg', 'ord']:
            errors['fecha_vencimiento'] = ValidationError(
                'Solo los cargos Regulares u Ordinarios tienen fecha de vencimiento.',
                code='invalid_vencimiento_for_caracter'
            )

        # Validación 4: Cargos Ad-Honorem no pueden tener dedicación exclusiva o semi
        if self.caracter == 'adh' and self.dedicacion in ['de', 'se']:
            errors['dedicacion'] = ValidationError(
                'Los cargos Ad-Honorem no pueden tener dedicación exclusiva o semi-exclusiva.',
                code='invalid_dedication_for_adhonorem'
            )

        # Validación 5: Validar horas según dedicación
        horas_esperadas = {
            'ds': 10,
            'se': 20,
            'de': 40
        }

        if self.dedicacion in horas_esperadas:
            # 80% del esperado
            horas_min = horas_esperadas[self.dedicacion] * 0.8
            # 120% del esperado
            horas_max = horas_esperadas[self.dedicacion] * 1.2

            if not (horas_min <= self.cantidad_horas <= horas_max):
                errors['cantidad_horas'] = ValidationError(
                    f'Para dedicación {self.get_dedicacion_display()}, se esperan aproximadamente '
                    f'{horas_esperadas[self.dedicacion]} horas (rango: {horas_min}-{horas_max}).',
                    code='invalid_hours_for_dedication'
                )

        # Validación 6: No puede haber cargos solapados para el mismo docente en la misma asignatura
        if self.estado == 'activo':
            cargos_solapados = Cargo.objects.filter(
                docente=self.docente,
                asignatura=self.asignatura,
                estado='activo'
            ).exclude(pk=self.pk)

            if cargos_solapados.exists():
                errors['asignatura'] = ValidationError(
                    f'El docente ya tiene un cargo activo en {self.asignatura.nombre}.',
                    code='duplicate_active_cargo'
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
        # Agregar índices
        indexes = [
            # Índice para filtrar por docente
            models.Index(fields=['docente'], name='cargo_docente_idx'),

            # Índice para filtrar por asignatura
            models.Index(fields=['asignatura'], name='cargo_asignatura_idx'),

            # Índice para filtrar por estado
            models.Index(fields=['estado'], name='cargo_estado_idx'),

            # Índice para filtrar por carácter
            models.Index(fields=['caracter'], name='cargo_caracter_idx'),

            # Índice compuesto: estado + carácter (query común para CA)
            models.Index(
                fields=['estado', 'caracter'],
                name='cargo_estado_caracter_idx'
            ),

            # Índice compuesto: docente + asignatura (evitar duplicados)
            models.Index(
                fields=['docente', 'asignatura'],
                name='cargo_doc_asig_idx'
            ),

            # Índice para ordenar por fecha de inicio
            models.Index(fields=['fecha_inicio'],
                         name='cargo_fecha_inicio_idx'),
        ]

    def __str__(self) -> str:
        return f"{self.docente.apellido.upper()} ({self.get_caracter_display()} en {self.asignatura.nombre.title()})"


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
    file = models.FileField(upload_to="resoluciones/", blank=True, null=True)
    # === NUEVOS CAMPOS PARA LICENCIAS ===
    fecha_inicio_licencia = models.DateField(
        "Fecha de Inicio de Licencia",
        null=True, blank=True,
        help_text="Solo para resoluciones de tipo 'Alta de Licencia'."
    )
    fecha_fin_licencia = models.DateField(
        "Fecha de Fin de Licencia",
        null=True, blank=True,
        help_text="Solo para resoluciones de tipo 'Alta de Licencia' o 'Baja de Licencia'."
    )
    genera_prorroga_ca = models.BooleanField(
        "Genera Prórroga en C.A.",
        default=False,
        help_text="Marcar si esta licencia debe extender la fecha de vencimiento de la Carrera Académica."
    )

    def clean(self):
        """Validaciones a nivel de modelo."""
        super().clean()
        errors = {}

        # Validación 1: Año no puede ser futuro
        current_year = timezone.now().year
        if self.año > current_year:
            errors['año'] = ValidationError(
                f'El año no puede ser futuro. Año actual: {current_year}.',
                code='future_year'
            )

        # Validación 2: Año debe ser razonable (no muy antiguo)
        if self.año < 1950:
            errors['año'] = ValidationError(
                'El año debe ser posterior a 1950.',
                code='year_too_old'
            )

        # Validación 3: Número de resolución debe ser positivo
        if self.numero <= 0:
            errors['numero'] = ValidationError(
                'El número de resolución debe ser positivo.',
                code='invalid_numero'
            )

        # Validación 4: Si es prórroga de CA, debe estar asociado a un cargo con CA
        if self.objeto == 'prorroga_ca':
            try:
                if not hasattr(self.cargo, 'carrera_academica'):
                    errors['objeto'] = ValidationError(
                        'No se puede crear una prórroga para un cargo sin Carrera Académica.',
                        code='no_ca_for_prorroga'
                    )
            except:
                pass  # Si el cargo aún no está asignado, se validará después

        # Validación 5: Validaciones específicas para licencias
        if self.objeto == 'licencia_alta':
            if not self.fecha_inicio_licencia:
                errors['fecha_inicio_licencia'] = ValidationError(
                    'Debe especificar la fecha de inicio de la licencia.',
                    code='missing_license_start'
                )

        if self.objeto == 'licencia_baja':
            if not self.fecha_fin_licencia:
                errors['fecha_fin_licencia'] = ValidationError(
                    'Debe especificar la fecha de fin de la licencia.',
                    code='missing_license_end'
                )

        # Validación 6: Fechas de licencia coherentes
        if self.fecha_inicio_licencia and self.fecha_fin_licencia:
            if self.fecha_fin_licencia <= self.fecha_inicio_licencia:
                errors['fecha_fin_licencia'] = ValidationError(
                    'La fecha de fin debe ser posterior a la fecha de inicio.',
                    code='invalid_license_dates'
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
        ordering = ['-año', '-numero']
        # Agregar índices
        indexes = [
            # Índice para filtrar por cargo
            models.Index(fields=['cargo'], name='res_cargo_idx'),

            # Índice para filtrar por objeto
            models.Index(fields=['objeto'], name='res_objeto_idx'),

            # Índice para ordenar por año
            models.Index(fields=['año'], name='res_anio_idx'),

            # Índice compuesto para ordenamiento default
            models.Index(
                fields=['-año', '-numero'],
                name='res_anio_num_idx'
            ),

            # Índice compuesto: cargo + objeto (búsquedas específicas)
            models.Index(
                fields=['cargo', 'objeto'],
                name='res_cargo_objeto_idx'
            ),
        ]

    def __str__(self):
        return f"Res. {self.get_origen_display()} {self.numero}/{self.año} - {self.cargo.docente.apellido.upper()}"
