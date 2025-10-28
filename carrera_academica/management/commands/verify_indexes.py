# carrera_academica/management/commands/verify_indexes.py
"""
Comando para verificar que los índices se crearon correctamente.
"""
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Verifica los índices creados en la base de datos"

    def handle(self, *args, **options):
        """Ejecuta la verificación."""
        self.stdout.write(
            self.style.WARNING("Verificando índices en la base de datos...\n")
        )

        with connection.cursor() as cursor:
            # Para SQLite
            if "sqlite" in connection.settings_dict["ENGINE"]:
                self.verify_sqlite_indexes(cursor)
            # Para PostgreSQL
            elif "postgresql" in connection.settings_dict["ENGINE"]:
                self.verify_postgresql_indexes(cursor)
            # Para MySQL
            elif "mysql" in connection.settings_dict["ENGINE"]:
                self.verify_mysql_indexes(cursor)
            else:
                self.stdout.write(
                    self.style.ERROR("Base de datos no soportada para este comando")
                )

        self.stdout.write(self.style.SUCCESS("\n✅ Verificación completada"))

    def verify_sqlite_indexes(self, cursor):
        """Verifica índices en SQLite."""
        self.stdout.write("=== Índices en SQLite ===\n")

        # Obtener todas las tablas
        cursor.execute(
            """
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name NOT LIKE 'sqlite_%'
            ORDER BY name
        """
        )

        tables = cursor.fetchall()
        total_indexes = 0

        for (table_name,) in tables:
            # Obtener índices de esta tabla
            cursor.execute(f"PRAGMA index_list('{table_name}')")
            indexes = cursor.fetchall()

            if indexes:
                self.stdout.write(f"\n📋 Tabla: {table_name}")
                for idx in indexes:
                    index_name = idx[1]
                    is_unique = idx[2]

                    # Obtener columnas del índice
                    cursor.execute(f"PRAGMA index_info('{index_name}')")
                    columns = cursor.fetchall()
                    column_names = [col[2] for col in columns]

                    unique_marker = "🔑" if is_unique else "📌"
                    self.stdout.write(
                        f'  {unique_marker} {index_name}: {", ".join(column_names)}'
                    )
                    total_indexes += 1

        self.stdout.write(f"\n📊 Total de índices: {total_indexes}")

    def verify_postgresql_indexes(self, cursor):
        """Verifica índices en PostgreSQL."""
        self.stdout.write("=== Índices en PostgreSQL ===\n")

        cursor.execute(
            """
            SELECT
                schemaname,
                tablename,
                indexname,
                indexdef
            FROM pg_indexes
            WHERE schemaname = 'public'
            ORDER BY tablename, indexname
        """
        )

        indexes = cursor.fetchall()
        current_table = None
        total_indexes = 0

        for schema, table, index_name, index_def in indexes:
            if table != current_table:
                current_table = table
                self.stdout.write(f"\n📋 Tabla: {table}")

            # Determinar si es único
            is_unique = "UNIQUE" in index_def.upper()
            unique_marker = "🔑" if is_unique else "📌"

            self.stdout.write(f"  {unique_marker} {index_name}")
            total_indexes += 1

        self.stdout.write(f"\n📊 Total de índices: {total_indexes}")

    def verify_mysql_indexes(self, cursor):
        """Verifica índices en MySQL."""
        self.stdout.write("=== Índices en MySQL ===\n")

        # Obtener nombre de la base de datos
        db_name = connection.settings_dict["NAME"]

        cursor.execute(
            f"""
            SELECT DISTINCT TABLE_NAME
            FROM INFORMATION_SCHEMA.STATISTICS
            WHERE TABLE_SCHEMA = '{db_name}'
            ORDER BY TABLE_NAME
        """
        )

        tables = cursor.fetchall()
        total_indexes = 0

        for (table_name,) in tables:
            cursor.execute(
                f"""
                SELECT 
                    INDEX_NAME,
                    GROUP_CONCAT(COLUMN_NAME ORDER BY SEQ_IN_INDEX),
                    NON_UNIQUE
                FROM INFORMATION_SCHEMA.STATISTICS
                WHERE TABLE_SCHEMA = '{db_name}' AND TABLE_NAME = '{table_name}'
                GROUP BY INDEX_NAME, NON_UNIQUE
                ORDER BY INDEX_NAME
            """
            )

            indexes = cursor.fetchall()

            if indexes:
                self.stdout.write(f"\n📋 Tabla: {table_name}")
                for index_name, columns, non_unique in indexes:
                    is_unique = non_unique == 0
                    unique_marker = "🔑" if is_unique else "📌"
                    self.stdout.write(f"  {unique_marker} {index_name}: {columns}")
                    total_indexes += 1

        self.stdout.write(f"\n📊 Total de índices: {total_indexes}")
