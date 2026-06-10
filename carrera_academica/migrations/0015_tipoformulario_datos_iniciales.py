from django.db import migrations

TIPOS_FORMULARIO = [
    ("CV",  "Curriculum Vitae",           "Historial académico y profesional del docente. Lo presenta el docente al inicio de la carrera."),
    ("F01", "Aceptacion",                 "No se usa mas"),
    ("F02", "Planificacion",              "Ficha De Actividad Curricular."),
    ("F03", "Estructura De Cátedra",      "Estructura De Cátedra."),
    ("F04", "Plan Anual De Actividades Del Docente",
     "Plan Anual De Actividades Del Docente"),
    ("F05", "Informe Anual Del Docente",
     "Informe Anual Del Docente."),
    ("F06", "Informe Anual Y Concepto Del Departamento",
     "Informe Anual Y Concepto Del Departamento"),
    ("F07", "Informe Anual Y Concepto Del Secretario Academico",
     "Informe Anual Y Concepto Del Secretario Academico."),
    ("F08", "Nómina De La Junta Evaluadora",
     "Resolucion de la nomina de la junta evaluadora."),
    ("F09", "Notificacion Para El Docente Postulante",
     "Notificacion al docente evaluado."),
    ("F10", "Notificacion A Profesores De La Junta Evaluadora",
     "Notificacion a los jurados de la junta evaluadora."),
    ("F11", "Notificacion A Veedores",
     "Notificacion a los veedores."),
    ("F12", "Acta Dictamen",
     "Acta de cierre del proceso evaluativo, firmada por todos los miembros del jurado."),
    ("F13", "Informe De La Secretaria De Ciencia Y Tecnologia",
     "Informe De La Secretaria De Ciencia Y Tecnologia."),
    ("ENC", "Encuesta estudiantil",       "Resultado de la encuesta de opinión de los alumnos sobre el desempeño docente. La realizan los alumnos cada año."),
]


def cargar_datos(apps, schema_editor):
    TipoFormulario = apps.get_model("carrera_academica", "TipoFormulario")
    for codigo, nombre, descripcion in TIPOS_FORMULARIO:
        TipoFormulario.objects.get_or_create(
            codigo=codigo,
            defaults={"nombre": nombre, "descripcion": descripcion},
        )


def eliminar_datos(apps, schema_editor):
    TipoFormulario = apps.get_model("carrera_academica", "TipoFormulario")
    TipoFormulario.objects.filter(
        codigo__in=[t[0] for t in TIPOS_FORMULARIO]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("carrera_academica", "0014_tipoformulario"),
    ]

    operations = [
        migrations.RunPython(cargar_datos, eliminar_datos),
    ]
