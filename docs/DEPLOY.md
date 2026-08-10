# Guía de Deploy — civil-web

Stack: Django 4.2 · PostgreSQL · Gunicorn · Nginx · Ubuntu/Debian

Variables usadas en esta guía — reemplazarlas con los valores reales:

| Variable | Ejemplo |
|---|---|
| `<USER>` | usuario del sistema que corre la app |
| `<PROJECT_DIR>` | ruta absoluta del repositorio, ej. `/home/<USER>/civil-web` |
| `<SERVICE_NAME>` | nombre del servicio systemd, ej. `civil-web` |
| `<DOMAIN>` | dominio o IP del servidor |

---

## 1. Paquetes del sistema

```bash
sudo apt update && sudo apt install -y \
    python3.12 python3.12-venv python3.12-dev \
    postgresql postgresql-contrib \
    nginx \
    git \
    ghostscript \
    libpango-1.0-0 libpangocairo-1.0-0 \
    libcairo2 libgdk-pixbuf2.0-0 \
    libffi-dev libssl-dev \
    build-essential
```

| Paquete | Para qué |
|---|---|
| `python3.12` | Runtime |
| `postgresql` | Base de datos |
| `nginx` | Proxy reverso |
| `ghostscript` | Compresión nocturna de PDFs |
| `libpango*` `libcairo*` `libgdk*` | WeasyPrint (generación de PDFs) |
| `libffi-dev` `libssl-dev` | Compilación de psycopg2 y cryptography |

---

## 2. Base de datos

```bash
sudo -u postgres psql

CREATE DATABASE <DB_NAME>;
CREATE USER <DB_USER> WITH PASSWORD '<DB_PASSWORD>';
ALTER ROLE <DB_USER> SET client_encoding TO 'utf8';
ALTER ROLE <DB_USER> SET default_transaction_isolation TO 'read committed';
ALTER ROLE <DB_USER> SET timezone TO 'America/Argentina/Buenos_Aires';
GRANT ALL PRIVILEGES ON DATABASE <DB_NAME> TO <DB_USER>;
\q
```

---

## 3. Clonar y configurar el proyecto

```bash
git clone https://github.com/Dept-Civil-UTN-FRLP/civil-web.git <PROJECT_DIR>
cd <PROJECT_DIR>

python3.12 -m venv venv
source venv/bin/activate

pip install -r requirements.txt
```

---

## 4. Variables de entorno

```bash
cp .env.example .env
```

Generar SECRET_KEY:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Editar `.env` con los valores reales:

```env
SERVICE_NAME=<nombre del servicio systemd>

SECRET_KEY=<generada arriba>
DEBUG=False
ALLOWED_HOSTS=<DOMAIN>

DEPARTAMENTO=civil
MODULOS_ACTIVOS=equivalencias,carrera_academica,planta_docente

DB_ENGINE=django.db.backends.postgresql
DB_NAME=<DB_NAME>
DB_USER=<DB_USER>
DB_PASSWORD=<DB_PASSWORD>
DB_HOST=localhost
DB_PORT=5432

EMAIL_HOST_USER=<cuenta SMTP>
SMTP_PASS=<contraseña SMTP>
PLANTA_DOCENTE_EMAIL=<email de notificaciones>

COMPRESS_PDFS=True
```

---

## 5. Inicializar la aplicación

```bash
source venv/bin/activate

python manage.py migrate
python manage.py collectstatic --no-input
python manage.py createsuperuser
```

---

## 6. Servicio Gunicorn (systemd)

Crear `/etc/systemd/system/<SERVICE_NAME>.service`:

```ini
[Unit]
Description=civil-web Gunicorn
After=network.target

[Service]
User=<USER>
Group=www-data
WorkingDirectory=<PROJECT_DIR>
ExecStart=<PROJECT_DIR>/venv/bin/gunicorn \
    --workers 3 \
    --bind unix:/run/<SERVICE_NAME>.sock \
    config.wsgi:application
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable <SERVICE_NAME>
sudo systemctl start <SERVICE_NAME>
```

