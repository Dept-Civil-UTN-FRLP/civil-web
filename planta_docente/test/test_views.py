# planta_docente/tests/test_views.py
"""
Tests para las views de planta docente.
"""
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from carrera_academica.models import CarreraAcademica
from planta_docente.models import Asignatura, Cargo, Docente


class DashboardPlantaViewTestCase(TestCase):
    """Tests para dashboard_planta_view."""

    def setUp(self):
        """Configurar datos de prueba."""
        # Crear usuario
        self.user = User.objects.create_user("testuser", "test@test.com", "password")
        self.client = Client()
        self.client.login(username="testuser", password="password")

        # Crear docente
        self.docente = Docente.objects.create(
            nombre="Juan",
            apellido="Pérez",
            documento=12345678,
            legajo=1001,
            fecha_nacimiento=date(1980, 1, 1),
        )

        # Crear asignatura
        self.asignatura = Asignatura.objects.create(
            nombre="Test",
            nivel="i",
            departamento="civil",
            especialidad="civil",
            hora_semanal=4,
            hora_total=96,
            dictado="a",
        )

        # Crear cargo
        self.cargo = Cargo.objects.create(
            docente=self.docente,
            asignatura=self.asignatura,
            caracter="reg",
            categoria="adj",
            dedicacion="ds",
            cantidad_horas=10,
            fecha_inicio=date(2020, 1, 1),
            fecha_vencimiento=timezone.now().date() + timedelta(days=90),
            estado="activo",
        )


    def test_dashboard_requiere_login(self):
        self.client.logout()
        url = reverse("carrera_academica:dashboard_ca")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response.url)
    
    def test_dashboard_carga_correctamente(self):
        """Test que dashboard carga sin errores."""
        response = self.client.get(reverse("planta_docente:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "planta_docente/dashboard.html")
        self.assertIn("cargos", response.context)
        self.assertIn("stats", response.context)

    def test_dashboard_muestra_cargos(self):
        """Test que dashboard muestra los cargos."""
        response = self.client.get(reverse("planta_docente:dashboard"))

        self.assertEqual(len(response.context["cargos"]), 1)
        cargo = response.context["cargos"][0]
        self.assertEqual(cargo.docente, self.docente)

    def test_dashboard_busqueda_por_nombre(self):
        """Test búsqueda por nombre de docente."""
        response = self.client.get(reverse("planta_docente:dashboard"), {"q": "Juan"})

        self.assertEqual(len(response.context["cargos"]), 1)

    def test_dashboard_busqueda_sin_resultados(self):
        """Test búsqueda sin resultados."""
        response = self.client.get(
            reverse("planta_docente:dashboard"), {"q": "NoExiste"}
        )

        self.assertEqual(len(response.context["cargos"]), 0)

    def test_dashboard_filtro_por_estado(self):
        """Test filtro por estado."""
        response = self.client.get(
            reverse("planta_docente:dashboard"), {"estado": "activo"}
        )

        self.assertEqual(len(response.context["cargos"]), 1)

    def test_dashboard_filtro_por_departamento(self):
        """Test filtro por departamento."""
        response = self.client.get(
            reverse("planta_docente:dashboard"), {"departamento": "civil"}
        )

        self.assertEqual(len(response.context["cargos"]), 1)

    def test_dashboard_estadisticas(self):
        """Test que se calculan estadísticas correctamente."""
        response = self.client.get(reverse("planta_docente:dashboard"))

        stats = response.context["stats"]
        self.assertEqual(stats["total_cargos"], 1)
        self.assertEqual(stats["cargos_activos"], 1)

    def test_dashboard_paginacion(self):
        """Test que la paginación funciona."""
        # Crear 30 cargos más
        for i in range(30):
            docente = Docente.objects.create(
                nombre=f"Docente{i}",
                apellido=f"Test{i}",
                documento=20000000 + i,
                legajo=2000 + i,
                fecha_nacimiento=date(1980, 1, 1),
            )
            Cargo.objects.create(
                docente=docente,
                asignatura=self.asignatura,
                caracter="reg",
                categoria="adj",
                dedicacion="ds",
                cantidad_horas=10,
                fecha_inicio=date(2020, 1, 1),
                fecha_vencimiento=timezone.now().date() + timedelta(days=90),
                estado="activo",
            )

        response = self.client.get(reverse("planta_docente:dashboard"))

        self.assertTrue(response.context["is_paginated"])
        self.assertEqual(len(response.context["cargos"]), 25)


class DetalleCargoViewTestCase(TestCase):
    """Tests para detalle_cargo_view."""

    def setUp(self):
        """Configurar datos de prueba."""
        self.user = User.objects.create_user("testuser", "test@test.com", "password")
        self.client = Client()
        self.client.login(username="testuser", password="password")

        self.docente = Docente.objects.create(
            nombre="Juan",
            apellido="Pérez",
            documento=12345678,
            legajo=1001,
            fecha_nacimiento=date(1980, 1, 1),
        )

        self.asignatura = Asignatura.objects.create(
            nombre="Test",
            nivel="i",
            departamento="civil",
            especialidad="civil",
            hora_semanal=4,
            hora_total=96,
            dictado="a",
        )

        self.cargo = Cargo.objects.create(
            docente=self.docente,
            asignatura=self.asignatura,
            caracter="reg",
            categoria="adj",
            dedicacion="ds",
            cantidad_horas=10,
            fecha_inicio=date(2020, 1, 1),
            fecha_vencimiento=timezone.now().date() + timedelta(days=90),
            estado="activo",
        )

    def test_detalle_cargo_requiere_login(self):
        """Test que detalle requiere autenticación."""
        self.client.logout()
        response = self.client.get(
            reverse("planta_docente:detalle_cargo", kwargs={"pk": self.cargo.pk})
        )

        self.assertEqual(response.status_code, 302)

    def test_detalle_cargo_carga_correctamente(self):
        """Test que detalle carga sin errores."""
        response = self.client.get(
            reverse("planta_docente:detalle_cargo", kwargs={"pk": self.cargo.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "planta_docente/cargo_detail.html")

    def test_detalle_cargo_muestra_informacion(self):
        """Test que detalle muestra información correcta."""
        response = self.client.get(
            reverse("planta_docente:detalle_cargo", kwargs={"pk": self.cargo.pk})
        )

        self.assertEqual(response.context["cargo"], self.cargo)
        self.assertIn("estado_venc", response.context)
        self.assertIn("estado_jub", response.context)
        self.assertIn("antiguedad_texto", response.context)

    def test_detalle_cargo_inexistente(self):
        """Test que devuelve 404 para cargo inexistente."""
        response = self.client.get(
            reverse("planta_docente:detalle_cargo", kwargs={"pk": 9999})
        )

        self.assertEqual(response.status_code, 404)

    def test_detalle_cargo_muestra_puede_iniciar_ca(self):
        """Test que muestra botón de iniciar CA cuando corresponde."""
        response = self.client.get(
            reverse("planta_docente:detalle_cargo", kwargs={"pk": self.cargo.pk})
        )

        self.assertTrue(response.context["puede_iniciar_ca"])


class DetalleDocenteViewTestCase(TestCase):
    """Tests para detalle_docente_view."""

    def setUp(self):
        """Configurar datos de prueba."""
        self.user = User.objects.create_user("testuser", "test@test.com", "password")
        self.client = Client()
        self.client.login(username="testuser", password="password")

        self.docente = Docente.objects.create(
            nombre="Juan",
            apellido="Pérez",
            documento=12345678,
            legajo=1001,
            fecha_nacimiento=date(1980, 1, 1),
        )

    def test_detalle_docente_carga_correctamente(self):
        """Test que detalle docente carga sin errores."""
        response = self.client.get(
            reverse("planta_docente:detalle_docente", kwargs={"pk": self.docente.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "planta_docente/docente_detail.html")

    def test_detalle_docente_muestra_edad(self):
        """Test que muestra la edad calculada."""
        response = self.client.get(
            reverse("planta_docente:detalle_docente", kwargs={"pk": self.docente.pk})
        )

        self.assertIn("edad", response.context)
        self.assertGreater(response.context["edad"], 0)


class VencimientosViewTestCase(TestCase):
    """Tests para vencimientos_view."""

    def setUp(self):
        """Configurar datos de prueba."""
        self.user = User.objects.create_user("testuser", "test@test.com", "password")
        self.client = Client()
        self.client.login(username="testuser", password="password")

        self.docente = Docente.objects.create(
            nombre="Juan",
            apellido="Pérez",
            documento=12345678,
            legajo=1001,
            fecha_nacimiento=date(1980, 1, 1),
        )

        self.asignatura = Asignatura.objects.create(
            nombre="Test",
            nivel="i",
            departamento="civil",
            especialidad="civil",
            hora_semanal=4,
            hora_total=96,
            dictado="a",
        )

        # Cargo próximo a vencer
        self.cargo_proximo = Cargo.objects.create(
            docente=self.docente,
            asignatura=self.asignatura,
            caracter="reg",
            categoria="adj",
            dedicacion="ds",
            cantidad_horas=10,
            fecha_inicio=date(2020, 1, 1),
            fecha_vencimiento=timezone.now().date() + timedelta(days=45),
            estado="activo",
        )

    def test_vencimientos_carga_correctamente(self):
        """Test que vista de vencimientos carga sin errores."""
        response = self.client.get(reverse("planta_docente:vencimientos"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "planta_docente/vencimientos.html")

    def test_vencimientos_muestra_cargo_proximo(self):
        """Test que muestra cargo próximo a vencer."""
        response = self.client.get(reverse("planta_docente:vencimientos"))

        criticos = response.context["criticos"]
        self.assertEqual(len(criticos), 1)
        self.assertEqual(criticos[0].pk, self.cargo_proximo.pk)


class JubilacionesViewTestCase(TestCase):
    """Tests para jubilaciones_view."""

    def setUp(self):
        """Configurar datos de prueba."""
        self.user = User.objects.create_user("testuser", "test@test.com", "password")
        self.client = Client()
        self.client.login(username="testuser", password="password")

        # Docente mayor de 65
        self.docente_mayor = Docente.objects.create(
            nombre="Jubilado",
            apellido="Test",
            documento=11111111,
            legajo=2001,
            fecha_nacimiento=date(1955, 1, 1),
        )

    def test_jubilaciones_carga_correctamente(self):
        """Test que vista de jubilaciones carga sin errores."""
        response = self.client.get(reverse("planta_docente:jubilaciones"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "planta_docente/jubilaciones.html")

    def test_jubilaciones_muestra_docente_mayor_65(self):
        """Test que muestra docente mayor de 65."""
        response = self.client.get(reverse("planta_docente:jubilaciones"))

        # Debe aparecer en entre_65_70 o mayores_70
        total_alertas = response.context["total_alertas"]
        self.assertGreater(total_alertas, 0)


class CargosSinCAViewTestCase(TestCase):
    """Tests para cargos_sin_ca_view."""

    def setUp(self):
        """Configurar datos de prueba."""
        self.user = User.objects.create_user("testuser", "test@test.com", "password")
        self.client = Client()
        self.client.login(username="testuser", password="password")

        self.docente = Docente.objects.create(
            nombre="Juan",
            apellido="Pérez",
            documento=12345678,
            legajo=1001,
            fecha_nacimiento=date(1980, 1, 1),
        )

        self.asignatura = Asignatura.objects.create(
            nombre="Test",
            nivel="i",
            departamento="civil",
            especialidad="civil",
            hora_semanal=4,
            hora_total=96,
            dictado="a",
        )

        # Cargo sin CA
        self.cargo_sin_ca = Cargo.objects.create(
            docente=self.docente,
            asignatura=self.asignatura,
            caracter="reg",
            categoria="adj",
            dedicacion="ds",
            cantidad_horas=10,
            fecha_inicio=date(2020, 1, 1),
            fecha_vencimiento=timezone.now().date() + timedelta(days=365),
            estado="activo",
        )

    def test_sin_ca_carga_correctamente(self):
        """Test que vista carga sin errores."""
        response = self.client.get(reverse("planta_docente:sin_ca"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "planta_docente/sin_ca.html")

    def test_sin_ca_muestra_cargo(self):
        """Test que muestra cargo sin CA."""
        response = self.client.get(reverse("planta_docente:sin_ca"))

        cargos = response.context["cargos"]
        self.assertEqual(len(cargos), 1)
        self.assertEqual(cargos[0].pk, self.cargo_sin_ca.pk)


class IniciarCADesdoCargoViewTestCase(TestCase):
    """Tests para iniciar_ca_desde_cargo_view."""

    def setUp(self):
        """Configurar datos de prueba."""
        self.user = User.objects.create_user("testuser", "test@test.com", "password")
        self.client = Client()
        self.client.login(username="testuser", password="password")

        self.docente = Docente.objects.create(
            nombre="Juan",
            apellido="Pérez",
            documento=12345678,
            legajo=1001,
            fecha_nacimiento=date(1980, 1, 1),
        )

        self.asignatura = Asignatura.objects.create(
            nombre="Test",
            nivel="i",
            departamento="civil",
            especialidad="civil",
            hora_semanal=4,
            hora_total=96,
            dictado="a",
        )

        self.cargo = Cargo.objects.create(
            docente=self.docente,
            asignatura=self.asignatura,
            caracter="reg",
            categoria="adj",
            dedicacion="ds",
            cantidad_horas=10,
            fecha_inicio=date(2020, 1, 1),
            fecha_vencimiento=date(2025, 1, 1),
            estado="activo",
        )

    def test_iniciar_ca_get_muestra_confirmacion(self):
        """Test que GET muestra página de confirmación."""
        response = self.client.get(
            reverse(
                "planta_docente:iniciar_ca_desde_cargo", kwargs={"pk": self.cargo.pk}
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "planta_docente/confirmar_iniciar_ca.html")

    def test_iniciar_ca_post_crea_ca(self):
        """Test que POST crea la CA correctamente."""
        response = self.client.post(
            reverse(
                "planta_docente:iniciar_ca_desde_cargo", kwargs={"pk": self.cargo.pk}
            )
        )

        # Debe redirigir al detalle de la CA
        self.assertEqual(response.status_code, 302)

        # Verificar que se creó la CA
        self.cargo.refresh_from_db()
        self.assertTrue(hasattr(self.cargo, "carrera_academica"))

    def test_iniciar_ca_cargo_interino_falla(self):
        """Test que no se puede iniciar CA para cargo interino."""
        cargo_int = Cargo.objects.create(
            docente=self.docente,
            asignatura=self.asignatura,
            caracter="int",
            categoria="adj",
            dedicacion="ds",
            cantidad_horas=10,
            fecha_inicio=date(2020, 1, 1),
            estado="activo",
        )

        response = self.client.post(
            reverse(
                "planta_docente:iniciar_ca_desde_cargo", kwargs={"pk": cargo_int.pk}
            )
        )

        # Debe redirigir con mensaje de error
        self.assertEqual(response.status_code, 302)
        self.assertFalse(hasattr(cargo_int, "carrera_academica"))


class CargoInfoAPIViewTestCase(TestCase):
    """Tests para cargo_info_api_view."""

    def setUp(self):
        """Configurar datos de prueba."""
        self.user = User.objects.create_user("testuser", "test@test.com", "password")
        self.client = Client()
        self.client.login(username="testuser", password="password")

        self.docente = Docente.objects.create(
            nombre="Juan",
            apellido="Pérez",
            documento=12345678,
            legajo=1001,
            fecha_nacimiento=date(1980, 1, 1),
        )

        self.asignatura = Asignatura.objects.create(
            nombre="Test",
            nivel="i",
            departamento="civil",
            especialidad="civil",
            hora_semanal=4,
            hora_total=96,
            dictado="a",
        )

        self.cargo = Cargo.objects.create(
            docente=self.docente,
            asignatura=self.asignatura,
            caracter="reg",
            categoria="adj",
            dedicacion="ds",
            cantidad_horas=10,
            fecha_inicio=date(2020, 1, 1),
            fecha_vencimiento=timezone.now().date() + timedelta(days=90),
            estado="activo",
        )

    def test_api_retorna_json(self):
        """Test que API retorna JSON válido."""
        response = self.client.get(
            reverse("planta_docente:cargo_info_api", kwargs={"pk": self.cargo.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")

    def test_api_contiene_datos_correctos(self):
        """Test que JSON contiene datos correctos."""
        response = self.client.get(
            reverse("planta_docente:cargo_info_api", kwargs={"pk": self.cargo.pk})
        )

        data = response.json()
        self.assertEqual(data["id"], self.cargo.pk)
        self.assertIn("docente", data)
        self.assertIn("antiguedad", data)

    def test_api_cargo_inexistente(self):
        """Test que API retorna 404 para cargo inexistente."""
        response = self.client.get(
            reverse("planta_docente:cargo_info_api", kwargs={"pk": 9999})
        )

        self.assertEqual(response.status_code, 404)
