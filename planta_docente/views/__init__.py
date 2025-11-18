# Importar todas las vistas del módulo principal
from .main import *

# Importar vistas de estructura de cátedra
from .estructura_catedra import (
    dashboard_asignaturas,
    formulario_estructura,
    generar_pdf_estructura
)

__all__ = [
    # Vistas principales (del views.py original)
    'dashboard_planta_view',
    'detalle_cargo_view',
    'detalle_docente_view',
    'vencimientos_view',
    'jubilaciones_view',
    'cargos_sin_ca_view',
    'iniciar_ca_desde_cargo_view',
    'cargo_info_api_view',
    'cargos_renovacion_view',
    'renovar_cargo_ajax',
    'exportar_renovaciones_excel',
    'crear_cargo_view',
    'editar_cargo_view',
    'gestionar_resoluciones_cargo',
    'crear_resolucion_cargo',
    'eliminar_resolucion_cargo',
    'gestionar_licencia_cargo',
    'gestionar_continuidad_cargo',
    'ver_historial_continuidad_docente',
    'gestionar_mayor_jerarquia_cargo',
    # Vistas de estructura de cátedra
    'dashboard_asignaturas',
    'formulario_estructura',
    'generar_pdf_estructura',
]
