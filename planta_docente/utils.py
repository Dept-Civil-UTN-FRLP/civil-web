# planta_docente/utils.py
"""
Funciones auxiliares para cálculos relacionados con planta docente.

Este módulo contiene funciones puras para:
- Cálculos de edad y antigüedad
- Determinación de fechas de jubilación
- Análisis de estado de vencimientos
- Formateo de datos para presentación
"""
from datetime import date, timedelta
from typing import Dict, Optional, Tuple

from django.db.models import Q
from django.utils import timezone


def calcular_edad(fecha_nacimiento: date) -> int:
    """
    Calcula la edad actual de una persona en años completos.

    Args:
        fecha_nacimiento (date): Fecha de nacimiento del docente

    Returns:
        int: Edad en años completos

    Example:
        >>> calcular_edad(date(1980, 5, 15))
        44  # Si hoy es 2024

    Note:
        Toma en cuenta si ya cumplió años en el año actual.
    """
    hoy = timezone.now().date()
    edad = hoy.year - fecha_nacimiento.year

    # Ajustar si aún no cumplió años este año
    if (hoy.month, hoy.day) < (fecha_nacimiento.month, fecha_nacimiento.day):
        edad -= 1

    return edad


def calcular_antiguedad(
    fecha_inicio: date, fecha_fin: Optional[date] = None
) -> Dict[str, int]:
    """
    Calcula la antigüedad en un cargo con detalle de años, meses y días.

    Args:
        fecha_inicio (date): Fecha de inicio del cargo
        fecha_fin (date, optional): Fecha de fin del cargo.
                                    Si es None, usa la fecha actual

    Returns:
        dict: Diccionario con las siguientes claves:
            - años (int): Años completos de antigüedad
            - meses (int): Meses adicionales
            - dias (int): Días adicionales
            - total_dias (int): Total de días de antigüedad

    Example:
        >>> calcular_antiguedad(date(2020, 3, 15), date(2024, 5, 20))
        {'años': 4, 'meses': 2, 'dias': 5, 'total_dias': 1527}

    Note:
        El cálculo es exacto tomando en cuenta la variación de días
        en cada mes.
    """
    if fecha_fin is None:
        fecha_fin = timezone.now().date()

    # Calcular diferencia base
    años = fecha_fin.year - fecha_inicio.year
    meses = fecha_fin.month - fecha_inicio.month
    dias = fecha_fin.day - fecha_inicio.day

    # Ajustar si los días son negativos
    if dias < 0:
        meses -= 1
        # Calcular días del mes anterior
        if fecha_fin.month == 1:
            mes_anterior = 12
            año_anterior = fecha_fin.year - 1
        else:
            mes_anterior = fecha_fin.month - 1
            año_anterior = fecha_fin.year

        # Obtener el último día del mes anterior
        if mes_anterior == 12:
            ultimo_dia = 31
        else:
            primer_dia_mes_sig = date(año_anterior, mes_anterior + 1, 1)
            ultimo_dia = (primer_dia_mes_sig - timedelta(days=1)).day

        dias += ultimo_dia

    # Ajustar si los meses son negativos
    if meses < 0:
        años -= 1
        meses += 12

    # Calcular total de días
    total_dias = (fecha_fin - fecha_inicio).days

    return {"años": años, "meses": meses, "dias": dias, "total_dias": total_dias}


