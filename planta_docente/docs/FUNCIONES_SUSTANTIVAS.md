# Funciones Sustantivas

Sistema para gestionar funciones sustantivas vinculadas a cargos docentes según normativa de concursos UTN.

## Normativa

Según el reglamento de concursos UTN-FRLP:

> Los concursos se llamarán por área de conocimientos, indicando la asignatura prioritaria sobre la que el profesor desarrollará la clase pública. **Cuando la asignatura indicada sea de 2 o 3 hs cátedra**, la FR deberá presentar las **funciones sustantivas** que desarrollará el docente concursado mientras dure su designación.

**Requisitos:**

- Todas las funciones sustantivas deben incluirse en la **Resolución de llamado a concurso del Consejo Directivo**
- Son **obligatorias** durante la designación del docente
- Deben estar formalmente documentadas

## Tipos de Funciones Sustantivas

### 1. Docencia - Grado

- Segundo curso de grado
- Asignaturas electivas
- Dirección/codirección de proyectos finales
- Tutorías de estudiantes
- Dirección/supervisión de prácticas supervisadas
- Dirección/supervisión de trabajos de campo

### 2. Docencia - Posgrado

- Cursos o seminarios
- Dirección/codirección de tesis
- Dirección/codirección de proyectos integradores (carreras de especialización)

### 3. Investigación

- Participación en PID UTN (con publicación, desarrollo y/o transferencia anual)

### 4. Extensión

- Cursos o seminarios
- Capacitación
- Voluntariado universitario
- Servicios y/o transferencia al medio

## Modelo de Datos

### ActividadSustantiva

**Campos principales:**

- `cargo`: FK al cargo base (donde está designado formalmente)
- `categoria`: Categoría calculada automáticamente (docencia_grado, docencia_posgrado, investigacion, extension)
- `tipo_actividad`: Tipo específico de actividad
- `asignatura_vinculada`: Asignatura donde desarrolla la actividad (opcional, solo para docencia)
- `descripcion`: Descripción detallada de la función
- `horas_semanales`: Carga horaria estimada
- `resolucion_cd`: Resolución CD que establece la función (**obligatorio**)
- `fecha_inicio/fecha_fin`: Vigencia de la función
- `activa`: Estado actual

**Propiedades:**

- `vigente`: Verifica si está actualmente vigente (activa + dentro del período)

**Validaciones:**

- Docencia en segundo curso/electiva requiere `asignatura_vinculada`
- PID requiere `codigo_proyecto`
- Fechas coherentes (fin > inicio)
- Categoría se asigna automáticamente según tipo

## Métodos del Modelo Cargo

### `requiere_funciones_sustantivas()`

Verifica si el cargo requiere declarar funciones sustantivas según normativa.

```python
requiere, razon = cargo.requiere_funciones_sustantivas()
# → (True, "Asignatura con 3hs cátedra requiere declarar funciones sustantivas")
```

### `get_funciones_sustantivas_activas()`

Retorna QuerySet con funciones activas.

```python
funciones = cargo.get_funciones_sustantivas_activas()
# → QuerySet<ActividadSustantiva>
```

### `resumen_funciones_sustantivas()`

Agrupa funciones por categoría.

```python
resumen = cargo.resumen_funciones_sustantivas()
# → {
#     'docencia_grado': [ActividadSustantiva(...)],
#     'docencia_posgrado': [],
#     'investigacion': [ActividadSustantiva(...)],
#     'extension': []
# }
```

### `tiene_funciones_sustantivas_completas()`

Valida si cumple con el requerimiento normativo.

```python
completo, mensaje = cargo.tiene_funciones_sustantivas_completas()
# → (True, "Tiene 2 función(es) sustantiva(s) declarada(s)")
```

### `get_horas_funciones_sustantivas()`

Calcula totales de horas por categoría.

```python
horas = cargo.get_horas_funciones_sustantivas()
# → {
#     'docencia_grado': 7,
#     'docencia_posgrado': 0,
#     'investigacion': 5,
#     'extension': 0,
#     'total': 12
# }
```

## Vistas

### `gestionar_funciones_sustantivas(cargo_pk)`

Dashboard principal con:

- Verificación de requerimiento normativo
- Listado agrupado por categoría
- Resumen de horas
- Estado de completitud

**URL:** `/planta/cargo/<id>/funciones-sustantivas/`

### `crear_funcion_sustantiva(cargo_pk)`

Formulario de alta con:

