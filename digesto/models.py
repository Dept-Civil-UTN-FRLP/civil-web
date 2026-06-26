from django.db import models
from django.utils.text import slugify


class CicloLectivo(models.Model):
    anio = models.PositiveIntegerField(unique=True)

    class Meta:
        ordering = ["-anio"]
        verbose_name = "Ciclo Lectivo"
        verbose_name_plural = "Ciclos Lectivos"

    def __str__(self):
        return str(self.anio)


class Acta(models.Model):
    TIPO_CHOICES = [
        ("ORD", "Ordinaria"),
        ("EXT", "Extraordinaria"),
    ]

    ciclo = models.ForeignKey(CicloLectivo, on_delete=models.PROTECT, related_name="actas")
    tipo = models.CharField(max_length=3, choices=TIPO_CHOICES)
    numero = models.PositiveIntegerField()
    mes = models.CharField(max_length=20)
    contenido_md = models.TextField(blank=True)
    pdf = models.FileField(upload_to="private/digesto/actas/", blank=True, null=True)
    referencias = models.ManyToManyField(
        "self", blank=True, symmetrical=False, related_name="referenciada_por"
    )

    class Meta:
        unique_together = ("ciclo", "tipo", "numero")
        ordering = ["-ciclo__anio", "-numero"]
        verbose_name = "Acta"
        verbose_name_plural = "Actas"

    def __str__(self):
        return self.nombre

    @property
    def nombre(self):
        return f"{self.numero:02d}-{self.get_tipo_display()}-{self.mes.capitalize()}-{self.ciclo.anio}"

    @property
    def slug(self):
        return slugify(self.nombre)


class Disposicion(models.Model):
    acta = models.ForeignKey(Acta, on_delete=models.PROTECT, related_name="disposiciones")
    numero = models.PositiveIntegerField()
    texto = models.TextField()
    deroga = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="derogada_por"
    )
    modifica = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="modificada_por"
    )

    class Meta:
        unique_together = ("acta", "numero")
        ordering = ["acta__ciclo__anio", "acta__numero", "numero"]
        verbose_name = "Disposición"
        verbose_name_plural = "Disposiciones"

    def __str__(self):
        return f"Disp. {self.numero} — {self.acta}"

    @property
    def estado(self):
        if self.derogada_por.exists():
            return "derogada"
        if self.modificada_por.exists():
            return "modificada"
        return "vigente"


class Certificacion(models.Model):
    acta = models.ForeignKey(Acta, on_delete=models.PROTECT, related_name="certificaciones")
    numero = models.PositiveIntegerField()
    texto = models.TextField()

    class Meta:
        unique_together = ("acta", "numero")
        ordering = ["acta__ciclo__anio", "acta__numero", "numero"]
        verbose_name = "Certificación"
        verbose_name_plural = "Certificaciones"

    def __str__(self):
        return f"Cert. {self.numero} — {self.acta}"
