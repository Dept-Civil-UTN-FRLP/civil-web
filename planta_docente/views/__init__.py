# Importar todas las vistas del módulo principal
from .main import *
from .estructura_catedra import *
from .funciones_sustantivas import *
from .planificaciones import *


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
    'editar_licencia_mayor_jerarquia_view',
    'crear_resolucion_csu_ajax',
    # Vistas de estructura de cátedra
    'dashboard_asignaturas',
    'formulario_estructura',
    'generar_pdf_estructura',
    'ver_ficha_asignatura',
    'editar_ficha_asignatura',
    # Vistas de funciones sustantivas
    'gestionar_funciones_sustantivas',
    'crear_funcion_sustantiva',
    'editar_funcion_sustantiva',
    'eliminar_funcion_sustantiva',
    'toggle_activa_funcion_sustantiva',
    # Vistas de planificaciones
    'dashboard_planificaciones',
    'subir_planificacion',
    'descargar_planificacion',
    'eliminar_planificacion',
    'vista_previa_notificacion',
]
