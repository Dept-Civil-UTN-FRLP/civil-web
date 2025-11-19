from django.contrib import admin
from .models import ActividadSustantiva
from django.utils.html import format_html

@admin.register(ActividadSustantiva)
class ActividadSustantivaAdmin(admin.ModelAdmin):
    list_display = [
        'cargo',
        'get_docente',
        'tipo_actividad',
        'asignatura_vinculada',
        'horas_semanales',
        'activa',
        'vigente_badge',
        'resolucion_cd',
    ]

    list_filter = [
        'activa',
        'categoria',
        'tipo_actividad',
        'fecha_inicio',
    ]

    search_fields = [
        'cargo__docente__apellido',
        'cargo__docente__nombre',
        'descripcion',
        'nombre_proyecto',
        'codigo_proyecto',
    ]

    autocomplete_fields = ['cargo', 'asignatura_vinculada', 'resolucion_cd']

    fieldsets = (
        ('Información Principal', {
            'fields': (
                'cargo',
                'tipo_actividad',
                'descripcion',
            )
        }),
        ('Asignatura Vinculada', {
            'fields': ('asignatura_vinculada',),
            'classes': ('collapse',),
            'description': 'Solo para actividades de docencia en otra asignatura'
        }),
        ('Proyecto/Curso', {
            'fields': (
                'codigo_proyecto',
                'nombre_proyecto',
            ),
            'classes': ('collapse',),
        }),
        ('Carga Horaria', {
            'fields': ('horas_semanales',),
        }),
        ('Resolución y Fechas', {
            'fields': (
                'resolucion_cd',
                'fecha_inicio',
                'fecha_fin',
                'activa',
            )
        }),
        ('Observaciones', {
            'fields': ('observaciones',),
            'classes': ('collapse',),
        }),
    )

    readonly_fields = ['fecha_carga', 'ultima_modificacion']

    date_hierarchy = 'fecha_inicio'

    def get_docente(self, obj):
        return obj.cargo.docente
    get_docente.short_description = 'Docente'
    get_docente.admin_order_field = 'cargo__docente__apellido'

    def vigente_badge(self, obj):
        if obj.vigente:
            return format_html(
                '<span style="color: green; font-weight: bold;">✓ Vigente</span>'
            )
        return format_html(
            '<span style="color: gray;">⊗ No Vigente</span>'
        )
    vigente_badge.short_description = 'Estado'

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related(
            'cargo__docente',
            'cargo__asignatura',
            'asignatura_vinculada',
            'resolucion_cd'
        )