def solicitar_renovacion(self, usuario):
    """
    Solicita la renovación del cargo, extendiendo la fecha de vencimiento
    al próximo 31 de marzo.
    Args:
        usuario: Usuario que solicita la renovación
    Returns:
        tuple: (éxito, mensaje)
    """
    from django.utils import timezone

    # Validar que es interino o ad-honorem
    if self.tipo_cargo not in ["interino", "ad-honorem"]:
        return False, "Solo se pueden renovar cargos interinos o ad-honorem"
    # Validar que está activo
    if self.estado != "activo":
        return False, "Solo se pueden renovar cargos activos"
    # Guardar fecha anterior (para poder revertir)
    self.fecha_vencimiento_anterior = self.fecha_vencimiento
    # Calcular próximo 31 de marzo
    hoy = timezone.now().date()
    año_actual = hoy.year
    # Si ya pasó el 31/03 de este año, va al próximo
    fecha_31_marzo = timezone.datetime(año_actual, 3, 31).date()
    if hoy > fecha_31_marzo:
        # Ya pasó el 31/03 de este año, va al próximo
        self.fecha_vencimiento = timezone.datetime(año_actual + 1, 3, 31).date()
    else:
        # Todavía no pasó el 31/03 de este año, va a ese
        self.fecha_vencimiento = fecha_31_marzo
    # Marcar como renovado
    self.renovacion_solicitada = True
    self.fecha_renovacion = hoy
    self.usuario_renovacion = usuario
    self.save()
    return (
        True,
        f"Renovación solicitada. Nueva fecha de vencimiento: {self.fecha_vencimiento.strftime('%d/%m/%Y')}",
    )


def cancelar_renovacion(self):
    """
    Cancela la renovación, restaurando la fecha de vencimiento anterior.

    Returns:
        tuple: (éxito, mensaje)
    """
    if not self.renovacion_solicitada:
        return False, "Este cargo no tiene una renovación solicitada"

    # Restaurar fecha anterior
    if self.fecha_vencimiento_anterior:
        self.fecha_vencimiento = self.fecha_vencimiento_anterior

    # Limpiar campos de renovación
    self.renovacion_solicitada = False
    self.fecha_renovacion = None
    self.fecha_vencimiento_anterior = None
    self.usuario_renovacion = None

    self.save()

    return True, "Renovación cancelada exitosamente"


def get_jerarquia_display(self):
    """
    Retorna la jerarquía formateada como 'Profesor Adjunto'.

    Returns:
        str: Jerarquía formateada
    """
    categoria_map = {
        "titular": "Profesor Titular",
        "asociado": "Profesor Asociado",
        "adjunto": "Profesor Adjunto",
        "jtp": "Jefe de Trabajos Prácticos",
        "ayudante_1": "Ayudante de Primera",
        "ayudante_2": "Ayudante de Segunda",
    }
    return categoria_map.get(self.categoria, self.get_categoria_display())


def obtener_fecha_jubilacion(fecha_nacimiento: date, edad_jubilacion: int = 65) -> date:
    """
    Calcula la fecha exacta en que el docente cumple la edad de jubilación.

    Args:
        fecha_nacimiento (date): Fecha de nacimiento del docente
        edad_jubilacion (int): Edad de jubilación a considerar.
                               Default: 65 años

    Returns:
        date: Fecha en que cumple la edad de jubilación

    Example:
        >>> obtener_fecha_jubilacion(date(1960, 3, 15), 65)
        date(2025, 3, 15)

        >>> obtener_fecha_jubilacion(date(1960, 3, 15), 70)
        date(2030, 3, 15)

    Note:
        Contempla las edades estándar de jubilación:
        - 65 años: Jubilación ordinaria
        - 70 años: Jubilación con prórroga
    """
    return date(
        fecha_nacimiento.year + edad_jubilacion,
        fecha_nacimiento.month,
        fecha_nacimiento.day,
    )


def dias_hasta_fecha(fecha_objetivo: date) -> Optional[int]:
    """
    Calcula los días restantes hasta una fecha objetivo.

    Args:
        fecha_objetivo (date): Fecha objetivo

    Returns:
        int: Días hasta la fecha (negativo si ya pasó)
        None: Si fecha_objetivo es None

    Example:
        >>> dias_hasta_fecha(date(2024, 12, 31))  # Si hoy es 2024-10-28
        64

        >>> dias_hasta_fecha(date(2024, 1, 1))  # Si hoy es 2024-10-28
        -301
    """
    if not fecha_objetivo:
        return None

    return (fecha_objetivo - timezone.now().date()).days


