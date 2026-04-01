# carrera_academica/services/ca_service.py
"""
Servicio para workflows de Carrera Académica: finalizar y archivar.
"""
import logging
from datetime import date, datetime

from django.db import transaction
from django.utils import timezone

from carrera_academica.models import CarreraAcademica

logger = logging.getLogger(__name__)


class CAService:

    @staticmethod
    def finalizar(ca: CarreraAcademica, resultado: str, observaciones: str = "",
                  nueva_fecha_vencimiento: date = None, usuario=None) -> tuple[bool, str]:
        """
        Finaliza una CA con el workflow correspondiente al resultado.

        Returns:
            (exito, mensaje)
        """
        if resultado == "aprobada_redesigna" and not nueva_fecha_vencimiento:
            return False, "Debe especificar la nueva fecha de vencimiento para la redesignación"

        try:
            with transaction.atomic():
                ca.estado = "FIN"
                ca.fecha_finalizacion = timezone.now()
                ca.resultado_cierre = resultado
                ca.observaciones_cierre = observaciones
                ca.save()

                cargo = ca.cargo

                if resultado == "aprobada_redesigna":
                    return CAService._workflow_redesignacion(ca, cargo, nueva_fecha_vencimiento, observaciones, usuario)

                elif resultado == "aprobada_rechaza":
                    cargo.caracter = "int"
                    cargo.save()
                    return True, "CA Aprobada pero rechaza redesignación. Cargo convertido a Interino."

                elif resultado == "renuncia":
                    exito, msg = cargo.finalizar_sin_continuidad(
                        razon="renuncia", observaciones=observaciones, usuario=usuario)
                    return exito, f"Docente {cargo.docente} renunció. Cargo dado de baja."

                elif resultado == "no_aprobada":
                    cargo.caracter = "int"
                    cargo.save()
                    return True, "CA No Aprobada. Cargo convertido a Interino."

                elif resultado == "jubilacion":
                    return CAService._workflow_jubilacion(cargo, observaciones, usuario)

                return False, f"Resultado desconocido: {resultado}"

        except Exception as e:
            logger.error(f"Error al finalizar CA {ca.pk}: {e}")
            return False, str(e)

    @staticmethod
    def _workflow_redesignacion(ca, cargo, nueva_fecha_vencimiento, observaciones, usuario):
        from planta_docente.models import Cargo as CargoModel

        nuevo_cargo = CargoModel.objects.create(
            docente=cargo.docente,
            asignatura=cargo.asignatura,
            categoria=cargo.categoria,
            dedicacion=cargo.dedicacion,
            caracter=cargo.caracter,
            cantidad_horas=cargo.cantidad_horas,
            cantidad_comisiones=cargo.cantidad_comisiones,
            fecha_inicio=timezone.now().date(),
            fecha_vencimiento=nueva_fecha_vencimiento,
            estado="activo",
            estado_continuidad="activo",
        )

        exito, msg = cargo.finalizar_con_continuidad(
            cargo_siguiente=nuevo_cargo,
            tipo_continuidad="mismo_cargo",
            observaciones=f"Redesignación por aprobación de CA. {observaciones}",
            usuario=usuario,
        )

        if not exito:
            raise Exception(f"Error al vincular continuidad de cargos: {msg}")

        nueva_ca = CarreraAcademica.objects.create(
            cargo=nuevo_cargo,
            fecha_inicio=nuevo_cargo.fecha_inicio,
            fecha_vencimiento_original=nueva_fecha_vencimiento,
            fecha_vencimiento_actual=nueva_fecha_vencimiento,
            estado="ACT",
            ca_anterior=ca,
        )

        return True, f"redesignacion:{nueva_ca.pk}"

    @staticmethod
    def _workflow_jubilacion(cargo, observaciones, usuario):
        exito, msg = cargo.finalizar_sin_continuidad(
            razon="jubilacion", observaciones=observaciones, usuario=usuario)

        docente = cargo.docente
        docente.jubilado = True
        docente.fecha_jubilacion = timezone.now().date()
        docente.save()

        return True, f"Docente {docente} jubilado. Cargo dado de baja."

    @staticmethod
    def archivar(ca: CarreraAcademica, motivo: str, observaciones: str = "") -> tuple[bool, str]:
        """
        Archiva una CA sin workflow formal de cierre.

        Returns:
            (exito, mensaje)
        """
        if ca.estado not in ["ACT", "VEN"]:
            return False, "Solo se pueden archivar CAs activas o vencidas"

        try:
            ca.estado = "ARCH"
            ca.motivo_archivo = motivo
            ca.observaciones_archivo = observaciones
            ca.fecha_archivo = timezone.now()
            ca.save()

            return (
                True,
                f"CA archivada: {ca.get_motivo_archivo_display()}. "
                f"El cargo se gestionará cuando la CA venza el {ca.fecha_vencimiento_actual.strftime('%d/%m/%Y')}.",
            )

        except Exception as e:
            logger.error(f"Error al archivar CA {ca.pk}: {e}")
            return False, str(e)

    @staticmethod
    def cerrar_archivada(ca: CarreraAcademica, resultado: str,
                         observaciones: str = "", usuario=None) -> tuple[bool, str]:
        """
        Cierra definitivamente una CA archivada.

        Returns:
            (exito, mensaje)
        """
        if ca.estado != "ARCH":
            return False, "Solo se pueden cerrar definitivamente CAs archivadas"

        try:
            with transaction.atomic():
                ca.estado = "FIN"
                ca.resultado_cierre = resultado
                ca.observaciones_cierre = observaciones
                ca.fecha_finalizacion = timezone.now()
                ca.save()

                cargo = ca.cargo

                if resultado == "renuncia":
                    cargo.finalizar_sin_continuidad(
                        razon="renuncia",
                        observaciones=f"Renuncia efectivizada. {observaciones}",
                        usuario=usuario,
                    )
                    return True, "Cargo dado de baja por renuncia"

                elif resultado == "jubilacion":
                    cargo.finalizar_sin_continuidad(
                        razon="jubilacion",
                        observaciones=f"Jubilación efectivizada. {observaciones}",
                        usuario=usuario,
                    )
                    docente = cargo.docente
                    docente.jubilado = True
                    docente.fecha_jubilacion = timezone.now().date()
                    docente.save()
                    return True, f"Docente {docente} jubilado y cargo dado de baja"

                elif resultado == "no_aprobada":
                    cargo.caracter = "int"
                    cargo.save()
                    return True, "Cargo convertido a Interino"

                return False, f"Resultado desconocido: {resultado}"

        except Exception as e:
            logger.error(f"Error al cerrar CA archivada {ca.pk}: {e}")
            return False, str(e)

    @staticmethod
    def aplicar_prorroga(ca: CarreraAcademica, nueva_fecha=None, dias=None) -> tuple[bool, str]:
        from datetime import timedelta
    
        if nueva_fecha:
            if nueva_fecha <= ca.fecha_vencimiento_actual:
                return False, f"La nueva fecha debe ser posterior al vencimiento actual ({ca.fecha_vencimiento_actual.strftime('%d/%m/%Y')})"
            dias_prorroga = (nueva_fecha - ca.fecha_vencimiento_actual).days
    
        elif dias and dias > 0:
            nueva_fecha = ca.fecha_vencimiento_actual + timedelta(days=dias)
            dias_prorroga = dias
    
        else:
            return False, "Debe especificar la nueva fecha de vencimiento O los días de prórroga"
    
        fecha_anterior = ca.fecha_vencimiento_actual
    
        # Calcular años nuevos ANTES de actualizar la fecha
        anios_nuevos, forms_creados, mensaje_anios = ca.agregar_anios_por_prorroga(
            nueva_fecha)
    
        # Actualizar y guardar después
        ca.fecha_vencimiento_actual = nueva_fecha
        ca.save()
    
        mensaje = f"Prórroga de {dias_prorroga} días aplicada: {fecha_anterior.strftime('%d/%m/%Y')} → {nueva_fecha.strftime('%d/%m/%Y')}"
        if anios_nuevos:
            mensaje += f". {mensaje_anios}"
    
        return True, mensaje
    