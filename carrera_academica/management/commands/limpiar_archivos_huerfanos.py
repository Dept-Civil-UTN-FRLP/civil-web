import os
from django.conf import settings
from django.core.management.base import BaseCommand
from carrera_academica.models import Formulario


class Command(BaseCommand):
    help = "Borra archivos físicos bajo media/private/ca/ que no están referenciados por ningún Formulario."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Solo muestra los archivos que se borrarían, sin eliminar nada.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        base_dir = os.path.join(settings.MEDIA_ROOT, "private", "ca")

        if not os.path.isdir(base_dir):
            self.stdout.write(self.style.WARNING(f"Directorio no encontrado: {base_dir}"))
            return

        # Conjunto de rutas conocidas por la BD (relativas a MEDIA_ROOT)
        archivos_en_bd = set(
            Formulario.objects.exclude(archivo="")
            .exclude(archivo=None)
            .values_list("archivo", flat=True)
        )

        huerfanos = []
        for dirpath, _, filenames in os.walk(base_dir):
            for filename in filenames:
                abs_path = os.path.join(dirpath, filename)
                # Ruta relativa a MEDIA_ROOT, con separadores normalizados
                rel_path = os.path.relpath(abs_path, settings.MEDIA_ROOT).replace("\\", "/")
                if rel_path not in archivos_en_bd:
                    huerfanos.append((rel_path, abs_path))

        if not huerfanos:
            self.stdout.write(self.style.SUCCESS("No se encontraron archivos huérfanos."))
            return

        self.stdout.write(f"{'[DRY RUN] ' if dry_run else ''}Archivos huérfanos encontrados: {len(huerfanos)}\n")
        for rel_path, abs_path in huerfanos:
            size_kb = os.path.getsize(abs_path) / 1024
            self.stdout.write(f"  {'(borraría)' if dry_run else '(borrando)'} {rel_path}  [{size_kb:.1f} KB]")
            if not dry_run:
                os.remove(abs_path)

        if dry_run:
            self.stdout.write(self.style.WARNING("\nDry run: no se borró nada. Ejecutá sin --dry-run para borrar."))
        else:
            self.stdout.write(self.style.SUCCESS(f"\n{len(huerfanos)} archivo(s) eliminado(s)."))

        # Limpiar directorios vacíos que hayan quedado
        if not dry_run:
            for dirpath, dirnames, filenames in os.walk(base_dir, topdown=False):
                if not os.listdir(dirpath) and dirpath != base_dir:
                    os.rmdir(dirpath)
                    self.stdout.write(f"  (directorio vacío eliminado) {os.path.relpath(dirpath, settings.MEDIA_ROOT)}")
