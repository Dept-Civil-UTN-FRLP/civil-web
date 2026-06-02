# planta_docente/tests/test_utils.py
"""
Tests para las funciones utilitarias de planta docente.
"""
from datetime import date, timedelta

from django.test import TestCase
from django.utils import timezone

from planta_docente.models import Asignatura, Cargo, Docente
from planta_docente.utils import (
    calcular_antiguedad,
    calcular_edad,
    calcular_proximo_vencimiento,
    dias_hasta_fecha,
    formatear_antiguedad,
    formatear_antiguedad_completa,
    obtener_alertas_cargo,
    obtener_estado_jubilacion,
    obtener_estado_vencimiento,
    obtener_fecha_jubilacion,
)


class CalcularEdadTestCase(TestCase):
    """Tests para calcular_edad."""

    def test_edad_simple(self):
        """Test cálculo de edad básico."""
        # Si hoy es 2024-10-28 y nació 1980-05-15
        fecha_nac = date(1980, 5, 15)
        edad = calcular_edad(fecha_nac)

        hoy = timezone.now().date()
        edad_esperada = hoy.year - 1980
        if (hoy.month, hoy.day) < (5, 15):
            edad_esperada -= 1

        self.assertEqual(edad, edad_esperada)

    def test_edad_no_cumplio_anios(self):
        """Test cuando aún no cumplió años en el año actual."""
        hoy = timezone.now().date()
        # Nació el próximo mes
        fecha_nac = date(hoy.year - 30, hoy.month + 1 if hoy.month < 12 else 1, 15)

        edad = calcular_edad(fecha_nac)

        # Debe tener 29 años (aún no cumple 30)
        self.assertEqual(edad, 29)


class CalcularAntiguedadTestCase(TestCase):
    """Tests para calcular_antiguedad."""

    def test_antiguedad_completa(self):
        """Test cálculo de antigüedad con años, meses y días."""
        fecha_inicio = date(2020, 3, 15)
        fecha_fin = date(2024, 5, 20)

        resultado = calcular_antiguedad(fecha_inicio, fecha_fin)

        self.assertEqual(resultado["años"], 4)
        self.assertEqual(resultado["meses"], 2)
        self.assertEqual(resultado["dias"], 5)
        self.assertGreater(resultado["total_dias"], 1500)

    def test_antiguedad_sin_fecha_fin(self):
        """Test que usa fecha actual si no se especifica fin."""
        fecha_inicio = date(2020, 1, 1)

        resultado = calcular_antiguedad(fecha_inicio)

        self.assertIsNotNone(resultado["años"])
        self.assertGreaterEqual(resultado["años"], 4)

    def test_antiguedad_menos_de_un_mes(self):
        """Test antigüedad menor a un mes."""
        fecha_inicio = date(2024, 10, 1)
        fecha_fin = date(2024, 10, 15)

        resultado = calcular_antiguedad(fecha_inicio, fecha_fin)

        self.assertEqual(resultado["años"], 0)
        self.assertEqual(resultado["meses"], 0)
        self.assertEqual(resultado["dias"], 14)


class ObtenerFechaJubilacionTestCase(TestCase):
    """Tests para obtener_fecha_jubilacion."""

    def test_jubilacion_65(self):
        """Test fecha de jubilación a los 65."""
        fecha_nac = date(1960, 3, 15)

        fecha_jub = obtener_fecha_jubilacion(fecha_nac, 65)

        self.assertEqual(fecha_jub, date(2025, 3, 15))

    def test_jubilacion_70(self):
        """Test fecha de jubilación a los 70."""
        fecha_nac = date(1960, 3, 15)

        fecha_jub = obtener_fecha_jubilacion(fecha_nac, 70)

        self.assertEqual(fecha_jub, date(2030, 3, 15))