def obtener_estado_vencimiento(cargo):
    """
    Determina el estado de vencimiento de un cargo.
    
    Considera:
    - Licencia por mayor jerarquía (vencimiento suspendido)
    - Días restantes hasta vencimiento
    - Umbrales de alerta (60 días crítico, 180 días próximo)
    
    Returns:
        dict: Información del estado de vencimiento
    """
    hoy = timezone.now().date()

    # ✅ NUEVO: Verificar licencia MJ PRIMERO
    if cargo.en_licencia_mayor_jerarquia:
        dias_licencia = (
            hoy - cargo.fecha_inicio_licencia_mj).days if cargo.fecha_inicio_licencia_mj else 0

        return {
            "tipo": "pausado",
            "mensaje": f"Vencimiento suspendido (Licencia M.J. desde {cargo.fecha_inicio_licencia_mj.strftime('%d/%m/%Y') if cargo.fecha_inicio_licencia_mj else 'N/A'})",
            "badge_class": "bg-warning text-dark",
            "icono": "bi-pause-circle",
            "dias_licencia": dias_licencia,
            "fecha_vencimiento_original": cargo.fecha_vencimiento_original_pre_licencia,
            "urgente": False,
        }

    # Si no tiene fecha de vencimiento, no aplica
    if not cargo.fecha_vencimiento:
        return {
            "tipo": "sin_vencimiento",
            "mensaje": "Sin fecha de vencimiento",
            "badge_class": "bg-secondary",
            "icono": "bi-infinity",
            "urgente": False,
        }

    # Calcular días restantes
    dias_restantes = (cargo.fecha_vencimiento - hoy).days

    # Cargo vencido (solo si NO está en licencia MJ)
    if dias_restantes < 0:
        dias_vencido = abs(dias_restantes)
        return {
            "tipo": "vencido",
            "dias_vencido": dias_vencido,
            "mensaje": f"Vencido hace {dias_vencido} día{'s' if dias_vencido != 1 else ''}",
            "badge_class": "bg-danger",
            "icono": "bi-exclamation-triangle-fill",
            "urgente": True
        }

    # Vencimiento crítico (menos de 60 días)
    if dias_restantes <= 60:
        return {
            "tipo": "critico",
            "dias_restantes": dias_restantes,
            "fecha_vencimiento": cargo.fecha_vencimiento,
            "mensaje": f"Vence en {dias_restantes} día{'s' if dias_restantes != 1 else ''}",
            "badge_class": "bg-danger",
            "icono": "bi-clock-fill",
            "urgente": True
        }

    # Vencimiento próximo (60-180 días)
    if dias_restantes <= 180:
        return {
            "tipo": "proximo",
            "dias_restantes": dias_restantes,
            "fecha_vencimiento": cargo.fecha_vencimiento,
            "mensaje": f"Vence en {dias_restantes} días",
            "badge_class": "bg-warning text-dark",
            "icono": "bi-clock",
            "urgente": False, 
        }

    # Vencimiento lejano (más de 180 días)
    return {
        "tipo": "vigente",
        "dias_restantes": dias_restantes,
        "fecha_vencimiento": cargo.fecha_vencimiento,
        "mensaje": f"Vigente ({dias_restantes} días)",
        "clase_badge": "bg-success",
        "icono": "bi-check-circle",
        "urgente": False,
    }


