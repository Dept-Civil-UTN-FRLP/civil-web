@echo off
title Servidor de desarrollo Django
echo ===========================================
echo   Iniciando servidor de desarrollo Django
echo ===========================================

REM Activar entorno virtual (ajustar ruta si es distinto)
call venv\Scripts\activate

REM Iniciar el servidor en una ventana separada
start "Servidor Django" cmd /k "python manage.py runserver"
start http://127.0.0.1:8000/


echo.
echo El servidor se está ejecutando.
echo Presiona cualquier tecla para detenerlo...
pause >nul

echo.
echo Deteniendo servidor...
taskkill /FI "WINDOWTITLE eq Servidor Django" /T /F

echo Servidor detenido.
pause
