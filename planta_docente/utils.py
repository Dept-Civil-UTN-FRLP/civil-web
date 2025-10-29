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
from django.utils import timezone
from typing import Dict, Optional, Tuple


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


def obtener_estado_vencimiento(cargo) -> Dict[str, any]:
    """
    Determina el estado del vencimiento de un cargo con información detallada.

    Clasifica el vencimiento en categorías según la urgencia y proporciona
    información útil para alertas y reportes.

    Args:
        cargo (Cargo): Instancia del modelo Cargo

    Returns:
        dict: Diccionario con las siguientes claves:
            - tipo (str): Categoría del vencimiento
                * 'sin_vencimiento': El cargo no tiene fecha de vencimiento
                * 'vencido': Ya pasó la fecha de vencimiento
                * 'critico': Vence en menos de 60 días
                * 'proximo': Vence entre 60 y 180 días
                * 'vigente': Vence en más de 180 días
            - dias (int): Días hasta/desde el vencimiento (negativo si venció)
            - urgente (bool): Si requiere atención inmediata
            - badge_class (str): Clase CSS para el badge (para templates)
            - mensaje (str): Mensaje descriptivo para mostrar al usuario

    Example:
        >>> cargo = Cargo.objects.get(pk=1)
        >>> estado = obtener_estado_vencimiento(cargo)
        >>> print(estado)
        {
            'tipo': 'critico',
            'dias': 45,
            'urgente': True,
            'badge_class': 'bg-danger',
            'mensaje': 'Vence en 45 días'
        }
    """
    if not cargo.fecha_vencimiento:
        return {
            "tipo": "sin_vencimiento",
            "dias": None,
            "urgente": False,
            "badge_class": "bg-secondary",
            "mensaje": "Sin vencimiento",
        }

    dias = dias_hasta_fecha(cargo.fecha_vencimiento)

    if dias < 0:
        return {
            "tipo": "vencido",
            "dias": abs(dias),
            "urgente": True,
            "badge_class": "bg-danger",
            "mensaje": f"Vencido hace {abs(dias)} días",
        }
    elif dias <= 60:
        return {
            "tipo": "critico",
            "dias": dias,
            "urgente": True,
            "badge_class": "bg-danger",
            "mensaje": f"Vence en {dias} días",
        }
    elif dias <= 180:
        return {
            "tipo": "proximo",
            "dias": dias,
            "urgente": False,
            "badge_class": "bg-warning",
            "mensaje": f"Vence en {dias} días",
        }
    else:
        return {
            "tipo": "vigente",
            "dias": dias,
            "urgente": False,
            "badge_class": "bg-success",
            "mensaje": f"Vigente ({dias} días)",
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
