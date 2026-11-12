"""
TaskMetrics Web Runner
Ejecuta el servidor web y panel de control en http://127.0.0.1:8000
"""

import sys
import os

# Asegurar que el directorio raíz del proyecto esté en el PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import uvicorn
from src.core.config import Config
from src.web.app import create_app

app = create_app()

if __name__ == "__main__":
    print("=" * 70)
    print("🚀 INICIANDO TASKMETRICS WEB DASHBOARD")
    print("=" * 70)
    print(f" * Panel Web: http://{Config.HOST}:{Config.PORT}")
    print(f" * Documentación API: http://{Config.HOST}:{Config.PORT}/docs")
    if Config.is_supabase_configured():
        print(" * Base de Datos: Conectado a Supabase (Cloud PostgreSQL)")
    else:
        print(" * Base de Datos: Modo Memoria Local (Offline/Dev)")
    print("=" * 70)
    print("Presiona CTRL+C para detener el servidor.\n")

    uvicorn.run(
        "run:app",
        host=Config.HOST,
        port=Config.PORT,
        reload=False
    )

