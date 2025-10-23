# Documento de Validaciones

## Carrera Académica

1. **Carácter del Cargo**
   - Solo cargos Regulares (`reg`) u Ordinarios (`ord`) pueden tener Carrera Académica
   - Error: `invalid_caracter`

2. **Fechas**
   - Fecha de vencimiento debe ser posterior a fecha de inicio
   - Duración mínima: 2 años
   - Error: `invalid_date_range`, `duration_too_short`

3. **Unicidad**
   - No puede haber dos CA activas para el mismo cargo
   - Error: `duplicate_active_ca`

4. **Estado Finalizada**
   - Si estado = 'FIN', debe tener fecha_finalizacion
   - Error: `missing_finalization_date`

## Evaluación


1. **Rango de Años**
   - Los años deben estar entre el inicio de la CA y el año actual
   - No se pueden evaluar años futuros
   - Error: `year_before_ca_start`, `future_year`

2. **Solapamiento**
   - No puede haber años repetidos entre evaluaciones de la misma CA
   - Error: `overlapping_years`

3. **Estado Realizada**
   - Si estado = 'REA', debe tener fecha_evaluacion
   - Error: `missing_evaluation_date`

## Formulario


1. **Formularios Anuales**
   - F04, F05, F06, F07, ENC, F13 deben tener anio_correspondiente
   - Error: `missing_year`

2. **Rango de Años**
   - El año debe estar dentro del período de la CA
   - Error: `year_out_of_range`

3. **Estado Entregado**
   - Debe tener archivo adjunto
   - Debe tener fecha_entrega
   - Error: `missing_file`, `missing_delivery_date`

## Cargo

1. **Fechas**
   - fecha_final > fecha_inicio
   - fecha_vencimiento > fecha_inicio
   - Solo reg/ord tienen fecha_vencimiento
   - Error: `invalid_date_range`, `invalid_vencimiento_for_caracter`

2. **Dedicación**
   - Ad-Honorem no puede tener DE o SE
   - Horas deben corresponder con dedicación (±20%)
   - Error: `invalid_dedication_for_adhonorem`, `invalid_hours_for_dedication`

3. **Unicidad**
   - No puede haber cargos activos duplicados (mismo docente + asignatura)
   - Error: `duplicate_active_cargo`

## Docente

1. **Fecha de Nacimiento**
   - No puede ser futura
   - Debe tener al menos 18 años
   - Error: `future_birth_date`, `underage`

## Resolución

1. **Año**
   - No puede ser futuro
   - Debe ser >= 1950
   - Error: `future_year`, `year_too_old`

2. **Licencias**
   - Alta de licencia requiere fecha_inicio_licencia
   - Baja de licencia requiere fecha_fin_licencia
   - fecha_fin > fecha_inicio
   - Error: `missing_license_start`, `missing_license_end`, `invalid_license_dates`

3. **Prórroga CA**
   - Solo se puede crear para cargos con CA existente
   - Error: `no_ca_for_prorroga`






####################################################
##################################################3#

### Paso 10: Commit y Push

```bash
git add .
git commit -m "feat: Agregar validaciones robustas a modelos y forms

- Implementar método clean() en todos los modelos principales
- Agregar validaciones cruzadas en formularios
- Crear validadores personalizados
- Implementar manejo de errores en views con logging
- Agregar auto-completado de campos (ej: fecha_entrega)
- Crear tests unitarios para validaciones
- Documentar todas las reglas de negocio

Validaciones agregadas:
- CarreraAcademica: caracter, fechas, duración, unicidad
- Evaluacion: rango de años, solapamiento
- Formulario: años, archivos, estados
- Cargo: fechas, dedicación, duplicados
- Docente: edad mínima
- Resolucion: años, licencias

Beneficios:
- Prevención de datos inconsistentes
- Mensajes de error claros y útiles
- Mejor experiencia de usuario
- Facilita debugging con logs

BREAKING CHANGE: Algunos datos existentes pueden fallar validaciones.
Revisar base de datos antes de actualizar."

git push origin feature/add-model-validations
```

### Paso 11: Crear Pull Request

```bash
gh pr create --title "Agregar validaciones robustas a modelos y forms" \
  --body "## Descripción
Implementa validaciones completas en todos los modelos y formularios para prevenir inconsistencias de datos.

## Cambios Principales

### Validaciones en Modelos
- ✅ CarreraAcademica: 6 validaciones (carácter, fechas, duración, etc.)
- ✅ Evaluacion: 3 validaciones (rango años, solapamiento, estado)
- ✅ Formulario: 4 validaciones (años, archivos, entrega)
- ✅ Cargo: 6 validaciones (fechas, dedicación, duplicados)
- ✅ Docente: 2 validaciones (edad, fecha nacimiento)
- ✅ Resolucion: 6 validaciones (años, licencias, prórroga)

### Validaciones en Forms
- ✅ Validaciones cruzadas
- ✅ Mensajes de error descriptivos
- ✅ Formato de expediente

### Manejo de Errores
- ✅ Try-catch en views críticas
- ✅ Logging de errores
- ✅ Mensajes al usuario

### Tests
- ✅ 15+ tests unitarios
- ✅ Cobertura de casos edge

## Testing
- [x] Tests unitarios pasan
- [x] Validaciones funcionan en admin
- [x] Mensajes de error son claros
- [x] Datos válidos se guardan correctamente
- [x] Datos inválidos son rechazados

## Documentación
- [x] Documento de validaciones (VALIDACIONES.md)
- [x] Docstrings en métodos clean()
- [x] Tests documentados

## ⚠️ Breaking Changes
Algunos datos existentes pueden no cumplir las nuevas validaciones.

### Antes de mergear:
1. Backup de la base de datos
2. Ejecutar tests: \`python manage.py test carrera_academica.tests.test_validations\`
3. Revisar datos existentes que puedan fallar validaciones

## Migración
\`\`\`bash
python manage.py makemigrations
python manage.py migrate
python manage.py test
\`\`\`"
```

---

## Checklist Final

```bash
# 1. Verificar que todos los tests pasan
python manage.py test carrera_academica.tests.test_validations

# 2. Verificar que no hay errores de sintaxis
python manage.py check

# 3. Verificar migraciones
python manage.py makemigrations --dry-run

# 4. Probar flujos completos manualmente
# - Crear CA válida ✓
# - Intentar crear CA inválida ✓
# - Crear evaluación válida ✓
# - Intentar evaluar año futuro ✓
```
