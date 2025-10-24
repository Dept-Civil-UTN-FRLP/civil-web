# carrera_academica/admin.py

from django.contrib import admin
from .models import *
from datetime import date  # Importamos date para el cálculo de la edad

# ==============================================================================
# REGISTROS SIMPLES
# ==============================================================================
admin.site.register(Area)
admin.site.register(Bloque)
admin.site.register(Correo)
# Lo registramos para consultas, aunque se maneja inline
admin.site.register(Formulario)
admin.site.register(JuntaEvaluadora)
admin.site.register(MiembroExterno)
admin.site.register(Veedor)
admin.site.register(MembreteAnual)

# ==============================================================================
# CONFIGURACIONES DE ADMIN DETALLADAS
# ==============================================================================


class AsignaturaAdmin(admin.ModelAdmin):
    list_display = (
        "nombre",
        "nivel",
        "puntaje",
        "departamento",
        "especialidad",
        "obligatoria",
        "mostrar_bloque",
        "mostrar_area",
        "dictado",
        "hora_total",
        "hora_semanal",
    )
    search_fields = ("nombre",)
    list_filter = (
        "nivel",
        "puntaje",
        "departamento",
        "especialidad",
        "obligatoria",
        "area",
        "bloque",
        "hora_total",
        "hora_semanal",
    )

    def mostrar_bloque(self, obj):
        return ", ".join([bloque.nombre.title() for bloque in obj.bloque.all()])

    mostrar_bloque.short_description = "Bloques"

    def mostrar_area(self, obj):
        # <<< CORRECCIÓN: Ahora itera sobre obj.area.all()
        return ", ".join([area.nombre.title() for area in obj.area.all()])

    mostrar_area.short_description = "Áreas"


class CorreoInline(admin.TabularInline):
    model = Correo
    extra = 1


class DocenteAdmin(admin.ModelAdmin):
    list_display = (
        "legajo",
        "apellido",
        "nombre",
        "documento",
        "edad",
        "correo_principal",
        "otros_correos",
    )
    search_fields = ("legajo", "nombre", "apellido", "documento")
    # Permite añadir/editar correos desde la página del docente
    inlines = [CorreoInline]

    # ✅ OPTIMIZACIÓN: prefetch_related para correos
    def get_queryset(self, request):
        """Override para optimizar queries."""
        qs = super().get_queryset(request)
        return qs.prefetch_related('correos')

    def correo_principal(self, obj):
        correo_principal = obj.correos.filter(principal=True).first()
        return correo_principal.email if correo_principal else "N/A"

    correo_principal.short_description = "Correo Principal"

    def otros_correos(self, obj):
        correos = obj.correos.exclude(principal=True)
        return (
            "; ".join([correo.email for correo in correos])
            if correos.exists()
            else "N/A"
        )

    otros_correos.short_description = "Otros Correos"

    def edad(self, obj):
        today = date.today()
        age = (
            today.year
            - obj.fecha_nacimiento.year
            - (
                (today.month, today.day)
                < (obj.fecha_nacimiento.month, obj.fecha_nacimiento.day)
            )
        )
        return f"{age} años"

    edad.short_description = "Edad"


class ResolucionInline(admin.TabularInline):
    model = Resolucion
    extra = 0
    fields = ("numero", "año", "objeto", "origen", "file")


class CargoAdmin(admin.ModelAdmin):
    list_display = (
        "docente",
        "asignatura",
        "caracter",
        "categoria",
        "dedicacion",
        "estado",
    )
    search_fields = ("docente__apellido", "docente__nombre", "asignatura__nombre")
    list_filter = ("caracter", "categoria", "dedicacion", "estado")
    # <<< ADAPTACIÓN: Muestra las resoluciones dentro del cargo
    inlines = [ResolucionInline]


class ResolucionAdmin(admin.ModelAdmin):
    list_display = ("__str__", "cargo", "objeto", "file")
    search_fields = ("numero", "año", "objeto", "origen", "cargo__docente__apellido")
    list_filter = ("año", "objeto", "origen")


# --- CONFIGURACIÓN PARA CARRERA ACADÉMICA ---


class FormularioInline(admin.TabularInline):
    model = Formulario
    extra = 0
    fields = (
        "tipo_formulario",
        "estado",
        "fecha_entrega",
        "anio_correspondiente",
        "evaluacion",
        "archivo",
    )
    readonly_fields = ("tipo_formulario", "anio_correspondiente", "evaluacion")


# Stacked se ve mejor para este caso
class JuntaEvaluadoraInline(admin.StackedInline):
    model = JuntaEvaluadora


# Creamos un nuevo inline para mostrar las Evaluaciones dentro de CarreraAcademica
class EvaluacionInline(admin.TabularInline):
    model = Evaluacion
    extra = 0
    fields = ("numero_evaluacion", "estado", "fecha_evaluacion", "anios_evaluados")
    readonly_fields = ("numero_evaluacion", "anios_evaluados")
    show_change_link = True


class CarreraAcademicaAdmin(admin.ModelAdmin):
    # Mostramos el nuevo número de expediente en el listado
    list_display = (
        "__str__",
        "numero_expediente",
        "estado",
        "fecha_vencimiento_actual",
        "progreso_formularios",
    )
    list_filter = ("estado",)
    search_fields = ("cargo__docente__apellido", "numero_expediente")
    inlines = [JuntaEvaluadoraInline, EvaluacionInline, FormularioInline]

    # ✅ OPTIMIZACIÓN: select_related y prefetch_related en el admin
    def get_queryset(self, request):
        """Override para optimizar queries en el listado del admin."""
        qs = super().get_queryset(request)
        return qs.select_related(
            'cargo',
            'cargo__docente',
            'cargo__asignatura',
        ).prefetch_related(
            'formularios',
        )

    # Organizamos los campos en secciones para que el formulario sea más claro
    fieldsets = (
        ("Información General", {"fields": ("cargo", "numero_expediente", "estado")}),
        (
            "Resoluciones de Inicio",
            {"fields": ("resolucion_designacion", "resolucion_puesta_en_funcion")},
        ),
        (
            "Fechas Clave",
            {
                "fields": (
                    "fecha_inicio",
                    "fecha_vencimiento_original",
                    "fecha_vencimiento_actual",
                )
            },
        ),
    )

    def progreso_formularios(self, obj):
        entregados = obj.formularios.filter(estado="ENT").count()
        total = obj.formularios.count()
        return f"{entregados} de {total} entregados"

    progreso_formularios.short_description = "Progreso Formularios"


class PlantillaDocumentoAdmin(admin.ModelAdmin):
    list_display = ("tipo_formulario", "descripcion", "archivo")
    list_filter = ("tipo_formulario",)


class EvaluacionAdmin(admin.ModelAdmin):
    list_display = ("__str__", "estado", "fecha_evaluacion")
    inlines = []


# ==============================================================================
# REGISTROS FINALES
# ==============================================================================
admin.site.register(Asignatura, AsignaturaAdmin)
admin.site.register(Docente, DocenteAdmin)
admin.site.register(Cargo, CargoAdmin)
admin.site.register(Resolucion, ResolucionAdmin)
admin.site.register(CarreraAcademica, CarreraAcademicaAdmin)
admin.site.register(PlantillaDocumento, PlantillaDocumentoAdmin)
admin.site.register(Evaluacion, EvaluacionAdmin)
