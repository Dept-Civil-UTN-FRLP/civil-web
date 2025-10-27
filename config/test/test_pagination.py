# config/tests/test_pagination.py
"""
Tests para el sistema de paginación.
"""
from django.test import TestCase, RequestFactory
from django.contrib.auth.models import User

from config.pagination import CustomPaginator, paginate_queryset
from carrera_academica.models import CarreraAcademica
from planta_docente.models import Cargo, Docente, Asignatura
from datetime import date


class PaginationTestCase(TestCase):
    """Tests para paginación."""

    @classmethod
    def setUpTestData(cls):
        """Crear datos de prueba."""
        # Crear usuario para requests
        cls.user = User.objects.create_user(
            'testuser', 'test@test.com', 'password')

        # Crear 60 docentes
        for i in range(60):
            Docente.objects.create(
                nombre=f"docente{i}",
                apellido=f"apellido{i}",
                documento=10000000 + i,
                legajo=1000 + i,
                fecha_nacimiento=date(1980, 1, 1)
            )

        # Crear asignatura
        asignatura = Asignatura.objects.create(
            nombre="test",
            nivel="i",
            departamento="civil",
            especialidad="civil",
            hora_semanal=4,
            hora_total=96,
            dictado="a"
        )

        # Crear 60 cargos y CAs
        for docente in Docente.objects.all():
            cargo = Cargo.objects.create(
                docente=docente,
                asignatura=asignatura,
                caracter="reg",
                categoria="adj",
                dedicacion="ds",
                fecha_inicio=date(2020, 1, 1),
                fecha_vencimiento=date(2025, 1, 1)
            )

            CarreraAcademica.objects.create(
                cargo=cargo,
                fecha_inicio=date(2020, 1, 1),
                fecha_vencimiento_original=date(2025, 1, 1)
            )

    def setUp(self):
        """Setup para cada test."""
        self.factory = RequestFactory()

    def test_pagination_default_page_size(self):
        """Test que el tamaño de página por defecto es 25."""
        request = self.factory.get('/test/')
        queryset = CarreraAcademica.objects.all()

        paginator = CustomPaginator(queryset, request)

        self.assertEqual(paginator.page_size, 25)
        self.assertEqual(len(paginator.page_obj), 25)

    def test_pagination_custom_page_size(self):
        """Test que se puede cambiar el tamaño de página."""
        request = self.factory.get('/test/?page_size=10')
        queryset = CarreraAcademica.objects.all()

        paginator = CustomPaginator(queryset, request)

        self.assertEqual(paginator.page_size, 10)
        self.assertEqual(len(paginator.page_obj), 10)

    def test_pagination_max_page_size(self):
        """Test que no se puede exceder el máximo de página."""
        request = self.factory.get('/test/?page_size=200')
        queryset = CarreraAcademica.objects.all()

        paginator = CustomPaginator(queryset, request)

        self.assertEqual(paginator.page_size, 100)  # MAX_PAGE_SIZE