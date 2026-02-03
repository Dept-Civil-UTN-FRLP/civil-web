import csv
from django.core.management.base import BaseCommand
from planta_docente.models import Docente


class Command(BaseCommand):
    help = "Exporta el listado de docentes con su correo principal (si existe)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--csv",
            action="store_true",
            help="Exporta el resultado a un archivo CSV"
        )

    def handle(self, *args, **options):
        docentes = Docente.objects.prefetch_related("correos").order_by(
            "apellido", "nombre"
        )

        if options["csv"]:
            filename = "docentes_con_correos.csv"
            with open(filename, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Apellido", "Nombre", "Legajo", "Email"])

                for d in docentes:
                    correo = d.correos.filter(principal=True).first()
                    writer.writerow([
                        d.apellido,
                        d.nombre,
                        d.legajo,
                        correo.email if correo else ""
                    ])

            self.stdout.write(
                self.style.SUCCESS(f"Archivo generado: {filename}")
            )
        else:
            for d in docentes:
                correo = d.correos.filter(principal=True).first()
                self.stdout.write(
                    f"{d.apellido}, {d.nombre} - {correo.email if correo else ''}"
                )
