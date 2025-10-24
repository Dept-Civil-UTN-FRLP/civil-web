# carrera_academica/management/commands/analyze_queries.py
"""
Comando para analizar queries lentas.
"""
from django.core.management.base import BaseCommand
from django.db import connection, reset_queries
from django.test.utils import override_settings

from carrera_academica.models import CarreraAcademica
from equivalencias.models import SolicitudEquivalencia


class Command(BaseCommand):
    help = 'Analiza las queries realizadas en views principales'

    @override_settings(DEBUG=True)
    def handle(self, *args, **options):
        """Ejecuta el análisis de queries."""
        self.stdout.write(self.style.WARNING(
            'Iniciando análisis de queries...\n'))

        # Test 1: Dashboard CA sin optimización
        self.stdout.write('=== Test 1: Dashboard CA (sin optimización) ===')
        reset_queries()
        list(CarreraAcademica.objects.all()[:10])
        self.print_query_stats()

        # Test 2: Dashboard CA con optimización
        self.stdout.write('\n=== Test 2: Dashboard CA (con optimización) ===')
        reset_queries()
        list(CarreraAcademica.objects.with_related_data()[:10])
        self.print_query_stats()

        # Test 3: Detalle CA sin optimización
        self.stdout.write('\n=== Test 3: Detalle CA (sin optimización) ===')
        reset_queries()
        ca = CarreraAcademica.objects.first()
        if ca:
            _ = ca.cargo.docente
            _ = ca.cargo.asignatura
            _ = list(ca.formularios.all())
            _ = list(ca.evaluaciones.all())
        self.print_query_stats()

        # Test 4: Detalle CA con optimización
        self.stdout.write('\n=== Test 4: Detalle CA (con optimización) ===')
        reset_queries()
        ca = CarreraAcademica.objects.with_full_detail().first()
        if ca:
            _ = ca.cargo.docente
            _ = ca.cargo.asignatura
            _ = list(ca.formularios.all())
            _ = list(ca.evaluaciones.all())
        self.print_query_stats()

        self.stdout.write(self.style.SUCCESS('\n✅ Análisis completado'))

    def print_query_stats(self):
        """Imprime estadísticas de queries."""
        queries = connection.queries
        total_time = sum(float(q['time']) for q in queries)

        self.stdout.write(f'Total queries: {len(queries)}')
        self.stdout.write(f'Tiempo total: {total_time:.4f}s')

        if queries:
            self.stdout.write(
                f'Promedio por query: {total_time/len(queries):.4f}s')

            # Mostrar las 3 queries más lentas
            sorted_queries = sorted(
                queries, key=lambda x: float(x['time']), reverse=True)
            self.stdout.write('\nTop 3 queries más lentas:')
            for i, q in enumerate(sorted_queries[:3], 1):
                self.stdout.write(
                    f"{i}. {float(q['time']):.4f}s - {q['sql'][:100]}..."
                )
