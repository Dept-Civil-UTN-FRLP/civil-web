"""
Validadores personalizados para archivos de planificación.
"""
import os
from django.core.exceptions import ValidationError
from django.conf import settings


def validar_extension_planificacion(value):
    """
    Valida que el archivo tenga extensión permitida (.pdf o .docx).
    
    Args:
        value: FileField value
    
    Raises:
        ValidationError: Si la extensión no es válida
    """
    ext = os.path.splitext(value.name)[1].lower()

    extensiones_permitidas = getattr(
        settings,
        'ALLOWED_PLANIFICACION_EXTENSIONS',
        ['.pdf', '.docx']
    )

    if ext not in extensiones_permitidas:
        raise ValidationError(
            f'Extensión no permitida. Solo se aceptan archivos: {", ".join(extensiones_permitidas)}'
        )


def validar_tamaño_planificacion(value):
    """
    Valida que el archivo no exceda el tamaño máximo.
    
    Args:
        value: FileField value
    
    Raises:
        ValidationError: Si el archivo es muy grande
    """
    max_size = getattr(settings, 'MAX_UPLOAD_SIZE', 20 *
                       1024 * 1024)  # 20MB por defecto

    if value.size > max_size:
        max_mb = max_size / (1024 * 1024)
        actual_mb = round(value.size / (1024 * 1024), 2)
        raise ValidationError(
            f'El archivo es muy grande ({actual_mb} MB). Tamaño máximo: {max_mb} MB'
        )
