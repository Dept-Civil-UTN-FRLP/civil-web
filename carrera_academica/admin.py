# carrera_academica/admin.py

from datetime import date  # Importamos date para el cálculo de la edad

from django.contrib import admin

from .models import *
from planta_docente.models import *

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


class ActividadSustantivaInline(admin.TabularInline):
    model = ActividadSustantiva
    extra = 0
    fields = [
        'tipo_actividad',
        'asignatura_vinculada',
        'horas_semanales',
        'resolucion_cd',
        'activa',
    ]
    autocomplete_fields = ['asignatura_vinculada', 'resolucion_cd']

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('asignatura_vinculada', 'resolucion_cd')

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
        return qs.prefetch_related("correos")

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
    inlines = [ActividadSustantivaInline, ResolucionInline]



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
            "cargo",
            "cargo__docente",
            "cargo__asignatura",
        ).prefetch_related(
            "formularios",
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


@admin.register(VeedorGraduado)
class VeedorGraduadoAdmin(admin.ModelAdmin):
    list_display = ['apellido', 'nombre', 'email', 'titulo', 'año_egreso']
    search_fields = ['apellido', 'nombre', 'email']
    list_filter = ['año_egreso']


@admin.register(VeedorEstudiante)
class VeedorEstudianteAdmin(admin.ModelAdmin):
    list_display = ['apellido', 'nombre', 'legajo', 'email']
    search_fields = ['apellido', 'nombre', 'legajo', 'email']


@admin.register(Jurado)
class JuradoAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'departamento',
                    'activo', 'fecha_creacion', 'cantidad_cas']
    list_filter = ['departamento', 'activo', 'fecha_creacion']
    search_fields = ['nombre', 'notas']
    readonly_fields = ['nombre', 'fecha_creacion']

    fieldsets = (
        ('Información General', {
            'fields': ('nombre', 'departamento', 'activo', 'fecha_creacion', 'notas')
        }),
        ('Profesores Titulares', {
            'fields': (
                ('profesor_titular_1', 'profesor_suplente_1'),
                ('profesor_titular_2', 'profesor_suplente_2'),
                ('profesor_titular_3', 'profesor_suplente_3'),
            )
        }),
        ('Veedores', {
            'fields': (
                ('veedor_graduado_titular', 'veedor_graduado_suplente'),
                ('veedor_estudiante_titular', 'veedor_estudiante_suplente'),
            )
        }),
    )

    def cantidad_cas(self, obj):
        return obj.get_cantidad_cas()
    cantidad_cas.short_description = 'CAs Asignadas'


@admin.register(Universidad)
class UniversidadAdmin(admin.ModelAdmin):
    list_display = ['sigla', 'nombre_completo',
                    'es_utn', 'regional', 'cantidad_jurados']
    list_filter = ['es_utn']
    search_fields = ['sigla', 'nombre_completo']

    def cantidad_jurados(self, obj):
        return obj.jurados_externos.count()
    cantidad_jurados.short_description = 'Jurados Externos'


@admin.register(JuradoExterno)
class JuradoExternoAdmin(admin.ModelAdmin):
    list_display = ['apellido', 'nombre', 'universidad',
                    'categoria', 'es_investigador', 'es_jubilado', 'activo']
    list_filter = ['categoria', 'es_investigador',
                   'es_jubilado', 'activo', 'universidad']
    search_fields = ['apellido', 'nombre', 'email']
    readonly_fields = ['fecha_alta']

    fieldsets = (
        ('Información Personal', {
            'fields': ('apellido', 'nombre', 'email', 'telefono')
        }),
        ('Datos Institucionales', {
            'fields': ('universidad', 'categoria', 'es_investigador', 'es_jubilado')
        }),
        ('Documentación', {
            'fields': ('archivo_resolucion', 'notas')
        }),
        ('Estado', {
            'fields': ('activo', 'fecha_alta')
        }),
    )
