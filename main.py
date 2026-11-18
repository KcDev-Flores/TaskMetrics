"""
TaskMetrics CLI - Sistema de Control y Cálculo de Ingresos por Sprint
"""

import argparse

from src.core.config import Config
from src.database.sqlite import SQLiteMetricsRepository
from src.database.supabase import SupabaseMetricsRepository
from src.services.metrics_service import TaskMetricsService


def get_service(area: str) -> TaskMetricsService:
    if Config.is_supabase_configured():
        from supabase import create_client

        client = create_client(Config.SUPABASE_URL, Config.SUPABASE_SERVICE_ROLE_KEY)
        return TaskMetricsService(SupabaseMetricsRepository(client, area))
    return TaskMetricsService(SQLiteMetricsRepository(area=area))


def main():
    parser = argparse.ArgumentParser(
        description="TaskMetrics: Sistema de Gestión de Sprints y Ponderación de Ingresos"
    )
    parser.add_argument(
        "--area", type=str, default=Config.AREAS[0],
        help=f"Área sobre la que se opera ({', '.join(Config.AREAS)})"
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

    # Comando: create-user
    new_user = subparsers.add_parser(
        "create-user",
        help="Crear una cuenta (sirve para dar de alta al primer administrador)"
    )
    new_user.add_argument("username", type=str, help="Nombre de usuario para iniciar sesión")
    new_user.add_argument("name", type=str, help="Nombre visible")
    new_user.add_argument("--role", choices=["admin", "lider"], default="lider")
    new_user.add_argument("--password", type=str, default=None, help="Si se omite, se pide por teclado")

    args = parser.parse_args()

    if args.command == "create-user":
        from getpass import getpass
        from src.services.auth_service import SupabaseAuthService

        password = args.password or getpass("Contraseña: ")
        try:
            result = SupabaseAuthService().create_user(
                username=args.username,
                password=password,
                name=args.name,
                role=args.role,
                area=args.area if args.role == "lider" else None,
            )
        except ValueError as e:
            parser.exit(1, f"[Error] {e}\n")
        print(f"[Éxito] {result['message']}")
        return

    service = get_service(args.area.strip().lower())

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
