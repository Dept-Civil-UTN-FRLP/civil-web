# carrera_academica/validators.py
"""
Validadores personalizados y mensajes de error.
"""
from django.core.exceptions import ValidationError
from django.utils import timezone


def validate_expediente_format(value):
    """Validador para el formato de número de expediente."""
    import re
    pattern = r'^\d{4,6}/\d{4}$'

    if not re.match(pattern, value):
        raise ValidationError(
            'El formato debe ser NNNNN/AAAA (ej: 12345/2024)',
            params={'value': value},
            code='invalid_format'
        )


def validate_year_in_range(year):
    """Validador para años razonables."""
    current_year = timezone.now().year

    if year > current_year:
        raise ValidationError(
            f'El año no puede ser futuro. Año actual: {current_year}',
            params={'year': year},
            code='future_year'
        )

    if year < 2000:
        raise ValidationError(
            'El año debe ser posterior a 2000',
            params={'year': year},
            code='year_too_old'
        )


# Mensajes de error personalizados
ERROR_MESSAGES = {
    'ca': {
        'invalid_caracter': 'Solo los cargos Regulares u Ordinarios pueden tener Carrera Académica.',
        'invalid_date_range': 'La fecha de vencimiento debe ser posterior a la fecha de inicio.',
        'duration_too_short': 'La Carrera Académica debe tener una duración mínima de 2 años.',
        'duplicate_active_ca': 'Ya existe una Carrera Académica activa para este cargo.',
    },
    'evaluacion': {
        'year_before_ca_start': 'El año es anterior al inicio de la Carrera Académica.',
        'future_year': 'No se pueden evaluar años futuros.',
        'overlapping_years': 'Estos años ya fueron evaluados en otra evaluación.',
    },
    'formulario': {
        'missing_year': 'Este tipo de formulario debe tener un año correspondiente.',
        'year_out_of_range': 'El año está fuera del rango de la Carrera Académica.',
        'missing_file': 'Un formulario entregado debe tener un archivo adjunto.',
    }
}
