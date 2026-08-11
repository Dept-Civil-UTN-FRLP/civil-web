# carrera_academica/test/test_jurado_portal_service.py
"""
Tests para la resolución DNI -> Jurado -> CarreraAcademica del Portal de
Jurados. No toca JuntaEvaluadora (modelo viejo) — solo Jurado.
"""
from datetime import date

from django.test import TestCase

from carrera_academica.models import (
    CarreraAcademica,
    Evaluacion,
    Jurado,
    JuradoExterno,
    Universidad,
    VeedorEstudiante,
    VeedorGraduado,
)
from carrera_academica.models import Formulario
from carrera_academica.services.jurado_portal_service import (
    obtener_checklist_documentos,
    buscar_jurados_por_persona,
    obtener_cas_para_persona,
    obtener_dni,
    obtener_evaluacion_relevante,
)
from planta_docente.models import Asignatura, Cargo, Docente


def _crear_ca(nombre_docente, documento, nombre_asignatura):
    docente = Docente.objects.create(
        nombre=nombre_docente,
        apellido="Test",
        documento=documento,
        legajo=documento,
        fecha_nacimiento=date(1980, 1, 1),
    )
    asignatura = Asignatura.objects.create(
        nombre=nombre_asignatura,
        nivel="i",
        departamento="civil",
        especialidad="civil",
        hora_semanal=4,
        hora_total=96,
        dictado="a",
    )
    cargo = Cargo.objects.create(
        docente=docente,
        asignatura=asignatura,
        caracter="reg",
        categoria="adj",
        dedicacion="ds",
        cantidad_horas=10,
        fecha_inicio=date(2020, 1, 1),
        fecha_vencimiento=date(2025, 1, 1),
        estado="activo",
        estado_continuidad="activo",
    )
    ca = CarreraAcademica.objects.create(
        cargo=cargo,
        fecha_inicio=date(2020, 1, 1),
        fecha_vencimiento_original=date(2025, 1, 1),
        fecha_vencimiento_actual=date(2025, 1, 1),
        estado="ACT",
    )
    return docente, ca


class JuradoPortalServiceTestCase(TestCase):
    def setUp(self):
        self.docente_titular_1, self.ca1 = _crear_ca("Ana", 10000001, "Analisis I")
        _docente_titular_1_ca2, self.ca2 = _crear_ca("Beto", 10000002, "Analisis II")

        self.universidad = Universidad.objects.create(
            sigla="UNLP", nombre_completo="Universidad Nacional de La Plata",
            es_utn=False,
        )

        # Compartido entre Jurado 1 y Jurado 2 — clave para el test de "misma
        # persona en varios Jurado".
        self.ext_compartido = JuradoExterno.objects.create(
            apellido="Externo", nombre="Compartido", email="compartido@test.com",
            universidad=self.universidad, categoria="titular", dni=20000001,
        )
        self.ext_solo_j1 = JuradoExterno.objects.create(
            apellido="Externo", nombre="SoloJ1", email="soloj1@test.com",
            universidad=self.universidad, categoria="titular", dni=20000002,
        )
        self.ext_solo_j2 = JuradoExterno.objects.create(
            apellido="Externo", nombre="SoloJ2", email="soloj2@test.com",
            universidad=self.universidad, categoria="titular", dni=20000003,
        )
        self.veedor_grad = VeedorGraduado.objects.create(
            apellido="Veedor", nombre="Grad", email="vgrad@test.com",
            titulo="Ingeniero Civil", dni=30000001,
        )
        self.veedor_est = VeedorEstudiante.objects.create(
            apellido="Veedor", nombre="Est", email="vest@test.com",
            legajo="1234", dni=30000002,
        )

        self.jurado1 = Jurado.objects.create(
            departamento="civil",
            profesor_titular_1=self.docente_titular_1,
            profesor_titular_2=self.ext_compartido,
            profesor_titular_3=self.ext_solo_j1,
            veedor_graduado_suplente=self.veedor_grad,
            veedor_estudiante_suplente=self.veedor_est,
        )
        self.jurado2 = Jurado.objects.create(
            departamento="civil",
            profesor_titular_1=self.docente_titular_1,
            profesor_titular_2=self.ext_compartido,
            profesor_titular_3=self.ext_solo_j2,
        )
        self.ca1.jurado = self.jurado1
        self.ca1.save()
        self.ca2.jurado = self.jurado2
        self.ca2.save()

    def test_docente_resuelve_a_ambos_jurados_y_cas(self):
        jurados = buscar_jurados_por_persona("docente", self.docente_titular_1.pk)
        self.assertEqual(set(jurados), {self.jurado1, self.jurado2})

        cas = obtener_cas_para_persona("docente", self.docente_titular_1.pk)
        self.assertEqual(set(cas), {self.ca1, self.ca2})

    def test_persona_compartida_entre_dos_jurados_sin_duplicados(self):
        cas = list(obtener_cas_para_persona("jurado_externo", self.ext_compartido.pk))
        self.assertEqual(len(cas), 2)
        self.assertEqual(set(cas), {self.ca1, self.ca2})

    def test_jurado_externo_solo_en_uno(self):
        cas = obtener_cas_para_persona("jurado_externo", self.ext_solo_j1.pk)
        self.assertEqual(set(cas), {self.ca1})

    def test_veedor_graduado_resuelve_su_ca(self):
        cas = obtener_cas_para_persona("veedor_graduado", self.veedor_grad.pk)
        self.assertEqual(set(cas), {self.ca1})

    def test_veedor_estudiante_resuelve_su_ca(self):
        cas = obtener_cas_para_persona("veedor_estudiante", self.veedor_est.pk)
        self.assertEqual(set(cas), {self.ca1})

    def test_persona_inexistente_no_rompe(self):
        cas = obtener_cas_para_persona("docente", 999999)
        self.assertEqual(list(cas), [])

    def test_obtener_dni_abstrae_el_campo(self):
        self.assertEqual(obtener_dni(self.docente_titular_1), self.docente_titular_1.documento)
        self.assertEqual(obtener_dni(self.ext_compartido), 20000001)
        self.assertEqual(obtener_dni(self.veedor_grad), 30000001)
        self.assertEqual(obtener_dni(self.veedor_est), 30000002)

    def test_evaluacion_relevante_prioriza_programada(self):
        Evaluacion.objects.create(
            carrera_academica=self.ca1, numero_evaluacion=1, estado="CAN"
        )
        Evaluacion.objects.create(
            carrera_academica=self.ca1, numero_evaluacion=2, estado="REA"
        )
        programada = Evaluacion.objects.create(
            carrera_academica=self.ca1, numero_evaluacion=3, estado="PRO"
        )
        self.assertEqual(obtener_evaluacion_relevante(self.ca1), programada)

    def test_evaluacion_relevante_sin_programada_usa_la_mas_reciente(self):
        Evaluacion.objects.create(
            carrera_academica=self.ca2, numero_evaluacion=1, estado="CAN"
        )
        ultima = Evaluacion.objects.create(
            carrera_academica=self.ca2, numero_evaluacion=2, estado="REA",
            fecha_evaluacion="2024-01-01T10:00:00Z",
        )
        self.assertEqual(obtener_evaluacion_relevante(self.ca2), ultima)

    def test_evaluacion_relevante_sin_evaluaciones_es_none(self):
        self.assertIsNone(obtener_evaluacion_relevante(self.ca1))


