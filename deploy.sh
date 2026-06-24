#!/bin/bash
set -e

# Ajustar estas variables según el entorno
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$PROJECT_DIR/venv"
SERVICE_NAME="civil-web"

cd "$PROJECT_DIR"

git pull

source "$VENV_DIR/bin/activate"

pip install -r requirements.txt --quiet

python manage.py migrate --no-input
python manage.py collectstatic --no-input

sudo systemctl restart "$SERVICE_NAME"

echo "Deploy completado."
