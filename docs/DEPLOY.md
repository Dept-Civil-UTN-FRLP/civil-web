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

## 11. Agente de Correo (IA)

Ver `issues/agente_mail/` para el plan completo (modelos, vistas, comando). Esta sección cubre
solo lo que hace falta en el servidor de producción, una vez que el código ya está desplegado.

### 11.1 Nginx — rate limit del webhook de Telegram

En el bloque `http {}` de `/etc/nginx/nginx.conf` (fuera del `server {}` de este sitio):

```nginx
limit_req_zone $binary_remote_addr zone=agente_mail_webhook:10m rate=10r/s;
```

En `/etc/nginx/sites-available/<SERVICE_NAME>`, sumar **antes** del `location /` genérico:

```nginx
    location /agente-mail/telegram/webhook/ {
        limit_req zone=agente_mail_webhook burst=20 nodelay;
        proxy_pass http://unix:/run/<SERVICE_NAME>.sock;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
```

```bash
sudo nginx -t
sudo systemctl reload nginx
```

El resto de las URLs de `agente_mail` (`/microsoft/iniciar/`, `/microsoft/callback/`) ya están
protegidas por `@login_required` + `is_superuser` a nivel Django — solo el webhook necesita esta
capa extra en nginx, porque es la única URL que acepta POSTs sin sesión de Django (la protección
ahí es el secret token de Telegram + el chequeo de `TELEGRAM_ADMIN_IDS`).

### 11.2 Cron

```bash
crontab -e
```

```
*/5 * * * * <PROJECT_DIR>/venv/bin/python <PROJECT_DIR>/manage.py revisar_mails --limite 10 >> /var/log/<SERVICE_NAME>-agente-mail.log 2>&1
```

### 11.3 Variables de entorno

Ver `.env.example` (sección "Agente de Correo (IA)") para la lista completa con instrucciones de
dónde conseguir cada valor. Activar recién con `AGENTE_MAIL_ENABLED=True` al final, después de
completar el flujo de autenticación una vez (`/agente-mail/microsoft/iniciar/` como superusuario).

### 11.4 Vencimiento de secretos

- **`O365_CLIENT_SECRET`**: expira según lo configurado en Azure AD (máx. 24 meses). Anotar la
  fecha de expiración acá cuando se genere: `<pendiente de completar en el primer deploy>`.
- **Certificado TLS de `dicivil.frlp.utn.edu.ar`**: verificar vigencia con
  `echo | openssl s_client -connect dicivil.frlp.utn.edu.ar:443 2>/dev/null | openssl x509 -noout -dates`.
  Telegram exige HTTPS válido para `setWebhook`.
