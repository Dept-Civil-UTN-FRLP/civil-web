# equivalencias/management/commands/populate_db.py

import random
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from faker import Faker
from equivalencias.models import (
    Asignatura,
    Estudiante,
    SolicitudEquivalencia,
    DetalleSolicitud,
    DocumentoAdjunto,
)

# Lista de asignaturas realistas para Ing. Civil
ASIGNATURAS_CIVIL = [
    "Análisis Matemático I",
    "Álgebra y Geometría Analítica",
    "Física I",
    "Química General",
    "Estabilidad I",
    "Tecnología de los Materiales",
    "Topografía",
    "Hidráulica General",
    "Hormigón Armado I",
    "Estructuras Metálicas",
    "Mecánica de Suelos",
    "Vías de Comunicación I",
    "Ingeniería Sanitaria",
    "Organización de Obras",
    "Proyecto Final",
]


class Command(BaseCommand):
    help = "Puebla la base de datos con datos de prueba realistas"

    def handle(self, *args, **options):
        self.stdout.write("Limpiando la base de datos...")
        # El orden es importante para evitar errores de clave foránea
        DetalleSolicitud.objects.all().delete()
        DocumentoAdjunto.objects.all().delete()
        SolicitudEquivalencia.objects.all().delete()
        Estudiante.objects.all().delete()
        Asignatura.objects.all().delete()

        faker = Faker("es_AR")  # Usamos la localización para Argentina

        # --- 1. Crear Asignaturas ---
        self.stdout.write("Creando asignaturas...")
        asignaturas_creadas = []
        for nombre_asig in ASIGNATURAS_CIVIL:
            asignatura = Asignatura.objects.create(
                nombre_asignatura=nombre_asig,
                nombre_responsable=faker.name(),
                email_responsable=faker.email(),
            )
            asignaturas_creadas.append(asignatura)

        # --- 2. Crear Estudiantes ---
        self.stdout.write("Creando estudiantes...")
        estudiantes_creados = []
        for _ in range(50):  # Crearemos 50 estudiantes
            estudiante = Estudiante.objects.create(
                nombre_completo=faker.name(),
                email_estudiante=faker.email(),
                dni_pasaporte=faker.unique.ssn().replace("-", "")[:11],
            )
            estudiantes_creados.append(estudiante)

        # --- 3. Crear Solicitudes y simular el proceso ---
        self.stdout.write("Creando solicitudes y simulando el proceso...")
        estados_posibles = ["Aprobada", "Denegada", "Requiere PC", "Enviada a Cátedra"]

        for _ in range(150):  # Crearemos 150 solicitudes
            estudiante_aleatorio = random.choice(estudiantes_creados)
            fecha_inicio = timezone.now() - timedelta(days=random.randint(10, 730))

            solicitud = SolicitudEquivalencia.objects.create(
                id_estudiante=estudiante_aleatorio,
                fecha_inicio=fecha_inicio,
                estado_general="En Proceso",
            )

            # Cada solicitud tendrá entre 2 y 6 asignaturas
            num_asignaturas = random.randint(2, 6)
            asignaturas_solicitadas = random.sample(
                asignaturas_creadas, num_asignaturas
            )

            todas_respondidas = True
            ultima_fecha_dictamen = fecha_inicio

            for asig in asignaturas_solicitadas:
                estado_asignatura = random.choices(
                    estados_posibles, weights=[45, 20, 15, 20], k=1
                )[0]
                fecha_dictamen = None

                if estado_asignatura != "Enviada a Cátedra":
                    # Simulamos que el dictamen tarda entre 7 y 60 días
                    dias_demora = timedelta(days=random.randint(7, 60))
                    fecha_dictamen = fecha_inicio + dias_demora
                    if fecha_dictamen > ultima_fecha_dictamen:
                        ultima_fecha_dictamen = fecha_dictamen
                else:
                    todas_respondidas = False

                DetalleSolicitud.objects.create(
                    id_solicitud=solicitud,
                    id_asignatura=asig,
                    estado_asignatura=estado_asignatura,
                    detalle_pc=(
                        faker.paragraph(nb_sentences=2)
                        if estado_asignatura == "Requiere PC"
                        else None
                    ),
                    fecha_dictamen=fecha_dictamen,
                )

            # Simulamos si la solicitud general se completó
            if (
                todas_respondidas and random.random() < 0.8
            ):  # 80% de chance de completarse si todo está respondido
                solicitud.estado_general = "Completada"
                solicitud.fecha_completada = ultima_fecha_dictamen + timedelta(
                    days=random.randint(2, 10)
                )
                solicitud.save()

        self.stdout.write(self.style.SUCCESS("¡Base de datos poblada exitosamente!"))