def obtener_estado_jubilacion(docente) -> Dict[str, any]:
    """
    Determina el estado del docente respecto a la jubilación.

    Analiza la edad actual del docente y calcula información relevante
    sobre su situación de jubilación considerando dos edades:
    - 65 años: Edad ordinaria de jubilación
    - 70 años: Edad límite con prórroga

    Args:
        docente (Docente): Instancia del modelo Docente

    Returns:
        dict: Diccionario con las siguientes claves:
            - edad_actual (int): Edad actual del docente
            - fecha_jub_65 (date): Fecha en que cumple 65 años
            - fecha_jub_70 (date): Fecha en que cumple 70 años
            - dias_hasta_65 (int|None): Días hasta cumplir 65 (None si ya los cumplió)
            - dias_hasta_70 (int|None): Días hasta cumplir 70 (None si ya los cumplió)
            - estado (str): Estado de jubilación
                * 'activo': Menor de 65 años, no próximo a jubilarse
                * 'proximo_65': A menos de 1 año de cumplir 65
                * 'jubilado_65': Entre 65 y 70 años
                * 'jubilado_70': 70 años o más
            - urgente (bool): Si requiere atención inmediata
            - badge_class (str): Clase CSS para el badge
            - mensaje (str): Mensaje descriptivo

    Example:
        >>> docente = Docente.objects.get(pk=1)
        >>> estado = obtener_estado_jubilacion(docente)
        >>> print(estado)
        {
            'edad_actual': 68,
            'fecha_jub_65': date(2021, 3, 15),
            'fecha_jub_70': date(2026, 3, 15),
            'dias_hasta_65': None,
            'dias_hasta_70': 487,
            'estado': 'jubilado_65',
            'urgente': True,
            'badge_class': 'bg-warning',
            'mensaje': 'Entre 65 y 70 años (487 días para límite)'
        }
    """
    edad_actual = calcular_edad(docente.fecha_nacimiento)
    fecha_jub_65 = obtener_fecha_jubilacion(docente.fecha_nacimiento, 65)
    fecha_jub_70 = obtener_fecha_jubilacion(docente.fecha_nacimiento, 70)

    dias_hasta_65 = dias_hasta_fecha(fecha_jub_65)
    dias_hasta_70 = dias_hasta_fecha(fecha_jub_70)

    # Solo mostrar días positivos
    dias_hasta_65 = dias_hasta_65 if dias_hasta_65 and dias_hasta_65 > 0 else None
    dias_hasta_70 = dias_hasta_70 if dias_hasta_70 and dias_hasta_70 > 0 else None

    # Determinar estado
    if edad_actual >= 70:
        estado = "jubilado_70"
        urgente = True
        badge_class = "bg-danger"
        mensaje = "70 años o más (límite alcanzado)"
    elif edad_actual >= 65:
        estado = "jubilado_65"
        urgente = True
        badge_class = "bg-warning"
        if dias_hasta_70:
            mensaje = f"Entre 65 y 70 años ({dias_hasta_70} días para límite)"
        else:
            mensaje = "Entre 65 y 70 años (próximo al límite)"
    elif dias_hasta_65 and dias_hasta_65 <= 365:
        estado = "proximo_65"
        urgente = False
        badge_class = "bg-info"
        mensaje = f"Próximo a 65 años ({dias_hasta_65} días)"
    else:
        estado = "activo"
        urgente = False
        badge_class = "bg-success"
        if dias_hasta_65:
            años_para_jubilarse = dias_hasta_65 // 365
            mensaje = f"{edad_actual} años ({años_para_jubilarse} años para jubilación)"
        else:
            mensaje = f"{edad_actual} años"

    return {
        "edad_actual": edad_actual,
        "fecha_jub_65": fecha_jub_65,
        "fecha_jub_70": fecha_jub_70,
        "dias_hasta_65": dias_hasta_65,
        "dias_hasta_70": dias_hasta_70,
        "estado": estado,
        "urgente": urgente,
        "badge_class": badge_class,
        "mensaje": mensaje,
    }


