# Guía de Deploy — civil-web

Stack: Django 4.2 · PostgreSQL · Gunicorn · Nginx · Ubuntu/Debian

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

CREATE DATABASE civil_web;
CREATE USER civil_user WITH PASSWORD 'contraseña-segura';
ALTER ROLE civil_user SET client_encoding TO 'utf8';
ALTER ROLE civil_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE civil_user SET timezone TO 'America/Argentina/Buenos_Aires';
GRANT ALL PRIVILEGES ON DATABASE civil_web TO civil_user;
\q
```

---

## 3. Clonar y configurar el proyecto

```bash
# Clonar
git clone https://github.com/Dept-Civil-UTN-FRLP/civil-web.git /home/jronconi/civil-web
cd /home/jronconi/civil-web

# Entorno virtual
python3.12 -m venv venv
source venv/bin/activate

# Dependencias Python
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
SECRET_KEY=<generada arriba>
DEBUG=False
ALLOWED_HOSTS=civil.frlp.utn.edu.ar,<IP del servidor>

DEPARTAMENTO=civil
MODULOS_ACTIVOS=equivalencias,carrera_academica,planta_docente

DB_ENGINE=django.db.backends.postgresql
DB_NAME=civil_web
DB_USER=civil_user
DB_PASSWORD=<contraseña-segura>
DB_HOST=localhost
DB_PORT=5432

EMAIL_HOST_USER=<cuenta Office365>
SMTP_PASS=<contraseña SMTP>
PLANTA_DOCENTE_EMAIL=dicivil@frlp.utn.edu.ar

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

Crear `/etc/systemd/system/civil.service`:

```ini
[Unit]
Description=civil-web Gunicorn
After=network.target

[Service]
User=jronconi
Group=www-data
WorkingDirectory=/home/jronconi/civil-web
ExecStart=/home/jronconi/civil-web/venv/bin/gunicorn \
    --workers 3 \
    --bind unix:/run/civil.sock \
    config.wsgi:application
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable civil
sudo systemctl start civil
```

---

## 7. Nginx

Crear `/etc/nginx/sites-available/civil`:

```nginx
server {
    listen 80;
    server_name civil.frlp.utn.edu.ar;

    client_max_body_size 20M;

    location /static/ {
        alias /home/jronconi/civil-web/staticfiles/;
    }

    location /media/private/ {
        internal;
        alias /home/jronconi/civil-web/media/private/;
    }

    location / {
        proxy_pass http://unix:/run/civil.sock;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/civil /etc/nginx/sites-enabled/
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
0 3 * * * /home/jronconi/civil-web/venv/bin/python /home/jronconi/civil-web/manage.py comprimir_formularios >> /var/log/civil-comprimir-pdfs.log 2>&1
```

Para correr manualmente o probar:

```bash
python manage.py comprimir_formularios --dry-run     # muestra qué comprimiría sin cambios
python manage.py comprimir_formularios               # comprime
python manage.py comprimir_formularios --calidad printer  # mayor calidad (300 dpi)
```

---

## 9. Deploy de actualizaciones

El script `deploy.sh` automatiza el proceso:

```bash
bash deploy.sh
```

Hace: `git pull` → `pip install` → `migrate` → `collectstatic` → `systemctl restart civil`.

---

## 10. Verificación post-deploy

```bash
# Estado del servicio
sudo systemctl status civil

# Logs en tiempo real
sudo journalctl -u civil -f

# Test de compresión de PDFs
python manage.py comprimir_formularios --dry-run
```
