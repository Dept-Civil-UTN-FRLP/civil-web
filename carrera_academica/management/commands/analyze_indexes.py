# carrera_academica/management/commands/analyze_indexes.py
"""
Comando para analizar qué índices necesitamos.
"""
from django.core.management.base import BaseCommand
from django.db import connection
from django.test.utils import override_settings

from carrera_academica.models import CarreraAcademica, Evaluacion, Formulario
from planta_docente.models import Cargo, Docente, Asignatura
from equivalencias.models import SolicitudEquivalencia, DetalleSolicitud


class Command(BaseCommand):
    help = 'Analiza queries para sugerir índices'

    @override_settings(DEBUG=True)
    def handle(self, *args, **options):
        """Ejecuta el análisis."""
        self.stdout.write(self.style.WARNING(
            'Analizando queries para índices...\n'))

        # Test queries comunes y ver EXPLAIN
        self.analyze_ca_queries()
        self.analyze_cargo_queries()
        self.analyze_equivalencias_queries()

        self.stdout.write(self.style.SUCCESS('\n✅ Análisis completado'))

    def analyze_ca_queries(self):
        """Analiza queries de Carrera Académica."""
        self.stdout.write('\n=== Carrera Académica ===')

        # Query 1: Filtrar por estado
        self.stdout.write('\n1. Filtrar por estado:')
        qs = CarreraAcademica.objects.filter(estado='ACT')
        self.print_explain(qs)

        # Query 2: Ordenar por fecha_vencimiento_actual
        self.stdout.write('\n2. Ordenar por fecha_vencimiento_actual:')
        qs = CarreraAcademica.objects.order_by('fecha_vencimiento_actual')
        self.print_explain(qs)

        # Query 3: Buscar por número de expediente
        self.stdout.write('\n3. Buscar por número de expediente:')
        qs = CarreraAcademica.objects.filter(numero_expediente='12345/2024')
        self.print_explain(qs)

    def analyze_cargo_queries(self):
        """Analiza queries de Cargo."""
        self.stdout.write('\n\n=== Cargo ===')

        # Query 1: Filtrar por estado
        self.stdout.write('\n1. Filtrar por estado:')
        qs = Cargo.objects.filter(estado='activo')
        self.print_explain(qs)

        # Query 2: Filtrar por carácter
        self.stdout.write('\n2. Filtrar por carácter:')
        qs = Cargo.objects.filter(caracter__in=['reg', 'ord'])
        self.print_explain(qs)

        # Query 3: Búsqueda por docente
        self.stdout.write('\n3. Búsqueda por docente:')
        qs = Cargo.objects.filter(docente__apellido__icontains='perez')
        self.print_explain(qs)

    def analyze_equivalencias_queries(self):
        """Analiza queries de Equivalencias."""
        self.stdout.write('\n\n=== Solicitud Equivalencia ===')

        # Query 1: Filtrar por estado
        self.stdout.write('\n1. Filtrar por estado:')
        qs = SolicitudEquivalencia.objects.filter(estado_general='En Proceso')
        self.print_explain(qs)

        # Query 2: Ordenar por fecha
        self.stdout.write('\n2. Ordenar por fecha:')
        qs = SolicitudEquivalencia.objects.order_by('-fecha_inicio')
        self.print_explain(qs)

    def print_explain(self, queryset):
        """Imprime el EXPLAIN de una query."""
        try:
            # Solo mostrar primera línea del explain
            explain = str(queryset.explain()).split('\n')[0]
            self.stdout.write(f'   {explain[:100]}...')

            # Sugerir índice si hace SCAN
            if 'SCAN' in explain.upper():
                self.stdout.write(self.style.WARNING(
                    '   ⚠️  Necesita índice (hace SCAN)'))
            else:
                self.stdout.write(self.style.SUCCESS('   ✓ Usa índice'))
        except Exception as e:
            self.stdout.write(f'   Error: {e}')