def formatear_antiguedad(antiguedad_dict: Dict[str, int]) -> str:
    """
    Formatea un diccionario de antigüedad a texto legible en español.

    Args:
        antiguedad_dict (dict): Diccionario con años, meses, días
                               (como el retornado por calcular_antiguedad)

    Returns:
        str: Texto formateado en español

    Example:
        >>> ant = {'años': 4, 'meses': 2, 'dias': 5, 'total_dias': 1527}
        >>> formatear_antiguedad(ant)
        '4 años y 2 meses'

        >>> ant = {'años': 0, 'meses': 3, 'dias': 15, 'total_dias': 105}
        >>> formatear_antiguedad(ant)
        '3 meses'

        >>> ant = {'años': 0, 'meses': 0, 'dias': 15, 'total_dias': 15}
        >>> formatear_antiguedad(ant)
        '15 días'

    Note:
        - Si hay años y meses, solo muestra años y meses (omite días)
        - Si solo hay meses, muestra solo meses
        - Si es menos de un mes, muestra días
        - Usa singular/plural correctamente
    """
    partes = []

    # Agregar años si existe
    if antiguedad_dict["años"] > 0:
        años_txt = "año" if antiguedad_dict["años"] == 1 else "años"
        partes.append(f"{antiguedad_dict['años']} {años_txt}")

    # Agregar meses si existe (solo si no hay muchos años)
    if antiguedad_dict["meses"] > 0:
        meses_txt = "mes" if antiguedad_dict["meses"] == 1 else "meses"
        partes.append(f"{antiguedad_dict['meses']} {meses_txt}")

    # Si no hay años ni meses, mostrar días
    if not partes:
        dias_txt = "día" if antiguedad_dict["dias"] == 1 else "días"
        partes.append(f"{antiguedad_dict['dias']} {dias_txt}")

    # Unir con "y"
    return " y ".join(partes)


def formatear_antiguedad_completa(antiguedad_dict: Dict[str, int]) -> str:
    """
    Formatea antigüedad incluyendo años, meses Y días.

    Args:
        antiguedad_dict (dict): Diccionario con años, meses, días

    Returns:
        str: Texto formateado completo

    Example:
        >>> ant = {'años': 4, 'meses': 2, 'dias': 5, 'total_dias': 1527}
        >>> formatear_antiguedad_completa(ant)
        '4 años, 2 meses y 5 días'
    """
    partes = []

    if antiguedad_dict["años"] > 0:
        años_txt = "año" if antiguedad_dict["años"] == 1 else "años"
        partes.append(f"{antiguedad_dict['años']} {años_txt}")

    if antiguedad_dict["meses"] > 0:
        meses_txt = "mes" if antiguedad_dict["meses"] == 1 else "meses"
        partes.append(f"{antiguedad_dict['meses']} {meses_txt}")

    if antiguedad_dict["dias"] > 0:
        dias_txt = "día" if antiguedad_dict["dias"] == 1 else "días"
        partes.append(f"{antiguedad_dict['dias']} {dias_txt}")

    if not partes:
        return "0 días"

    if len(partes) == 1:
        return partes[0]
    elif len(partes) == 2:
        return " y ".join(partes)
    else:
        return ", ".join(partes[:-1]) + " y " + partes[-1]


def obtener_alertas_cargo(cargo) -> list:
    """
    Obtiene una lista de todas las alertas aplicables a un cargo.

    Analiza tanto el vencimiento del cargo como la situación de jubilación
    del docente asociado para generar una lista de alertas priorizadas.

    Args:
        cargo (Cargo): Instancia del modelo Cargo

    Returns:
        list: Lista de diccionarios con alertas, cada una con:
            - tipo (str): 'vencimiento' o 'jubilacion'
            - prioridad (int): 1 (urgente) a 3 (informativa)
            - mensaje (str): Mensaje de la alerta
            - badge_class (str): Clase CSS para el badge

    Example:
        >>> cargo = Cargo.objects.get(pk=1)
        >>> alertas = obtener_alertas_cargo(cargo)
        >>> for alerta in alertas:
        ...     print(f"{alerta['prioridad']}: {alerta['mensaje']}")
        1: Cargo vence en 45 días
        2: Docente tiene 68 años (próximo a límite de 70)
    """
    alertas = []

    # Alerta de vencimiento de cargo
    estado_venc = obtener_estado_vencimiento(cargo)
    if estado_venc["urgente"]:
        prioridad = 1 if estado_venc["tipo"] == "vencido" else 2
        alertas.append(
            {
                "tipo": "vencimiento",
                "prioridad": prioridad,
                "urgente": estado_venc["urgente"],
                "mensaje": f"Cargo: {estado_venc['mensaje']}",
                "badge_class": estado_venc["badge_class"],
            }
        )

    # Alerta de jubilación
    estado_jub = obtener_estado_jubilacion(cargo.docente)
    if estado_jub["urgente"]:
        prioridad = 1 if estado_jub["estado"] == "jubilado_70" else 2
        alertas.append(
            {
                "tipo": "jubilacion",
                "prioridad": prioridad,
                "urgente": estado_venc["urgente"],
                "mensaje": f"Docente: {estado_jub['mensaje']}",
                "badge_class": estado_jub["badge_class"],
            }
        )

    # Ordenar por prioridad
    alertas.sort(key=lambda x: x["prioridad"])

    return alertas


