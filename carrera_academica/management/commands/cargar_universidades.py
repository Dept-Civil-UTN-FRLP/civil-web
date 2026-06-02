from django.core.management.base import BaseCommand
from carrera_academica.models import Universidad


class Command(BaseCommand):
    help = 'Carga universidades iniciales en la base de datos'

    def handle(self, *args, **options):
        universidades = [
            # UTN Regionales
            {'sigla': 'UTN-FRLP', 'nombre_completo': 'Universidad Tecnológica Nacional - Facultad Regional La Plata',
                'es_utn': True, 'regional': 'FRLP'},
            {'sigla': 'UTN-FRBA', 'nombre_completo': 'Universidad Tecnológica Nacional - Facultad Regional Buenos Aires',
                'es_utn': True, 'regional': 'FRBA'},
            {'sigla': 'UTN-FRC', 'nombre_completo': 'Universidad Tecnológica Nacional - Facultad Regional Córdoba',
                'es_utn': True, 'regional': 'FRC'},
            {'sigla': 'UTN-FRA', 'nombre_completo': 'Universidad Tecnológica Nacional - Facultad Regional Avellaneda',
                'es_utn': True, 'regional': 'FRA'},
            {'sigla': 'UTN-FRM', 'nombre_completo': 'Universidad Tecnológica Nacional - Facultad Regional Mendoza',
                'es_utn': True, 'regional': 'FRM'},
            {'sigla': 'UTN-FRRO', 'nombre_completo': 'Universidad Tecnológica Nacional - Facultad Regional Rosario',
                'es_utn': True, 'regional': 'FRRO'},
            {'sigla': 'UTN-FRSF', 'nombre_completo': 'Universidad Tecnológica Nacional - Facultad Regional Santa Fe',
                'es_utn': True, 'regional': 'FRSF'},

            # Universidades Nacionales principales
            {'sigla': 'UBA', 'nombre_completo': 'Universidad de Buenos Aires',
                'es_utn': False, 'regional': ''},
            {'sigla': 'UNLP', 'nombre_completo': 'Universidad Nacional de La Plata',
                'es_utn': False, 'regional': ''},
            {'sigla': 'UNC', 'nombre_completo': 'Universidad Nacional de Córdoba',
                'es_utn': False, 'regional': ''},
            {'sigla': 'UNR', 'nombre_completo': 'Universidad Nacional de Rosario',
                'es_utn': False, 'regional': ''},
            {'sigla': 'UNL', 'nombre_completo': 'Universidad Nacional del Litoral',
                'es_utn': False, 'regional': ''},
            {'sigla': 'UNCPBA', 'nombre_completo': 'Universidad Nacional del Centro de la Provincia de Buenos Aires',
                'es_utn': False, 'regional': ''},
            {'sigla': 'UNMDP', 'nombre_completo': 'Universidad Nacional de Mar del Plata',
                'es_utn': False, 'regional': ''},
            {'sigla': 'UNCuyo', 'nombre_completo': 'Universidad Nacional de Cuyo',
                'es_utn': False, 'regional': ''},
        ]

        creadas = 0
        for data in universidades:
            universidad, created = Universidad.objects.get_or_create(
                sigla=data['sigla'],
                defaults=data
            )
            if created:
                creadas += 1
                self.stdout.write(self.style.SUCCESS(
                    f'✓ Creada: {universidad}'))
            else:
                self.stdout.write(f'  Ya existe: {universidad}')

        self.stdout.write(self.style.SUCCESS(
            f'\n✓ Proceso completado: {creadas} universidades creadas'))
