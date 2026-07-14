from django.contrib import admin

from .models import Acta, Certificacion, CicloLectivo, Disposicion


class ActaInline(admin.TabularInline):
    model = Acta
    extra = 0
    fields = ("numero", "tipo", "mes", "pdf")
    show_change_link = True


@admin.register(CicloLectivo)
class CicloLectivoAdmin(admin.ModelAdmin):
    list_display = ("anio",)
    inlines = [ActaInline]


class DisposicionInline(admin.TabularInline):
    model = Disposicion
    extra = 0
    fields = ("numero", "texto", "deroga", "modifica")
    show_change_link = True


class CertificacionInline(admin.TabularInline):
    model = Certificacion
    extra = 0
    fields = ("numero", "texto")


@admin.register(Acta)
class ActaAdmin(admin.ModelAdmin):
    list_display = ("__str__", "ciclo", "tipo", "numero", "mes")
    list_filter = ("ciclo", "tipo")
    search_fields = ("numero", "mes", "contenido_md")
    inlines = [DisposicionInline, CertificacionInline]
    filter_horizontal = ("referencias",)


@admin.register(Disposicion)
class DisposicionAdmin(admin.ModelAdmin):
    list_display = ("__str__", "acta", "numero", "estado")
    list_filter = ("acta__ciclo",)
    search_fields = ("numero", "texto")
    raw_id_fields = ("acta", "deroga", "modifica")

    @admin.display(description="Estado")
    def estado(self, obj):
        return obj.estado


@admin.register(Certificacion)
class CertificacionAdmin(admin.ModelAdmin):
    list_display = ("__str__", "acta", "numero")
    list_filter = ("acta__ciclo",)
    search_fields = ("numero", "texto")
    raw_id_fields = ("acta",)
