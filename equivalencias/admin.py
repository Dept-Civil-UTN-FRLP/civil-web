# equivalencias/admin.py

from django.contrib import admin
from .models import (
    AsignaturaParaEquivalencia,
    Estudiante,
    SolicitudEquivalencia,
    DetalleSolicitud,
    DocumentoAdjunto,
)

# Definimos una clase para mostrar los documentos "inline"


class DocumentoAdjuntoInline(admin.TabularInline):
    model = DocumentoAdjunto
    extra = 1  # Muestra un campo para subir un archivo extra por defecto


@admin.register(AsignaturaParaEquivalencia)
class AsignaturaParaEquivalenciaAdmin(admin.ModelAdmin):
    """
    Personalización del admin para el modelo AsignaturaParaEquivalencia.
    """

    # 1. DEFINE LAS COLUMNAS A MOSTRAR EN LA LISTA
    # Accedemos a los campos del modelo relacionado 'AsignaturaCA'
    list_display = (
        '__str__',  # Muestra el nombre de la asignatura
        'get_nivel',  # Usamos una función para obtener el nivel
        'docente_responsable'
    )

    # 2. AÑADE EL FILTRO POR NIVEL (LA SOLUCIÓN A TU PREGUNTA)
    # Esto creará el bloque de filtros a la derecha
    list_filter = ('asignatura__nivel',)

    # 3. (OPCIONAL PERO RECOMENDADO) AÑADE UNA BARRA DE BÚSQUEDA
    # Permite buscar por el nombre de la asignatura
    search_fields = ('asignatura__nombre',)

    # Función para mostrar el nivel en list_display de forma ordenada
    @admin.display(description='Nivel', ordering='asignatura__nivel')
    def get_nivel(self, obj):
        return obj.asignatura.nivel


class SolicitudEquivalenciaAdmin(admin.ModelAdmin):
    inlines = [DocumentoAdjuntoInline]
    list_display = ('__str__', 'estado_general', 'fecha_inicio')
    list_filter = ('estado_general',)
    search_fields = ('id_estudiante__nombre_completo',)

    # ✅ OPTIMIZACIÓN: Optimizar queries en el admin
    def get_queryset(self, request):
        """Override para optimizar queries."""
        qs = super().get_queryset(request)
        return qs.select_related('id_estudiante').prefetch_related(
            'detallesolicitud_set',
            'documentoadjunto_set',
        )


#admin.site.register(AsignaturaParaEquivalencia)
admin.site.register(Estudiante)
admin.site.register(SolicitudEquivalencia, SolicitudEquivalenciaAdmin)
admin.site.register(DetalleSolicitud)
admin.site.register(DocumentoAdjunto)
