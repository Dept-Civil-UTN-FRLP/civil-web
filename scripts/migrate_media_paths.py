import os
import shutil
import django
import sys

sys.path.insert(0, '.')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from planta_docente.models import Asignatura, Resolucion, PlanificacionAnual
from equivalencias.models import SolicitudEquivalencia, DocumentoAdjunto, ConfiguracionDepartamento
from carrera_academica.models import Formulario, MembreteAnual, PlantillaDocumento
from django.conf import settings


MEDIA_ROOT = settings.MEDIA_ROOT

MIGRATIONS = [
    (Formulario, 'archivo', 'ca/', 'private/ca/'),
    (MembreteAnual, 'logo', 'membretes/', 'private/membretes/'),
    (PlantillaDocumento, 'archivo', 'plantillas_documentos/',
     'private/plantillas_documentos/'),
    (SolicitudEquivalencia, 'acta_firmada',
     'equivalencias/', 'private/equivalencias/'),
    (DocumentoAdjunto, 'archivo', 'equivalencias/', 'private/equivalencias/'),
    (ConfiguracionDepartamento, 'firma_imagen', 'firmas/', 'private/firmas/'),
    (Asignatura, 'programa', 'programas/', 'public/programas/'),
    (Resolucion, 'file', 'resoluciones/', 'private/resoluciones/'),
    (PlanificacionAnual, 'archivo', 'planificaciones/', 'private/planificaciones/'),
]

for model, field_name, old_prefix, new_prefix in MIGRATIONS:
    qs = model.objects.exclude(
        **{f'{field_name}': ''}).exclude(**{f'{field_name}': None})
    for obj in qs:
        field = getattr(obj, field_name)
        if not field or not field.name:
            continue
        if field.name.startswith(new_prefix):
            continue  # ya migrado
        new_name = field.name.replace(old_prefix, new_prefix, 1)
        old_path = os.path.join(MEDIA_ROOT, field.name)
        new_path = os.path.join(MEDIA_ROOT, new_name)
        if os.path.exists(old_path):
            os.makedirs(os.path.dirname(new_path), exist_ok=True)
            shutil.move(old_path, new_path)
            print(f'Movido: {field.name} → {new_name}')
        else:
            print(f'Archivo no encontrado: {old_path}')
        setattr(obj, field_name, new_name)
        obj.save(update_fields=[field_name])

print('Migración completada.')
