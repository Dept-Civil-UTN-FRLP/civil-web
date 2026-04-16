# civil-web

Sistema de gestión administrativa para departamentos de ingeniería — UTN FRLP.

## Módulos

El sistema está compuesto por tres módulos independientes:

- **equivalencias**: gestión de solicitudes de equivalencias, seguimiento de dictámenes y generación de actas.
- **carrera_academica**: expedientes de carrera académica, prórrogas y evaluaciones docentes.
- **planta_docente**: cargos docentes, vencimientos, jubilaciones y planificaciones anuales.

---

## Configuración por departamento

Cada instancia del sistema se configura mediante variables de entorno. Esto permite desplegar el mismo codebase para distintos departamentos, activando solo los módulos relevantes y mostrando la landing correspondiente.

### Variables de entorno

Copiá `.env.example` y ajustá los valores:

```bash
cp .env.example .env
```

| Variable | Descripción | Ejemplo |
|---|---|---|
| `DEPARTAMENTO` | Determina qué landing se muestra | `civil` |
| `MODULOS_ACTIVOS` | Módulos habilitados (separados por coma) | `equivalencias,carrera_academica,planta_docente` |

### Departamentos disponibles

| Valor | Landing |
|---|---|
| `civil` | Ingeniería Civil |
| `industrial` | Ingeniería Industrial |

Para agregar un nuevo departamento: crear la view en `config/views.py` y registrarla en el dict `LANDING_VIEWS` en `config/urls.py`.

### Ejemplos de configuración

**Instancia Civil** (todos los módulos):

```env
DEPARTAMENTO=civil
MODULOS_ACTIVOS=equivalencias,carrera_academica,planta_docente
```

**Instancia Industrial** (solo equivalencias):

```env
DEPARTAMENTO=industrial
MODULOS_ACTIVOS=equivalencias
```

---

## Instalación

### 1. Clonar el repositorio

```bash
git clone
cd
```

### 2. Crear entorno virtual

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 4. Configurar variables de entorno

```bash
cp .env.example .env

# Generar SECRET_KEY
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

# Editar .env y pegar la SECRET_KEY generada
```

### 5. Aplicar migraciones

```bash
python manage.py migrate
```

### 6. Crear superusuario

```bash
python manage.py createsuperuser
```

### 7. Ejecutar servidor

```bash
python manage.py runserver
```

---

## Configuración de firma en actas

La firma que aparece en las actas de equivalencias se gestiona desde el admin de Django en **Equivalencias → Configuración del Departamento**. Solo puede haber una configuración activa a la vez; al activar una fila, las demás se desactivan automáticamente.

Campos:

- **Firma imagen**: archivo de imagen (PNG con fondo transparente recomendado)
- **Nombre firmante**: nombre completo que aparece bajo la firma
- **Cargo firmante**: cargo institucional

---

## Stack

- **Backend**: Django 5, Python 3.12, PostgreSQL
- **Frontend**: Bootstrap 5
- **Server**: Nginx + Gunicorn
- **PDF**: WeasyPrint
- **Email**: SMTP Office365

---

## Performance

Este proyecto está optimizado para minimizar queries a la base de datos:

- **Managers personalizados** con `select_related()` y `prefetch_related()`
- **~90% reducción** en número de queries
- **~85% reducción** en tiempo de carga

### Herramientas de desarrollo

#### Django Debug Toolbar

```bash
# Ya está instalado, visitar en desarrollo:
http://localhost:8000/__debug__/
```

#### Análisis de queries

```bash
python manage.py analyze_queries
```

Consultar `docs/OPTIMIZACIONES.md` para detalles completos.

---

UTN — Facultad Regional La Plata
