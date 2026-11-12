@echo off
title TaskMetrics Web Server
echo ========================================================
echo  Iniciando TaskMetrics en http://127.0.0.1:8000
echo ========================================================
".venv\Scripts\python.exe" run.py
if errorlevel 1 (
    echo.
    echo Hubo un error al iniciar el servidor.
    pause
)

