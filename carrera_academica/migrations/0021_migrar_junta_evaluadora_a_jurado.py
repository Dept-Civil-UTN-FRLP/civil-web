# Generated manually
"""
Migra los datos reales de JuntaEvaluadora (modelo viejo, 1 por CA) al modelo
Jurado (nuevo, reutilizable). Corre ANTES de que el modelo JuntaEvaluadora se
elimine del todo -- sin esto se perderían los registros existentes.

CAs cuya JuntaEvaluadora está vacía (sin miembro_interno_titular) se saltean,
no hay nada que migrar. CAs que ya tienen un Jurado asignado tampoco se tocan.
"""
from django.db import migrations


def migrar_junta_a_jurado(apps, schema_editor):
    JuntaEvaluadora = apps.get_model("carrera_academica", "JuntaEvaluadora")
    Jurado = apps.get_model("carrera_academica", "Jurado")
    JuradoExterno = apps.get_model("carrera_academica", "JuradoExterno")
    VeedorGraduado = apps.get_model("carrera_academica", "VeedorGraduado")
    VeedorEstudiante = apps.get_model("carrera_academica", "VeedorEstudiante")
    Universidad = apps.get_model("carrera_academica", "Universidad")

    def resolver_categoria(cargo_info):
        texto = (cargo_info or "").lower()
        if "asociado" in texto:
            return "asociado"
        if "adjunto" in texto:
            return "adjunto"
        return "titular"

    def resolver_universidad(nombre_origen):
        nombre_origen = (nombre_origen or "").strip()
        uni = Universidad.objects.filter(sigla__iexact=nombre_origen).first()
        if uni:
            return uni
        uni = Universidad.objects.filter(nombre_completo__iexact=nombre_origen).first()
        if uni:
            return uni
        # Fallback defensivo: crear la universidad con lo que haya, para no
        # perder el dato ni romper la migración por un nombre no catalogado.
        print(
            f"[migrar_junta_a_jurado] AVISO: universidad '{nombre_origen}' no "
            f"encontrada, se crea una entrada nueva -- revisar/completar a mano."
        )
        return Universidad.objects.create(
            sigla=(nombre_origen[:20] or "S/D"),
            nombre_completo=nombre_origen or "Sin especificar",
        )

    def partir_nombre(nombre_completo):
        nombre_completo = (nombre_completo or "").strip()
        if "," in nombre_completo:
            apellido, nombre = [p.strip() for p in nombre_completo.split(",", 1)]
            return apellido or "S/D", nombre or "S/D"
        return nombre_completo or "S/D", "S/D"

    def externo_a_jurado_externo(miembro_externo):
        if miembro_externo is None:
            return None
        existente = JuradoExterno.objects.filter(email=miembro_externo.email).first()
        if existente:
            return existente
        apellido, nombre = partir_nombre(miembro_externo.nombre_completo)
        return JuradoExterno.objects.create(
            apellido=apellido,
            nombre=nombre,
            email=miembro_externo.email,
            universidad=resolver_universidad(miembro_externo.universidad_origen),
            categoria=resolver_categoria(miembro_externo.cargo_info),
        )

    def veedor_a_nuevo(veedor, ca_pk):
        """
        Best-effort: el Veedor viejo no tiene legajo/titulo/año_egreso, campos
        que VeedorEstudiante/VeedorGraduado sí requieren. Se completan con
        'S/D' y se avisa por consola -- no se pierde el registro, pero queda
        marcado que hay que completarlo a mano en el admin.
        """
        if veedor is None:
            return None
        email = veedor.email or "sin-email@sin-datos.local"
        apellido, nombre = partir_nombre(veedor.nombre_completo)

        if veedor.claustro == "ALU":
            existente = VeedorEstudiante.objects.filter(email=email).first()
            if existente:
                return existente
            print(
                f"[migrar_junta_a_jurado] AVISO CA {ca_pk}: veedor estudiante "
                f"'{veedor.nombre_completo}' migrado sin legajo real (falta completar)."
            )
            return VeedorEstudiante.objects.create(
                apellido=apellido, nombre=nombre, email=email, legajo="S/D",
            )
        else:
            existente = VeedorGraduado.objects.filter(email=email).first()
            if existente:
                return existente
            print(
                f"[migrar_junta_a_jurado] AVISO CA {ca_pk}: veedor graduado "
                f"'{veedor.nombre_completo}' migrado sin título real (falta completar)."
            )
            return VeedorGraduado.objects.create(
                apellido=apellido, nombre=nombre, email=email, titulo="S/D",
            )

    migrados = 0
    for junta in JuntaEvaluadora.objects.select_related(
        "carrera_academica",
        "carrera_academica__cargo__asignatura",
        "miembro_interno_titular",
        "miembro_interno_suplente",
        "veedor_alumno_titular",
        "veedor_alumno_suplente",
        "veedor_graduado_titular",
        "veedor_graduado_suplente",
    ).prefetch_related(
        "miembros_externos_titulares", "miembros_externos_suplentes",
    ):
        ca = junta.carrera_academica

        if getattr(ca, "jurado_id", None):
            continue  # ya tiene Jurado nuevo asignado, no pisar
        if not junta.miembro_interno_titular:
            continue  # cascara vacia (creada sin cargar nada), nada que migrar

        externos_titulares = list(junta.miembros_externos_titulares.all())
        externos_suplentes = list(junta.miembros_externos_suplentes.all())

        # El modelo Jurado exige que profesor_titular_3 sea de una universidad
        # NO-UTN -- separar por es_utn en vez de confiar en el orden original.
        def separar_por_utn(lista):
            no_utn, utn = [], []
            for m in lista:
                (no_utn if not resolver_universidad(m.universidad_origen).es_utn else utn).append(m)
            return utn + no_utn  # UTN primero (va a titular_2), no-UTN despues (titular_3)

        ordenados_tit = separar_por_utn(externos_titulares)
        ordenados_sup = separar_por_utn(externos_suplentes)

        if len(externos_titulares) > 2:
            print(
                f"[migrar_junta_a_jurado] AVISO CA {ca.pk}: tenía "
                f"{len(externos_titulares)} externos titulares, Jurado solo "
                f"soporta 2 -- se migraron los primeros 2."
            )
        if len(externos_suplentes) > 2:
            print(
                f"[migrar_junta_a_jurado] AVISO CA {ca.pk}: tenía "
                f"{len(externos_suplentes)} externos suplentes, Jurado solo "
                f"soporta 2 -- se migraron los primeros 2."
            )

        prof_tit_2 = externo_a_jurado_externo(ordenados_tit[0]) if len(ordenados_tit) > 0 else None
        prof_tit_3 = externo_a_jurado_externo(ordenados_tit[1]) if len(ordenados_tit) > 1 else None
        prof_sup_2 = externo_a_jurado_externo(ordenados_sup[0]) if len(ordenados_sup) > 0 else None
        prof_sup_3 = externo_a_jurado_externo(ordenados_sup[1]) if len(ordenados_sup) > 1 else None

        if prof_tit_2 is None or prof_tit_3 is None:
            print(
                f"[migrar_junta_a_jurado] AVISO: CA {ca.pk} no tenía 2 externos "
                f"titulares cargados -- Jurado requiere profesor_titular_2 y "
                f"profesor_titular_3, no se migró automáticamente. Asignar a mano."
            )
            continue

        veedor_grad_tit = veedor_a_nuevo(junta.veedor_graduado_titular, ca.pk)
        veedor_grad_sup = veedor_a_nuevo(junta.veedor_graduado_suplente, ca.pk)
        veedor_est_tit = veedor_a_nuevo(junta.veedor_alumno_titular, ca.pk)
        veedor_est_sup = veedor_a_nuevo(junta.veedor_alumno_suplente, ca.pk)

        # Jurado.save() real auto-genera "nombre" con los apellidos de los 3
        # titulares -- el modelo histórico de esta migración no tiene ese
        # override, así que se arma acá con la misma lógica.
        apellidos = [junta.miembro_interno_titular.apellido]
        if prof_tit_2:
            apellidos.append(prof_tit_2.apellido)
        if prof_tit_3:
            apellidos.append(prof_tit_3.apellido)

        nuevo_jurado = Jurado.objects.create(
            nombre=" - ".join(apellidos) if apellidos else "Jurado sin nombre",
            departamento=ca.cargo.asignatura.departamento,
            profesor_titular_1=junta.miembro_interno_titular,
            profesor_suplente_1=junta.miembro_interno_suplente,
            profesor_titular_2=prof_tit_2,
            profesor_suplente_2=prof_sup_2,
            profesor_titular_3=prof_tit_3,
            profesor_suplente_3=prof_sup_3,
            veedor_graduado_titular=veedor_grad_tit,
            veedor_graduado_suplente=veedor_grad_sup,
            veedor_estudiante_titular=veedor_est_tit,
            veedor_estudiante_suplente=veedor_est_sup,
            notas=f"Migrado automáticamente desde JuntaEvaluadora (CA {ca.pk}).",
        )
        ca.jurado = nuevo_jurado
        ca.save(update_fields=["jurado"])
        migrados += 1
        print(
            f"[migrar_junta_a_jurado] CA {ca.pk}: JuntaEvaluadora migrada a "
            f"Jurado #{nuevo_jurado.pk} ('{nuevo_jurado.nombre}')."
        )

    print(f"[migrar_junta_a_jurado] Total CAs migradas: {migrados}")


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("carrera_academica", "0020_portal_jurado_vista_detalle_choice"),
    ]

    operations = [
        migrations.RunPython(migrar_junta_a_jurado, noop_reverse),
    ]
