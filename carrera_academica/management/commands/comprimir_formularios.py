"""
Management command para comprimir PDFs de formularios con Ghostscript.

Uso:
    python manage.py comprimir_formularios
    python manage.py comprimir_formularios --dry-run
    python manage.py comprimir_formularios --calidad printer
    python manage.py comprimir_formularios --force   # recomprimir ya procesados

Cron sugerido (3am diario):
    0 3 * * * /ruta/venv/bin/python /ruta/manage.py comprimir_formularios >> /var/log/comprimir_pdfs.log 2>&1
"""

import os
import shutil
import subprocess
import tempfile

from django.conf import settings
from django.core.management.base import BaseCommand

from carrera_academica.models import Formulario


CALIDADES = {
    "screen":  "/screen",    # 72 dpi  — mínima calidad, máxima compresión
    "ebook":   "/ebook",     # 150 dpi — buena para escaneados (recomendado)
    "printer": "/printer",   # 300 dpi — alta calidad
}


def _gs_disponible():
    return shutil.which("gs") is not None


def _comprimir_pdf(ruta_entrada: str, calidad: str) -> tuple[bool, int, int, str]:
    """
    Comprime un PDF con Ghostscript.
    Devuelve (exito, bytes_antes, bytes_despues, mensaje).
    Si el resultado es mayor que el original, devuelve el original sin reemplazar.
    """
    tamaño_original = os.path.getsize(ruta_entrada)

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        ruta_tmp = tmp.name

    try:
        resultado = subprocess.run(
            [
                "gs",
                "-dBATCH", "-dNOPAUSE", "-dQUIET",
                "-sDEVICE=pdfwrite",
                "-dCompatibilityLevel=1.4",
                f"-dPDFSETTINGS={CALIDADES[calidad]}",
                f"-sOutputFile={ruta_tmp}",
                ruta_entrada,
            ],
            capture_output=True,
            timeout=120,
        )

        if resultado.returncode != 0:
            return False, tamaño_original, 0, resultado.stderr.decode(errors="replace")

        tamaño_nuevo = os.path.getsize(ruta_tmp)

        if tamaño_nuevo >= tamaño_original:
            return True, tamaño_original, tamaño_original, "sin ganancia"

        shutil.move(ruta_tmp, ruta_entrada)
        return True, tamaño_original, tamaño_nuevo, "ok"

    except subprocess.TimeoutExpired:
        return False, tamaño_original, 0, "timeout"
    except Exception as e:
        return False, tamaño_original, 0, str(e)
    finally:
        if os.path.exists(ruta_tmp):
            os.unlink(ruta_tmp)


class Command(BaseCommand):
    help = "Comprime PDFs de formularios sin comprimir usando Ghostscript."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Muestra qué archivos se comprimirían sin hacer cambios.",
        )
        parser.add_argument(
            "--calidad",
            choices=CALIDADES.keys(),
            default="ebook",
            help="Nivel de compresión (default: ebook = 150 dpi).",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Recomprimir archivos que ya fueron procesados.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        calidad = options["calidad"]
        force = options["force"]

        if not _gs_disponible():
            self.stderr.write(self.style.ERROR(
                "Ghostscript no está instalado. Ejecutá: apt install ghostscript"
            ))
            return

        qs = Formulario.objects.filter(
            estado="ENT",
            archivo__isnull=False,
        ).exclude(archivo="")

        if not force:
            qs = qs.filter(comprimido=False)

        total = qs.count()
        if total == 0:
            self.stdout.write("No hay formularios pendientes de comprimir.")
            return

        self.stdout.write(f"Formularios a procesar: {total} (calidad: {calidad}{'  [dry-run]' if dry_run else ''})")

        procesados = 0
        errores = 0
        bytes_ahorrados = 0

        for formulario in qs.iterator():
            ruta = os.path.join(settings.MEDIA_ROOT, formulario.archivo.name)

            if not os.path.exists(ruta):
                self.stderr.write(f"  Archivo no encontrado: {ruta}")
                errores += 1
                continue

            nombre = formulario.archivo.name
            extension = os.path.splitext(nombre)[1].lower()

            if extension != ".pdf":
                if not force:
                    formulario.comprimido = True
                    formulario.save(update_fields=["comprimido"])
                continue

            if dry_run:
                tamaño = os.path.getsize(ruta)
                self.stdout.write(f"  [dry-run] {nombre}  ({tamaño / 1024:.0f} KB)")
                continue

            exito, antes, despues, msg = _comprimir_pdf(ruta, calidad)

            if exito:
                formulario.comprimido = True
                formulario.save(update_fields=["comprimido"])
                ahorro = antes - despues
                bytes_ahorrados += ahorro
                procesados += 1
                if msg == "sin ganancia":
                    self.stdout.write(f"  {nombre}  ({antes / 1024:.0f} KB) — sin ganancia, se conserva original")
                else:
                    pct = (ahorro / antes * 100) if antes else 0
                    self.stdout.write(
                        f"  {nombre}  {antes / 1024:.0f} KB → {despues / 1024:.0f} KB  (-{pct:.0f}%)"
                    )
            else:
                errores += 1
                self.stderr.write(f"  ERROR {nombre}: {msg}")

        if not dry_run:
            self.stdout.write(self.style.SUCCESS(
                f"\nListo. Procesados: {procesados} | Errores: {errores} | "
                f"Espacio ahorrado: {bytes_ahorrados / 1024 / 1024:.1f} MB"
            ))
