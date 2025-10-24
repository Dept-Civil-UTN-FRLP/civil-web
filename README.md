# Sistema de Gestión de Expedientes

## Configuración Inicial

### 1. Clonar el repositorio
```bash
git clone 
cd 
```

### 2. Crear entorno virtual
```bash
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate
```

### 3. Instalar dependencias
```bash
pip install -r requirements.txt
```

### 4. Configurar variables de entorno
```bash
# Copiar el archivo de ejemplo
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

## Variables de Entorno

Ver `.env.example` para la lista completa de variables requeridas.

## Performance

Este proyecto está optimizado para minimizar queries a la base de datos:

- **Managers personalizados** con `select_related()` y `prefetch_related()`
- **~90% reducción** en número de queries
- **~85% reducción** en tiempo de carga

### Herramientas de Desarrollo

#### Django Debug Toolbar

```bash
# Ya está instalado, visitar en desarrollo:
http://localhost:8000/__debug__/
```

#### Análisis de Queries

```bash
python manage.py analyze_queries
```

### Ver Optimizaciones

Consultar `docs/OPTIMIZACIONES.md` para detalles completos.