def calcular_proximo_vencimiento(cargos_queryset) -> Tuple[Optional[date], int]:
    """
    Encuentra el próximo vencimiento en un conjunto de cargos.

    Args:
        cargos_queryset: QuerySet de cargos

    Returns:
        tuple: (fecha_vencimiento, cantidad_cargos)
               (None, 0) si no hay vencimientos

    Example:
        >>> cargos = Cargo.objects.activos()
        >>> fecha, cantidad = calcular_proximo_vencimiento(cargos)
        >>> print(f"{cantidad} cargos vencen el {fecha}")
        3 cargos vencen el 2025-03-15
    """
    cargos_con_vencimiento = cargos_queryset.filter(
        fecha_vencimiento__isnull=False
    ).order_by("fecha_vencimiento")

    if not cargos_con_vencimiento.exists():
        return None, 0

    primer_vencimiento = cargos_con_vencimiento.first().fecha_vencimiento
    cantidad = cargos_con_vencimiento.filter(
        fecha_vencimiento=primer_vencimiento
    ).count()

    return primer_vencimiento, cantidad


def obtener_cargo_efectivo(cargo) -> Dict[str, any]:
    """
    Determina el cargo efectivo actual de un docente, considerando licencias.
    
    El "cargo efectivo" es lo que el docente está ejerciendo AHORA:
    - Si está activo sin licencia → el cargo mismo
    - Si está en licencia M.J. con cargo docente → el cargo temporal
    - Si está en licencia M.J. por gestión → descripción del cargo de gestión
    - Si está en licencia normal → el cargo con indicador de licencia
    
    Args:
        cargo (Cargo): Instancia del modelo Cargo
        
    Returns:
        dict: Diccionario con información del cargo efectivo
    """
    from django.utils import timezone

    # PRIORIDAD 1: Verificar licencias MJ PRIMERO (vencimiento suspendido)

    # CASO 1: Licencia M.J. con cargo docente vinculado
    if cargo.en_licencia_mayor_jerarquia:

        # Subcaso A: Buscar si tiene cargo docente temporal vinculado
        cargo_temporal = None
        if hasattr(cargo, 'cargo_temporal_mj'):
            cargo_temporal = cargo.cargo_temporal_mj.filter(
                es_cargo_mayor_jerarquia=True,
                estado='activo'
            ).first()
    
        if cargo_temporal:
            # Tiene cargo temporal docente
            observacion = f"Base: {cargo.get_categoria_display()} - {cargo.asignatura.nombre if cargo.asignatura else 'Sin asignatura'}"
    
            return {
                'tipo': 'licencia_mj_docente',
                'cargo_efectivo_display': cargo_temporal.get_categoria_display(),
                'asignatura_efectiva_display': cargo_temporal.asignatura.nombre if cargo_temporal.asignatura else '-',
                'observacion': observacion,
                'badge_class': 'bg-warning text-dark',
                'es_cargo_temporal': True,
                'cargo_base_info': {
                    'categoria': cargo.get_categoria_display(),
                    'asignatura': cargo.asignatura.nombre if cargo.asignatura else '-',
                },
            }
    
        else:
            # Licencia MJ sin cargo temporal (gestión, externa, u otra)
            # Intentar construir descripción del cargo
            cargo_mj_display = "Licencia por Mayor Jerarquía"
    
            if cargo.descripcion_cargo_mj:
                cargo_mj_display = cargo.descripcion_cargo_mj
            elif cargo.tipo_cargo_mj:
                cargo_mj_display = cargo.get_tipo_cargo_mj_display()
    
            if cargo.institucion_cargo_mj:
                cargo_mj_display += f" ({cargo.institucion_cargo_mj})"
    
            observacion = f"Base: {cargo.get_categoria_display()} - {cargo.asignatura.nombre if cargo.asignatura else 'Sin asignatura'}"
    
            return {
                'tipo': 'licencia_mj_gestion',
                'cargo_efectivo_display': cargo_mj_display,
                'asignatura_efectiva_display': '-',
                'observacion': observacion,
                'badge_class': 'bg-warning text-dark',
                'es_cargo_temporal': False,
                'cargo_base_info': {
                    'categoria': cargo.get_categoria_display(),
                    'asignatura': cargo.asignatura.nombre if cargo.asignatura else '-',
                },
            }

    # CASO 3: Licencia normal (NO M.J.)
    if cargo.en_licencia_normal:
        fecha_fin_str = cargo.fecha_fin_licencia_normal.strftime(
            '%d/%m/%Y') if cargo.fecha_fin_licencia_normal else 'Sin fecha'

        return {
            'tipo': 'licencia_normal',
            'cargo_efectivo_display': cargo.get_categoria_display(),
            'asignatura_efectiva_display': cargo.asignatura.nombre if cargo.asignatura else '-',
            'observacion': f'En Licencia hasta {fecha_fin_str}',
            'badge_class': 'bg-info',
            'es_cargo_temporal': False,
            'cargo_base_info': None,
        }

    # ✅ PRIORIDAD 2: Después de verificar licencias, verificar estados inactivos

    # CASO 4: Cargo dado de baja
    if cargo.estado == 'baja':
        return {
            'tipo': 'inactivo',
            'cargo_efectivo_display': cargo.get_categoria_display(),
            'asignatura_efectiva_display': cargo.asignatura.nombre if cargo.asignatura else '-',
            'observacion': 'Dado de baja',
            'badge_class': 'bg-secondary',
            'es_cargo_temporal': False,
            'cargo_base_info': None,
        }

    # CASO 5: Docente jubilado
    if cargo.docente.jubilado:
        return {
            'tipo': 'inactivo',
            'cargo_efectivo_display': cargo.get_categoria_display(),
            'asignatura_efectiva_display': cargo.asignatura.nombre if cargo.asignatura else '-',
            'observacion': 'Docente jubilado',
            'badge_class': 'bg-secondary',
            'es_cargo_temporal': False,
            'cargo_base_info': None,
        }

    # CASO 6: Cargo vencido (solo si NO está en licencia MJ - ya verificado arriba)
    if cargo.fecha_vencimiento and cargo.fecha_vencimiento < timezone.now().date():
        return {
            'tipo': 'inactivo',
            'cargo_efectivo_display': cargo.get_categoria_display(),
            'asignatura_efectiva_display': cargo.asignatura.nombre if cargo.asignatura else '-',
            'observacion': 'Vencido',
            'badge_class': 'bg-danger',
            'es_cargo_temporal': False,
            'cargo_base_info': None,
        }

    # CASO 7: Cargo activo normal (sin licencias)
    return {
        'tipo': 'normal',
        'cargo_efectivo_display': cargo.get_categoria_display(),
        'asignatura_efectiva_display': cargo.asignatura.nombre if cargo.asignatura else '-',
        'observacion': None,
        'badge_class': 'bg-success',
        'es_cargo_temporal': False,
        'cargo_base_info': None,
    }