---

## 7. Nginx

Crear `/etc/nginx/sites-available/<SERVICE_NAME>`:

```nginx
server {
    listen 80;
    server_name <DOMAIN>;

    client_max_body_size 20M;

    location /static/ {
        alias <PROJECT_DIR>/staticfiles/;
    }

    location /media/private/ {
        internal;
        alias <PROJECT_DIR>/media/private/;
    }

    location / {
        proxy_pass http://unix:/run/<SERVICE_NAME>.sock;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/<SERVICE_NAME> /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---

## 8. Cron — compresión nocturna de PDFs

```bash
crontab -e
```

Agregar:

```
0 3 * * * <PROJECT_DIR>/venv/bin/python <PROJECT_DIR>/manage.py comprimir_formularios >> /var/log/<SERVICE_NAME>-pdfs.log 2>&1
```

Para correr manualmente o probar:

```bash
python manage.py comprimir_formularios --dry-run      # muestra qué comprimiría sin cambios
python manage.py comprimir_formularios                # comprime
python manage.py comprimir_formularios --calidad printer  # mayor calidad (300 dpi)
```

---

## 9. Deploy de actualizaciones

El script `deploy.sh` automatiza el proceso:

```bash
bash deploy.sh
```

Hace: `git pull` → `pip install` → `migrate` → `collectstatic` → reinicio del servicio.

---

## 10. Verificación post-deploy

```bash
# Estado del servicio
sudo systemctl status <SERVICE_NAME>

# Logs en tiempo real
sudo journalctl -u <SERVICE_NAME> -f

# Test de compresión de PDFs
python manage.py comprimir_formularios --dry-run
```

---

## 11. Portal de Jurados

Reemplaza el envío de documentación por mail con adjuntos por un link personal:
el jurado entra a `/carrera/portal-jurados/<token>/`, confirma su DNI, y ve las
Carreras Académicas donde participa. Ver `carrera_academica/views_portal_jurado.py`.

**Variables de entorno** (agregar al `.env`, ver `.env.example`):

```env
PORTAL_JURADOS_ENABLED=True
PORTAL_JURADO_TOKEN_DIAS_VALIDEZ=60
PORTAL_JURADO_SESSION_MINUTOS=60
```

Con `PORTAL_JURADOS_ENABLED=False` (default) las URLs del portal ni se registran
— es el kill switch, independiente de `MODULOS_ACTIVOS` (esa gatea toda la app
`carrera_academica`, esto solo la superficie pública nueva).

**Rate limiting (nginx)** — la única ruta adivinable/fuerza-bruteable es la de
entrada con DNI (`/carrera/portal-jurados/<token>/`); el resto de las vistas
requieren una sesión ya verificada, así que no necesitan `limit_req` propio.

En el bloque `http {}` de `/etc/nginx/nginx.conf`:

```nginx
limit_req_zone $binary_remote_addr zone=portal_jurados:10m rate=5r/m;
```

En `/etc/nginx/sites-available/<SERVICE_NAME>`, agregar **antes** del
`location /` genérico (mismo `proxy_pass` que el resto del sitio):

```nginx
location ~ ^/carrera/portal-jurados/[^/]+/$ {
    limit_req zone=portal_jurados burst=10 nodelay;
    include proxy_params;
    proxy_pass http://unix:/run/<SERVICE_NAME>.sock;
}
```

```bash
sudo nginx -t
sudo systemctl reload nginx
```

**No hace falta agregar ni tocar ningún `location` de medios**: el portal sirve
los PDFs reusando el mismo mecanismo que ya usa el resto del sitio
(`X-Accel-Redirect` hacia `/protected-media/private/...`, servido internamente
por el bloque `location /protected-media/private/ { internal; ... }` ya
existente en el nginx del servidor).
