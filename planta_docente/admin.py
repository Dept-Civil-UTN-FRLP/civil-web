from django.contrib import admin
from .models import ActividadSustantiva, PlanificacionAnual, HistorialNotificacionPlanificacion
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


@admin.register(PlanificacionAnual)
class PlanificacionAnualAdmin(admin.ModelAdmin):
    """
    Admin para gestión de planificaciones anuales.
    """
    list_display = [
        'asignatura',
        'año',
        'estado_badge',
        'docente_responsable',
        'tiene_archivo',
        'tamaño_mb',
        'fecha_subida',
        'cantidad_notificaciones',
    ]

    list_filter = [
        'año',
        'estado',
        'asignatura__departamento',
        'fecha_subida',
    ]

    search_fields = [
        'asignatura__nombre',
        'docente_responsable__apellido',
        'docente_responsable__nombre',
    ]

    readonly_fields = [
        'fecha_subida',
        'subido_por',
        'fecha_ultima_notificacion',
        'cantidad_notificaciones',
        'archivo_nombre_original',
    ]

    fieldsets = (
        ('Información Básica', {
            'fields': ('asignatura', 'año', 'estado')
        }),
        ('Archivo', {
            'fields': ('archivo', 'archivo_nombre_original')
        }),
        ('Responsable', {
            'fields': ('docente_responsable',)
        }),
        ('Observaciones', {
            'fields': ('observaciones',),
            'classes': ('collapse',)
        }),
        ('Metadatos', {
            'fields': (
                'fecha_subida',
                'subido_por',
                'fecha_ultima_notificacion',
                'cantidad_notificaciones',
            ),
            'classes': ('collapse',)
        }),
    )

    def estado_badge(self, obj):
        """Muestra badge de estado con color."""
        colors = {
            'pendiente': 'gray',
            'enviada': 'blue',
            'recibida': 'green',
            'aprobada': 'darkgreen',
            'observada': 'orange',
        }
        color = colors.get(obj.estado, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px; font-size: 11px;">{}</span>',
            color,
            obj.get_estado_display()
        )
    estado_badge.short_description = 'Estado'

    def tiene_archivo(self, obj):
        """Muestra si tiene archivo subido."""
        if obj.archivo:
            return format_html('<span style="color: green;">✓ Sí</span>')
        return format_html('<span style="color: red;">✗ No</span>')
    tiene_archivo.short_description = 'Archivo'

    def tamaño_mb(self, obj):
        """Muestra tamaño del archivo."""
        if obj.archivo:
            return f"{obj.tamaño_archivo_mb} MB"
        return "-"
    tamaño_mb.short_description = 'Tamaño'

    def save_model(self, request, obj, form, change):
        """Guarda el usuario que sube el archivo."""
        if not change:  # Si es nuevo
            obj.subido_por = request.user
        super().save_model(request, obj, form, change)


@admin.register(HistorialNotificacionPlanificacion)
class HistorialNotificacionAdmin(admin.ModelAdmin):
    """
    Admin para consultar historial de notificaciones.
    Solo lectura.
    """
    list_display = [
        'planificacion',
        'email_destinatario',
        'tipo_mensaje',
        'estado_envio',
        'fecha_envio',
        'enviado_por',
    ]

    list_filter = [
        'tipo_mensaje',
        'enviado_exitosamente',
        'fecha_envio',
        'ficha_adjunta',
    ]

    search_fields = [
        'planificacion__asignatura__nombre',
        'email_destinatario',
        'destinatario__apellido',
        'asunto',
    ]

    readonly_fields = [
        'planificacion',
        'destinatario',
        'email_destinatario',
        'asunto',
        'cuerpo',
        'tipo_mensaje',
        'archivos_adjuntos',
        'ficha_adjunta',
        'fecha_envio',
        'enviado_por',
        'enviado_exitosamente',
        'error_envio',
    ]

    fieldsets = (
        ('Planificación', {
            'fields': ('planificacion',)
        }),
        ('Destinatario', {
            'fields': ('destinatario', 'email_destinatario')
        }),
        ('Contenido', {
            'fields': ('asunto', 'cuerpo', 'tipo_mensaje')
        }),
        ('Adjuntos', {
            'fields': ('archivos_adjuntos', 'ficha_adjunta')
        }),
        ('Estado de Envío', {
            'fields': ('enviado_exitosamente', 'error_envio', 'fecha_envio', 'enviado_por')
        }),
    )

    def estado_envio(self, obj):
        """Muestra estado del envío con color."""
        if obj.enviado_exitosamente:
            return format_html('<span style="color: green;">✓ Exitoso</span>')
        return format_html('<span style="color: red;">✗ Fallido</span>')
    estado_envio.short_description = 'Estado'

    def has_add_permission(self, request):
        """No permitir agregar manualmente."""
        return False

    def has_delete_permission(self, request, obj=None):
        """No permitir eliminar (auditoría)."""
        return False
