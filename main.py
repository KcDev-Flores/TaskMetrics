"""
TaskMetrics CLI - Sistema de Control y Cálculo de Ingresos por Sprint
"""

import argparse
import os
import sys
from dotenv import load_dotenv

from src.database.sqlite import SQLiteMetricsRepository
from src.database.supabase import SupabaseMetricsRepository
from src.services.metrics_service import TaskMetricsService
from src.models.schemas import TaskItem

load_dotenv()


def get_service():
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_KEY")

    if supabase_url and supabase_key and "your-project-ref" not in supabase_url:
        try:
            repo = SupabaseMetricsRepository(url=supabase_url, key=supabase_key)
            return TaskMetricsService(repo)
        except Exception:
            return TaskMetricsService(SQLiteMetricsRepository())
    else:
        return TaskMetricsService(SQLiteMetricsRepository())


def main():
    parser = argparse.ArgumentParser(
        description="TaskMetrics: Sistema de Gestión de Sprints y Ponderación de Ingresos"
    )
    subparsers = parser.add_subparsers(dest="command", help="Comandos disponibles")

    # Comando: add-dev
    add_prog = subparsers.add_parser("add-dev", help="Registrar un integrante")
    add_prog.add_argument("name", type=str, help="Nombre del integrante")

    # Comando: delete-sprint
    del_sprint = subparsers.add_parser("delete-sprint", help="Eliminar un sprint y recalcular métricas")
    del_sprint.add_argument("sprint", type=int, help="Número de sprint a eliminar")

    # Comando: remove-dev
    rem_dev = subparsers.add_parser("remove-dev", help="Eliminar un integrante")
    rem_dev.add_argument("name", type=str, help="Nombre del integrante a eliminar")

    # Comando: report
    report_cmd = subparsers.add_parser("report", help="Mostrar tablero de rendimiento y porcentajes actuales")
    report_cmd.add_argument("--up-to", type=int, default=None, help="Filtrar métricas acumuladas hasta un sprint específico")
    report_cmd.add_argument("--export", type=str, default=None, help="Ruta de archivo para exportar (.csv o .md)")

    args = parser.parse_args()

    service = get_service()

    if not args.command or args.command == "report":
        up_to = getattr(args, "up_to", None)
        table_rendered = service.export_to_markdown_string(up_to_sprint=up_to)
        print("\n" + table_rendered)

        export_path = getattr(args, "export", None)
        if export_path:
            if export_path.lower().endswith(".csv"):
                content = service.export_to_csv_string(up_to_sprint=up_to)
            else:
                content = table_rendered
            with open(export_path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"\n[Éxito] Reporte exportado a: {export_path}")

    elif args.command == "add-dev":
        dev = service.register_programmer(args.name)
        print(f"[Éxito] Integrante '{dev.name}' registrado.")

    elif args.command == "remove-dev":
        success = service.remove_programmer(args.name)
        if success:
            print(f"[Éxito] Integrante '{args.name}' eliminado.")
            print("\nTablero actualizado:")
            print(service.export_to_markdown_string())
        else:
            print(f"[Aviso] No se encontró al integrante '{args.name}'.")

    elif args.command == "delete-sprint":
        success = service.delete_sprint(args.sprint)
        if success:
            print(f"[Éxito] Sprint {args.sprint} eliminado correctamente.")
            print("\nTablero actualizado:")
            print(service.export_to_markdown_string())
        else:
            print(f"[Aviso] No se encontró el Sprint {args.sprint}.")


if __name__ == "__main__":
    main()