class ObtenerEstadoVencimientoTestCase(TestCase):
    """Tests para obtener_estado_vencimiento."""

    def setUp(self):
        """Configurar datos de prueba."""
        self.docente = Docente.objects.create(
            nombre="Test",
            apellido="Docente",
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

    def test_cargo_sin_vencimiento(self):
        """Test cargo sin fecha de vencimiento."""
        cargo = Cargo.objects.create(
            docente=self.docente,
            asignatura=self.asignatura,
            caracter="int",
            categoria="adj",
            dedicacion="ds",
            cantidad_horas=10,
            fecha_inicio=date(2020, 1, 1),
            fecha_vencimiento=None,
        )

        estado = obtener_estado_vencimiento(cargo)

        self.assertEqual(estado["tipo"], "sin_vencimiento")
        self.assertFalse(estado["urgente"])

    def test_cargo_vencido(self):
        """Test cargo con vencimiento pasado."""
        cargo = Cargo.objects.create(
            docente=self.docente,
            asignatura=self.asignatura,
            caracter="reg",
            categoria="adj",
            dedicacion="ds",
            cantidad_horas=10,
            fecha_inicio=date(2020, 1, 1),
            fecha_vencimiento=timezone.now().date() - timedelta(days=30),
        )

        estado = obtener_estado_vencimiento(cargo)

        self.assertEqual(estado["tipo"], "vencido")
        self.assertTrue(estado["urgente"])
        self.assertEqual(estado["dias"], 30)

    def test_cargo_critico(self):
        """Test cargo que vence en menos de 60 días."""
        cargo = Cargo.objects.create(
            docente=self.docente,
            asignatura=self.asignatura,
            caracter="reg",
            categoria="adj",
            dedicacion="ds",
            cantidad_horas=10,
            fecha_inicio=date(2020, 1, 1),
            fecha_vencimiento=timezone.now().date() + timedelta(days=45),
        )

        estado = obtener_estado_vencimiento(cargo)

        self.assertEqual(estado["tipo"], "critico")
        self.assertTrue(estado["urgente"])

    def test_cargo_proximo(self):
        """Test cargo que vence entre 60 y 180 días."""
        cargo = Cargo.objects.create(
            docente=self.docente,
            asignatura=self.asignatura,
            caracter="reg",
            categoria="adj",
            dedicacion="ds",
            cantidad_horas=10,
            fecha_inicio=date(2020, 1, 1),
            fecha_vencimiento=timezone.now().date() + timedelta(days=120),
        )

        estado = obtener_estado_vencimiento(cargo)

        self.assertEqual(estado["tipo"], "proximo")
        self.assertFalse(estado["urgente"])


class FormatearAntiguedadTestCase(TestCase):
    """Tests para formatear_antiguedad."""

    def test_formatear_años_y_meses(self):
        """Test formateo con años y meses."""
        ant = {"años": 4, "meses": 2, "dias": 5, "total_dias": 1527}

        resultado = formatear_antiguedad(ant)

        self.assertEqual(resultado, "4 años y 2 meses")

    def test_formatear_solo_meses(self):
        """Test formateo solo meses."""
        ant = {"años": 0, "meses": 3, "dias": 15, "total_dias": 105}

        resultado = formatear_antiguedad(ant)

        self.assertEqual(resultado, "3 meses")

    def test_formatear_solo_dias(self):
        """Test formateo solo días."""
        ant = {"años": 0, "meses": 0, "dias": 15, "total_dias": 15}

        resultado = formatear_antiguedad(ant)

        self.assertEqual(resultado, "15 días")

    def test_formatear_singular(self):
        """Test que usa singular correctamente."""
        ant = {"años": 1, "meses": 1, "dias": 1, "total_dias": 397}

        resultado = formatear_antiguedad(ant)

        self.assertIn("año", resultado)
        self.assertIn("mes", resultado)
        self.assertNotIn("años", resultado)
        self.assertNotIn("meses", resultado)

    def test_formatear_completa(self):
        """Test formateo completo con todos los componentes."""
        ant = {"años": 2, "meses": 3, "dias": 15, "total_dias": 835}

        resultado = formatear_antiguedad_completa(ant)

        self.assertEqual(resultado, "2 años, 3 meses y 15 días")


class ObtenerEstadoJubilacionTestCase(TestCase):
    """Tests para obtener_estado_jubilacion."""

    def test_docente_activo(self):
        """Test docente menor de 65 años."""
        docente = Docente.objects.create(
            nombre="Joven",
            apellido="Docente",
            documento=11111111,
            legajo=2001,
            fecha_nacimiento=date(1985, 3, 15),
        )

        estado = obtener_estado_jubilacion(docente)

        self.assertEqual(estado["estado"], "activo")
        self.assertFalse(estado["urgente"])
        self.assertIsNotNone(estado["dias_hasta_65"])

    def test_docente_proximo_65(self):
        """Test docente próximo a cumplir 65."""
        hoy = timezone.now().date()
        # Nació hace 64 años y 6 meses
        if hoy.month > 6:
            fecha_nac = date(hoy.year - 64, hoy.month - 6, hoy.day)
        else:
            fecha_nac = date(hoy.year - 65, hoy.month + 6, hoy.day)

        docente = Docente.objects.create(
            nombre="Proximo",
            apellido="Docente",
            documento=22222222,
            legajo=2002,
            fecha_nacimiento=fecha_nac,
        )

        estado = obtener_estado_jubilacion(docente)

        self.assertEqual(estado["estado"], "proximo_65")
        self.assertFalse(estado["urgente"])

    def test_docente_entre_65_y_70(self):
        """Test docente entre 65 y 70 años."""
        docente = Docente.objects.create(
            nombre="Jubilado",
            apellido="Parcial",
            documento=33333333,
            legajo=2003,
            fecha_nacimiento=date(1957, 1, 1),
        )

        estado = obtener_estado_jubilacion(docente)

        self.assertEqual(estado["estado"], "jubilado_65")
        self.assertTrue(estado["urgente"])

    def test_docente_mayor_70(self):
        """Test docente mayor de 70 años."""
        docente = Docente.objects.create(
            nombre="Jubilado",
            apellido="Total",
            documento=44444444,
            legajo=2004,
            fecha_nacimiento=date(1950, 1, 1),
        )

        estado = obtener_estado_jubilacion(docente)

        self.assertEqual(estado["estado"], "jubilado_70")
        self.assertTrue(estado["urgente"])


class ObtenerAlertasCargoTestCase(TestCase):
    """Tests para obtener_alertas_cargo."""

    def setUp(self):
        """Configurar datos de prueba."""
        self.asignatura = Asignatura.objects.create(
            nombre="Test",
            nivel="i",
            departamento="civil",
            especialidad="civil",
            hora_semanal=4,
            hora_total=96,
            dictado="a",
        )

    def test_cargo_sin_alertas(self):
        """Test cargo sin alertas urgentes."""
        docente = Docente.objects.create(
            nombre="Normal",
            apellido="Docente",
            documento=11111111,
            legajo=3001,
            fecha_nacimiento=date(1985, 1, 1),
        )

        cargo = Cargo.objects.create(
            docente=docente,
            asignatura=self.asignatura,
            caracter="reg",
            categoria="adj",
            dedicacion="ds",
            cantidad_horas=10,
            fecha_inicio=date(2020, 1, 1),
            fecha_vencimiento=timezone.now().date() + timedelta(days=365),
        )

        alertas = obtener_alertas_cargo(cargo)

        self.assertEqual(len(alertas), 0)

    def test_cargo_con_vencimiento_critico(self):
        """Test cargo con vencimiento crítico."""
        docente = Docente.objects.create(
            nombre="Urgente",
            apellido="Docente",
            documento=22222222,
            legajo=3002,
            fecha_nacimiento=date(1985, 1, 1),
        )

        cargo = Cargo.objects.create(
            docente=docente,
            asignatura=self.asignatura,
            caracter="reg",
            categoria="adj",
            dedicacion="ds",
            cantidad_horas=10,
            fecha_inicio=date(2020, 1, 1),
            fecha_vencimiento=timezone.now().date() + timedelta(days=30),
        )

        alertas = obtener_alertas_cargo(cargo)

        self.assertGreater(len(alertas), 0)
        self.assertEqual(alertas[0]["tipo"], "vencimiento")
        self.assertTrue(
            "30 días" in alertas[0]["mensaje"] or "29 días" in alertas[0]["mensaje"]
        )

    def test_cargo_docente_jubilado(self):
        """Test cargo con docente mayor de 70."""
        docente = Docente.objects.create(
            nombre="Jubilado",
            apellido="Docente",
            documento=33333333,
            legajo=3003,
            fecha_nacimiento=date(1950, 1, 1),
        )

        cargo = Cargo.objects.create(
            docente=docente,
            asignatura=self.asignatura,
            caracter="reg",
            categoria="adj",
            dedicacion="ds",
            cantidad_horas=10,
            fecha_inicio=date(2020, 1, 1),
            fecha_vencimiento=timezone.now().date() + timedelta(days=365),
        )

        alertas = obtener_alertas_cargo(cargo)

        self.assertGreater(len(alertas), 0)
        jubilacion_alert = [a for a in alertas if a["tipo"] == "jubilacion"]
        self.assertGreater(len(jubilacion_alert), 0)

    def test_alertas_ordenadas_por_prioridad(self):
        """Test que alertas se ordenan por prioridad."""
        docente = Docente.objects.create(
            nombre="Multiple",
            apellido="Alertas",
            documento=44444444,
            legajo=3004,
            fecha_nacimiento=date(1952, 1, 1),  # ~72 años
        )

        cargo = Cargo.objects.create(
            docente=docente,
            asignatura=self.asignatura,
            caracter="reg",
            categoria="adj",
            dedicacion="ds",
            cantidad_horas=10,
            fecha_inicio=date(2020, 1, 1),
            fecha_vencimiento=timezone.now().date() + timedelta(days=30),
        )

        alertas = obtener_alertas_cargo(cargo)

        # Debe haber al menos 2 alertas
        self.assertGreaterEqual(len(alertas), 2)

        # Las prioridades deben estar ordenadas ascendentemente
        for i in range(len(alertas) - 1):
            self.assertLessEqual(alertas[i]["prioridad"], alertas[i + 1]["prioridad"])


class CalcularProximoVencimientoTestCase(TestCase):
    """Tests para calcular_proximo_vencimiento."""

    def setUp(self):
        """Configurar datos de prueba."""
        self.docente = Docente.objects.create(
            nombre="Test",
            apellido="Docente",
            documento=12345678,
            legajo=4001,
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

    def test_sin_cargos(self):
        """Test con QuerySet vacío."""
        from planta_docente.models import Cargo

        fecha, cantidad = calcular_proximo_vencimiento(Cargo.objects.none())

        self.assertIsNone(fecha)
        self.assertEqual(cantidad, 0)

    def test_con_un_cargo(self):
        """Test con un solo cargo."""
        fecha_venc = timezone.now().date() + timedelta(days=90)

        from planta_docente.models import Cargo

        Cargo.objects.create(
            docente=self.docente,
            asignatura=self.asignatura,
            caracter="reg",
            categoria="adj",
            dedicacion="ds",
            cantidad_horas=10,
            fecha_inicio=date(2020, 1, 1),
            fecha_vencimiento=fecha_venc,
        )

        fecha, cantidad = calcular_proximo_vencimiento(Cargo.objects.all())

        self.assertEqual(fecha, fecha_venc)
        self.assertEqual(cantidad, 1)

    def test_con_multiples_cargos_misma_fecha(self):
        """Test con múltiples cargos que vencen el mismo día."""
        fecha_venc = timezone.now().date() + timedelta(days=90)

        from planta_docente.models import Cargo

        # Crear 3 docentes diferentes
        for i in range(3):
            docente = Docente.objects.create(
                nombre=f"Docente{i}",
                apellido=f"Test{i}",
                documento=10000000 + i,
                legajo=5000 + i,
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
                fecha_vencimiento=fecha_venc,
            )

        fecha, cantidad = calcular_proximo_vencimiento(Cargo.objects.all())

        self.assertEqual(fecha, fecha_venc)
        self.assertEqual(cantidad, 3)


class DiasHastaFechaTestCase(TestCase):
    """Tests para dias_hasta_fecha."""

    def test_fecha_futura(self):
        """Test con fecha futura."""
        fecha_futura = timezone.now().date() + timedelta(days=30)

        dias = dias_hasta_fecha(fecha_futura)

        self.assertEqual(dias, 30)

    def test_fecha_pasada(self):
        """Test con fecha pasada."""
        fecha_pasada = timezone.now().date() - timedelta(days=30)

        dias = dias_hasta_fecha(fecha_pasada)

        self.assertEqual(dias, -30)

    def test_fecha_none(self):
        """Test con fecha None."""
        dias = dias_hasta_fecha(None)

        self.assertIsNone(dias)

    def test_fecha_hoy(self):
        """Test con fecha de hoy."""
        dias = dias_hasta_fecha(timezone.now().date())

        self.assertEqual(dias, 0)
