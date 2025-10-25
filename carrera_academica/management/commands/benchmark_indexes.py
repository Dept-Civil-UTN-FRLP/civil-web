# carrera_academica/management/commands/benchmark_indexes.py
"""
Comando para hacer benchmark antes/después de índices.
"""
import time
from django.core.management.base import BaseCommand
from django.db import connection, reset_queries
from django.test.utils import override_settings

from carrera_academica.models import CarreraAcademica, Formulario
from planta_docente.models import Cargo, Docente
from equivalencias.models import SolicitudEquivalencia


class Command(BaseCommand):
    help = 'Hace benchmark de queries para medir impacto de índices'

    @override_settings(DEBUG=True)
    def handle(self, *args, **options):
        """Ejecuta el benchmark."""
        self.stdout.write(self.style.WARNING(
            'Iniciando benchmark de índices...\n'))

        results = []

        # Test 1: Dashboard CA - Filtrar por estado
        results.append(self.benchmark_query(
            'Dashboard CA - Filtrar por estado',
            lambda: list(CarreraAcademica.objects.filter(estado='ACT')[:50])
        ))

        # Test 2: Dashboard CA - Filtrar y ordenar
        results.append(self.benchmark_query(
            'Dashboard CA - Filtrar y ordenar',
            lambda: list(
                CarreraAcademica.objects.filter(estado='ACT')
                .order_by('fecha_vencimiento_actual')[:50]
            )
        ))

        # Test 3: Buscar por expediente
        results.append(self.benchmark_query(
            'Buscar por expediente',
            lambda: list(CarreraAcademica.objects.filter(
                numero_expediente__icontains='2024'
            ))
        ))

        # Test 4: Formularios pendientes
        results.append(self.benchmark_query(
            'Formularios pendientes por CA',
            lambda: list(Formulario.objects.filter(
                carrera_academica_id=1,
                estado='PEN'
            ))
        ))

        # Test 5: Cargos activos regulares
        results.append(self.benchmark_query(
            'Cargos activos regulares',
            lambda: list(Cargo.objects.filter(
                estado='activo',
                caracter__in=['reg', 'ord']
            )[:50])
        ))

        # Test 6: Búsqueda de docentes
        results.append(self.benchmark_query(
            'Buscar docentes por apellido',
            lambda: list(Docente.objects.filter(
                apellido__icontains='a'
            )[:50])
        ))

        # Test 7: Solicitudes en proceso
        results.append(self.benchmark_query(
            'Solicitudes en proceso',
            lambda: list(
                SolicitudEquivalencia.objects.filter(
                    estado_general='En Proceso')
                .order_by('-fecha_inicio')[:50]
            )
        ))

        # Mostrar resultados
        self.print_results(results)

    def benchmark_query(self, name, query_func, iterations=5):
        """Ejecuta una query múltiples veces y mide el tiempo."""
        times = []
        query_counts = []

        for _ in range(iterations):
            reset_queries()

            start = time.time()
            query_func()
            end = time.time()

            times.append((end - start) * 1000)  # Convertir a ms
            query_counts.append(len(connection.queries))

        avg_time = sum(times) / len(times)
        avg_queries = sum(query_counts) / len(query_counts)

        return {
            'name': name,
            'avg_time': avg_time,
            'avg_queries': avg_queries,
            'min_time': min(times),
            'max_time': max(times)
        }

    def print_results(self, results):
        """Imprime los resultados en formato tabla."""
        self.stdout.write('\n' + '=' * 80)
        self.stdout.write('RESULTADOS DEL BENCHMARK')
        self.stdout.write('=' * 80 + '\n')

        # Encabezado
        self.stdout.write(
            f"{'Query':<40} {'Tiempo (ms)':<15} {'Queries':<10}"
        )
        self.stdout.write('-' * 80)

        # Resultados
        total_time = 0
        for result in results:
            self.stdout.write(
                f"{result['name']:<40} "
                f"{result['avg_time']:>10.2f}ms    "
                f"{result['avg_queries']:>5.1f}"
            )
            total_time += result['avg_time']

        # Total
        self.stdout.write('-' * 80)
        self.stdout.write(f"{'TOTAL':<40} {total_time:>10.2f}ms")
        self.stdout.write('=' * 80)

        # Recomendaciones
        self.stdout.write('\n📊 Análisis:')
        slow_queries = [r for r in results if r['avg_time'] > 100]

        if slow_queries:
            self.stdout.write(self.style.WARNING(
                f'\n⚠️  {len(slow_queries)} queries lentas (>100ms):'
            ))
            for q in slow_queries:
                self.stdout.write(f'   - {q["name"]}: {q["avg_time"]:.2f}ms')
        else:
            self.stdout.write(self.style.SUCCESS(
                '\n✅ Todas las queries son rápidas (<100ms)'
            ))

        self.stdout.write(f'\n💾 Promedio de queries por operación: '
                          f'{sum(r["avg_queries"] for r in results) / len(results):.1f}')