class ChecklistDocumentosTestCase(TestCase):
    """
    ca1 se crea vía CarreraAcademica.objects.create(...), lo que dispara la señal
    crear_formularios_iniciales -- ya tiene el checklist completo (CV/F01/F02/F03
    generales + F04/F05/F06/F07/ENC por cada año 2020-2025), todos "PEN" sin archivo.
    """

    def setUp(self):
        self.docente, self.ca = _crear_ca("Ana", 10000001, "Analisis I")

    def test_generales_aparecen_sin_evaluacion(self):
        checklist = obtener_checklist_documentos(self.ca, evaluacion=None)
        tipos = {d.tipo_formulario for d in checklist}
        self.assertEqual(tipos, {"CV", "F01", "F02", "F03"})

    def test_anuales_de_evaluacion_aparecen_los_de_esos_anios_nomas(self):
        evaluacion = Evaluacion.objects.create(
            carrera_academica=self.ca, numero_evaluacion=1,
            anios_evaluados=[2020, 2021], estado="PRO",
        )
        checklist = obtener_checklist_documentos(self.ca, evaluacion)

        anuales = [d for d in checklist if d.anio_correspondiente]
        anios_presentes = {d.anio_correspondiente for d in anuales}
        self.assertEqual(anios_presentes, {2020, 2021})
        tipos_anuales = {d.tipo_formulario for d in anuales}
        self.assertEqual(tipos_anuales, {"F04", "F05", "F06", "F07", "ENC"})

    def test_ligados_a_la_evaluacion_aparecen(self):
        evaluacion = Evaluacion.objects.create(
            carrera_academica=self.ca, numero_evaluacion=1,
            anios_evaluados=[2020], estado="PRO",
        )
        for tipo in ["F08", "F09", "F10", "F11", "F12"]:
            Formulario.objects.create(
                carrera_academica=self.ca, tipo_formulario=tipo, evaluacion=evaluacion,
            )

        checklist = obtener_checklist_documentos(self.ca, evaluacion)
        tipos = {d.tipo_formulario for d in checklist}
        self.assertTrue({"F08", "F09", "F10", "F11", "F12"}.issubset(tipos))

    def test_pendientes_no_tienen_archivo(self):
        checklist = obtener_checklist_documentos(self.ca, evaluacion=None)
        self.assertTrue(all(not d.archivo for d in checklist))