# ============================================================================
# PLANIFICACIONES - FUNCIONES HELPER
# ============================================================================

def obtener_responsable_planificacion(asignatura):
    """
    Obtiene el docente responsable de la planificación de una asignatura.
    
    Prioridad: Titular → Asociado → Adjunto
    
    Args:
        asignatura (Asignatura): Asignatura para la cual obtener responsable
    
    Returns:
        Cargo|None: Cargo activo del docente responsable, o None si no hay
    
    Example:
        >>> responsable = obtener_responsable_planificacion(asignatura)
        >>> if responsable:
        >>>     print(f"Responsable: {responsable.docente.get_full_name()}")
    """
    from planta_docente.models import Cargo

    ORDEN_PRIORIDAD = ['tit', 'aso', 'adj']

    for categoria in ORDEN_PRIORIDAD:
        cargo = Cargo.objects.filter(
            asignatura=asignatura,
            estado='activo',
            categoria=categoria
        ).select_related('docente').first()

        # Validar que el docente tenga email
        if cargo and cargo.docente and cargo.docente.email:
            return cargo

    return None


def obtener_planificaciones_faltantes(año):
    """
    Obtiene asignaturas que NO tienen planificación subida para el año.
    EXCLUYE asignaturas deshabilitadas para ese año.
    
    Args:
        año: Año lectivo a consultar
        
    Returns:
        QuerySet: Asignaturas sin planificación y activas para el año
    """
    from planta_docente.models import Asignatura, PlanificacionAnual, AsignaturaAnual

    # Asignaturas con planificación ya recibida
    con_planificacion = PlanificacionAnual.objects.filter(
        año=año,
        estado__in=['recibida', 'aprobada']
    ).values_list('asignatura_id', flat=True)

    # Asignaturas deshabilitadas para este año
    deshabilitadas = AsignaturaAnual.objects.filter(
        año=año,
        activa=False
    ).values_list('asignatura_id', flat=True)

    # Asignaturas faltantes = todas - (con planificación + deshabilitadas)
    faltantes = Asignatura.objects.exclude(
        id__in=list(con_planificacion) + list(deshabilitadas)
    ).order_by('nivel', 'nombre')

    return faltantes