- Validaciones client-side (Bootstrap)
- Campos dinámicos según tipo
- Selección de asignatura vinculada
- Resolución CD obligatoria

**URL:** `/planta/cargo/<id>/funciones-sustantivas/crear/`

### `editar_funcion_sustantiva(pk)`

Formulario de edición con valores pre-cargados.

**URL:** `/planta/funciones-sustantivas/<id>/editar/`

### `eliminar_funcion_sustantiva(pk)`

Confirmación de eliminación con información completa.

**URL:** `/planta/funciones-sustantivas/<id>/eliminar/`

### `toggle_activa_funcion_sustantiva(pk)`

Endpoint AJAX para activar/desactivar.

**URL:** `/planta/funciones-sustantivas/<id>/toggle/` (POST)

## Integración con Otros Módulos

### Detalle de Cargo

- Card informativa si requiere funciones sustantivas
- Badge de estado (completo/incompleto)
- Lista de funciones registradas
- Resumen visual de horas
- Botón de gestión en sidebar

### Estructura de Cátedra (PDF)

- Detecta docentes con función sustantiva en la asignatura
- Marca con asterisco (*) en las tablas
- Incluye leyenda explicativa
- Identifica cargo de origen

## Casos de Uso

### Caso 1: Cargo en Asignatura de 3hs

```
Cargo: Adjunto Simple en "Ferrocarriles 1" (3hs semanales)
↓
Sistema detecta: Requiere funciones sustantivas
↓
Docente registra:
  1. Docencia en "Ferrocarriles 2" (7hs)
  2. Participación en PID-UTN-2024-001 (5hs)
↓
Total: 12hs de funciones sustantivas
Estado: Completo ✓
```

### Caso 2: Estructura de Cátedra

```
PDF de "Ferrocarriles 2":
- Muestra profesor titular con cargo en esa asignatura
- Muestra profesor adjunto* con función sustantiva desde "Ferrocarriles 1"
- Leyenda explica el asterisco
```

## Admin

### ActividadSustantivaAdmin

- Filtros: activa, categoría, tipo, fecha
- Búsqueda: docente, descripción, proyecto
- Autocomplete: cargo, asignatura, resolución
- Fieldsets organizados por secciones
- Badge visual de estado vigente

### Inline en CargoAdmin

- Gestión rápida desde el cargo
- Vista tabular compacta
- Solo campos esenciales

## Permisos

Requiere permisos Django estándar:

- `planta_docente.view_actividadsustantiva`
- `planta_docente.add_actividadsustantiva`
- `planta_docente.change_actividadsustantiva`
- `planta_docente.delete_actividadsustantiva`

## Validaciones

### Nivel Modelo

- Tipos específicos requieren asignatura vinculada
- PID requiere código de proyecto
- Fechas coherentes
- Categoría automática

### Nivel Vista

- Formularios con validación Bootstrap
- Campos obligatorios marcados
- Mensajes de error claros

### Nivel Template

- JavaScript para campos dinámicos
- Validación client-side
- Feedback visual inmediato

## Reportes y Consultas

### Cargos sin funciones sustantivas completas

```python
from planta_docente.models import Cargo

cargos_incompletos = []
for cargo in Cargo.objects.filter(estado='activo'):
    completo, _ = cargo.tiene_funciones_sustantivas_completas()
    if not completo:
        cargos_incompletos.append(cargo)
```

### Docentes con múltiples funciones

```python
from django.db.models import Count
from planta_docente.models import ActividadSustantiva

funciones_por_cargo = ActividadSustantiva.objects.filter(
    activa=True
).values('cargo__docente__apellido', 'cargo__docente__nombre').annotate(
    total=Count('id')
).order_by('-total')
```

### Horas totales por categoría

```python
from django.db.models import Sum
from planta_docente.models import ActividadSustantiva

totales = ActividadSustantiva.objects.filter(
    activa=True
).values('categoria').annotate(
    total_horas=Sum('horas_semanales')
)
```

## Futuras Mejoras

- [ ] Dashboard de estadísticas de funciones sustantivas
- [ ] Alertas automáticas por vencimiento
- [ ] Export Excel de funciones por departamento
- [ ] Validación cruzada con sistema de PID
- [ ] Histórico de cambios en funciones
- [ ] Notificaciones a docentes
- [ ] Integración con sistema de seguimiento de concursos
- [ ] Reportes de cumplimiento normativo
- [ ] API REST para consultas externas

## Referencias

- Normativa de concursos UTN-FRLP
- Reglamento de carrera docente
- Ordenanza de investigación (PID)
