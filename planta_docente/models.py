from django.db import models
from django.db.models.signals import pre_save
from django.dispatch import receiver

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


class Docente(models.Model):
    nombre = models.CharField(max_length=50)
    apellido = models.CharField(max_length=50)
    documento = models.IntegerField(unique=True)
    legajo = models.IntegerField(unique=True)
    fecha_nacimiento = models.DateField(default="1900-01-01")

    def __str__(self) -> str:
        return f"{self.apellido.upper()}, {self.nombre.title()}"

    def save(self, *args, **kwargs):
        self.nombre = self.nombre.lower()
        self.apellido = self.apellido.lower()
        super().save(*args, **kwargs)


class Correo(models.Model):
    email = models.EmailField()
    principal = models.BooleanField(default=True)
    docente = models.ForeignKey(
        "Docente", related_name="correos", on_delete=models.CASCADE
    )

    def __str__(self) -> str:
        return f"{self.docente.apellido.upper()}, {self.docente.nombre.title()} <{self.email.lower()}>"

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

    def __str__(self):
        return f"Res. {self.get_origen_display()} {self.numero}/{self.año} - {self.cargo.docente.apellido.upper()}"
