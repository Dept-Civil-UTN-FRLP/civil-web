"""
Comando interactivo para agregar emails a docentes con cargos activos.
"""
from django.core.management.base import BaseCommand
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from planta_docente.models import Docente, Correo, Cargo


class Command(BaseCommand):
    help = 'Agrega emails a docentes de forma interactiva'

    def add_arguments(self, parser):
        parser.add_argument(
            '--solo-profesores',
            action='store_true',
            help='Solo procesar profesores (Titular, Asociado, Adjunto)',
        )

        parser.add_argument(
            '--listar',
            action='store_true',
            help='Solo listar docentes sin email, sin agregar',
        )

    def handle(self, *args, **options):
        solo_profesores = options['solo_profesores']
        solo_listar = options['listar']

        self.stdout.write("=" * 70)
        self.stdout.write(self.style.SUCCESS(
            "📧 GESTIÓN DE EMAILS DE DOCENTES"))
        self.stdout.write("=" * 70)

        # Filtrar docentes según opciones
        if solo_profesores:
            self.stdout.write(
                "\n🎓 Filtrando solo profesores (Titular, Asociado, Adjunto)\n")
            categorias = ['tit', 'aso', 'adj']
        else:
            self.stdout.write(
                "\n👥 Procesando todos los docentes con cargos activos\n")
            categorias = ['tit', 'aso', 'adj', 'jtp', 'atp1', 'atp2', 'ads']

        # Obtener IDs de docentes con cargos activos
        docentes_con_cargos = Cargo.objects.filter(
            estado='activo',
            categoria__in=categorias
        ).values_list('docente_id', flat=True).distinct()

        # Filtrar los que NO tienen email
        docentes_sin_email = Docente.objects.filter(
            id__in=docentes_con_cargos
        ).prefetch_related('correos', 'cargo_docente').order_by('apellido', 'nombre')

        docentes_procesados = []
        for docente in docentes_sin_email:
            if not docente.tiene_email:
                docentes_procesados.append(docente)

        if not docentes_procesados:
            self.stdout.write(self.style.SUCCESS(
                "\n✅ Todos los docentes ya tienen email configurado\n"))
            return

        self.stdout.write(
            f"📊 Total docentes sin email: {len(docentes_procesados)}\n")
        self.stdout.write("=" * 70 + "\n")

        # Si solo listar, mostrar y salir
        if solo_listar:
            self._listar_docentes(docentes_procesados)
            return

        # Modo interactivo
        self.stdout.write(self.style.WARNING("Modo interactivo:"))
        self.stdout.write("- Ingresa el email para cada docente")
        self.stdout.write("- Presiona ENTER sin escribir nada para omitir")
        self.stdout.write("- Escribe 'q' o 'quit' para salir\n")

        contador_agregados = 0
        contador_omitidos = 0

        for idx, docente in enumerate(docentes_procesados, 1):
            self.stdout.write("\n" + "-" * 70)
            self.stdout.write(
                f"\n[{idx}/{len(docentes_procesados)}] {self.style.SUCCESS(docente.get_full_name())}")

            # Mostrar información del docente
            self._mostrar_info_docente(docente)

            # Sugerir email
            email_sugerido = self._generar_email(docente)

            # Solicitar email
            while True:
                try:
                    email_input = input(
                        f"\n📧 Email [{email_sugerido}]: ").strip()

                    # Salir
                    if email_input.lower() in ['q', 'quit', 'exit', 'salir']:
                        self.stdout.write(self.style.WARNING(
                            "\n\n⚠️  Proceso interrumpido por el usuario"))
                        break

                    # Omitir
                    if not email_input:
                        self.stdout.write(self.style.WARNING("⏭️  Omitido"))
                        contador_omitidos += 1
                        break

                    # Usar sugerido si presiona solo enter después de ver la sugerencia
                    email_final = email_input if email_input else email_sugerido

                    # Validar email
                    validate_email(email_final)

                    # Crear correo
                    Correo.objects.create(
                        docente=docente,
                        email=email_final,
                        principal=True
                    )

                    self.stdout.write(self.style.SUCCESS(
                        f"✅ Email agregado: {email_final}"))
                    contador_agregados += 1
                    break

                except ValidationError:
                    self.stdout.write(self.style.ERROR(
                        "❌ Email inválido. Intenta de nuevo."))
                except KeyboardInterrupt:
                    self.stdout.write(self.style.WARNING(
                        "\n\n⚠️  Proceso interrumpido (Ctrl+C)"))
                    return
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"❌ Error: {str(e)}"))

            # Si el usuario salió, terminar
            if email_input and email_input.lower() in ['q', 'quit', 'exit', 'salir']:
                break

        # Resumen final
        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(self.style.SUCCESS(f"\n📊 RESUMEN:"))
        self.stdout.write(f"✅ Emails agregados: {contador_agregados}")
        self.stdout.write(f"⏭️  Omitidos: {contador_omitidos}")
        self.stdout.write(
            f"📧 Total procesados: {contador_agregados + contador_omitidos}")
        self.stdout.write("=" * 70 + "\n")

    def _listar_docentes(self, docentes):
        """Lista todos los docentes sin email."""
        for idx, docente in enumerate(docentes, 1):
            self.stdout.write(f"\n{idx}. {docente.get_full_name()}")
            self._mostrar_info_docente(docente)
            email_sugerido = self._generar_email(docente)
            self.stdout.write(f"   💡 Email sugerido: {email_sugerido}")

        self.stdout.write(f"\n{'=' * 70}")
        self.stdout.write(f"Total: {len(docentes)} docentes sin email")
        self.stdout.write(f"{'=' * 70}\n")

    def _mostrar_info_docente(self, docente):
        """Muestra información relevante del docente."""
        # DNI
        if docente.documento:
            self.stdout.write(f"   DNI: {docente.documento}")

        # Cargos
        cargos = Cargo.objects.filter(
            docente=docente,
            estado='activo'
        ).select_related('asignatura')

        if cargos.exists():
            self.stdout.write("   Cargos activos:")
            for cargo in cargos:
                self.stdout.write(
                    f"      • {cargo.get_categoria_display()} - {cargo.asignatura.nombre}"
                )

    def _generar_email(self, docente):
        """
        Genera un email sugerido en formato: apellido.nombre@frlp.utn.edu.ar
        """
        # Limpiar apellido
        apellido = docente.apellido.lower().strip() if docente.apellido else 'docente'
        apellido = apellido.replace(' ', '').replace('ñ', 'n').replace('á', 'a').replace(
            'é', 'e').replace('í', 'i').replace('ó', 'o').replace('ú', 'u')
        apellido = ''.join(c for c in apellido if c.isalnum())

        # Limpiar nombre (solo primer nombre)
        if docente.nombre:
            nombre = docente.nombre.lower().strip().split()[0]
            nombre = nombre.replace('ñ', 'n').replace('á', 'a').replace(
                'é', 'e').replace('í', 'i').replace('ó', 'o').replace('ú', 'u')
            nombre = ''.join(c for c in nombre if c.isalnum())
        else:
            nombre = 'docente'

        return f"{apellido}.{nombre}@frlp.utn.edu.ar"