def obtener_estadisticas_planificaciones(año):
    """Obtiene estadísticas de planificaciones anuales para un año lectivo específico."""

    from planta_docente.models import Asignatura, PlanificacionAnual, AsignaturaAnual

    # Contar asignaturas deshabilitadas para este año
    asignaturas_deshabilitadas_ids = list(AsignaturaAnual.objects.filter(
        año=año,
        activa=False
    ).values_list('asignatura_id', flat=True))

    total_deshabilitadas = len(asignaturas_deshabilitadas_ids)

    base_queryset = PlanificacionAnual.objects.filter(año=año)

    # Recibidas = las que tienen archivo subido
    con_planificacion = base_queryset.filter(
        archivo__isnull=False).exclude(archivo='').count()
    aprobadas = base_queryset.filter(estado='aprobada').count()
    rechazadas = base_queryset.filter(estado='rechazada').count()

    # Notificadas pendientes = tienen registro pero sin archivo
    notificadas_pendientes = base_queryset.filter(
        fecha_ultima_notificacion__isnull=False
    ).filter(archivo='').count()

    # Total efectivo
    total_asignaturas = Asignatura.objects.count()
    total_efectivo = total_asignaturas - total_deshabilitadas

    # Asignaturas con registro (excluyendo deshabilitadas)
    asignaturas_con_registro = base_queryset.exclude(
        asignatura_id__in=asignaturas_deshabilitadas_ids
    ).values_list('asignatura_id', flat=True)

    # Sin notificar = asignaturas activas sin registro
    sin_notificar = total_efectivo - len(set(asignaturas_con_registro))

    # Faltantes = total sin archivo
    faltantes = total_efectivo - con_planificacion

    # Porcentaje
    porcentaje = round((con_planificacion / total_efectivo *
                       100), 1) if total_efectivo > 0 else 0

    return {
        'total_asignaturas': total_efectivo,
        'con_planificacion': con_planificacion,
        'notificadas_pendientes': notificadas_pendientes,
        'sin_notificar': sin_notificar,
        'pendientes': faltantes,
        'porcentaje_completado': porcentaje,
        'aprobadas': aprobadas,
        'rechazadas': rechazadas,
        'deshabilitadas': total_deshabilitadas,
    }
