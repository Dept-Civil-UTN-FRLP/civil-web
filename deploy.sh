#!/bin/bash
set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$PROJECT_DIR/venv"

# Leer SERVICE_NAME del .env; si no existe, usar "civil-web" como fallback
SERVICE_NAME="$(grep -E '^SERVICE_NAME=' "$PROJECT_DIR/.env" 2>/dev/null | cut -d '=' -f2 | tr -d '[:space:]')"
SERVICE_NAME="${SERVICE_NAME:-civil-web}"

cd "$PROJECT_DIR"

git pull

source "$VENV_DIR/bin/activate"

pip install -r requirements.txt --quiet

python manage.py migrate --no-input
python manage.py collectstatic --no-input

sudo systemctl restart "$SERVICE_NAME"

echo "Deploy completado."
