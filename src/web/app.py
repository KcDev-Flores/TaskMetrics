import html
import logging
import os
from typing import Optional
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from src.core.auth import auth_service, get_current_user, get_optional_user, require_admin
from src.core.config import Config
from src.database.sqlite import SQLiteMetricsRepository
from src.database.supabase import SupabaseMetricsRepository
from src.services.metrics_service import TaskMetricsService
from src.models.schemas import (
    ProgrammerCreate,
    ProgrammerUpdate,
    SprintCreateRequest,
    SprintUpdateRequest,
    TaskItem,
    UserCredentials,
    TokenRefreshRequest,
    UserCreateAdmin,
    UserUpdateAdmin,
)

logger = logging.getLogger("taskmetrics")


def create_app() -> FastAPI:
    app = FastAPI(
        title="TaskMetrics API",
        description="Sistema de Registro, Gestión de Sprints y Ponderación de Ingresos con Supabase Auth",
        version="2.2.0"
    )

    def known_areas() -> list:
        """Áreas configuradas más las que ya tengan datos en el modo local."""
        areas = list(Config.AREAS)
        if not auth_service.is_configured:
            areas += [a for a in auth_service.local.list_areas() if a not in areas]
        return areas

    def resolve_area(current_user: dict, requested: Optional[str]) -> str:
        """Un líder siempre opera sobre su área; el admin elige cuál consultar."""
        if current_user.get("role") != "admin":
            area = current_user.get("area")
            if not area:
                raise HTTPException(
                    status_code=403,
                    detail="Tu usuario no tiene un área asignada. Pide al administrador que la configure."
                )
            return area

        areas = known_areas()
        area = (requested or "").strip().lower() or (areas[0] if areas else "")
        if area not in areas:
            raise HTTPException(status_code=400, detail=f"Área desconocida: '{requested}'.")
        return area

    def get_service(current_user: dict, requested_area: Optional[str] = None) -> TaskMetricsService:
        area = resolve_area(current_user, requested_area)
        if auth_service.is_configured:
            return TaskMetricsService(SupabaseMetricsRepository(auth_service.db, area))
        return TaskMetricsService(SQLiteMetricsRepository(area=area))

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception):
        logger.exception("Error no controlado en %s %s", request.method, request.url.path)
        detail = "Error interno del servidor."
        if auth_service.is_configured:
            from postgrest.exceptions import APIError

            if isinstance(exc, APIError):
                detail = f"Supabase rechazó la operación: {exc.message}"
                if exc.code in ("PGRST205", "PGRST204", "42P01", "42703"):
                    detail += " Ejecuta database/schema.sql en el SQL Editor de Supabase."
            else:
                detail = f"No se pudo completar la operación con Supabase: {exc}"
        return JSONResponse(status_code=502 if auth_service.is_configured else 500, content={"detail": detail})

    current_dir = os.path.dirname(os.path.abspath(__file__))
    static_dir = os.path.join(current_dir, "static")
    templates_dir = os.path.join(current_dir, "templates")

    if os.path.exists(static_dir):
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

    # -------------------------------------------------------------------------
    # Frontend HTML
    # -------------------------------------------------------------------------
    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        html_file = os.path.join(templates_dir, "index.html")
        if os.path.exists(html_file):
            with open(html_file, "r", encoding="utf-8") as f:
                return f.read().replace("{{STUDIO_NAME}}", html.escape(Config.STUDIO_NAME))
        return "<h1>TaskMetrics</h1><p>Archivo index.html no encontrado.</p>"

    # -------------------------------------------------------------------------
    # API Autenticación Supabase
    # -------------------------------------------------------------------------
    @app.post("/api/auth/login")
    async def login_user(payload: UserCredentials):
        try:
            return auth_service.sign_in(payload.email, payload.password)
        except ValueError as e:
            raise HTTPException(status_code=401, detail=str(e))

    @app.post("/api/auth/refresh")
    async def refresh_user_token(payload: TokenRefreshRequest):
        try:
            return auth_service.refresh_session(payload.refresh_token)
        except ValueError as e:
            raise HTTPException(status_code=401, detail=str(e))

    @app.post("/api/auth/logout")
    async def logout_user(current_user: Optional[dict] = Depends(get_optional_user)):
        token = current_user.get("token") if current_user else None
        auth_service.sign_out(token)
        return {"status": "success", "message": "Sesión cerrada correctamente."}

    @app.get("/api/auth/me")
    async def get_me(current_user: dict = Depends(get_current_user)):
        return {
            "status": "success",
            "user": {k: v for k, v in current_user.items() if k != "token"}
        }

    @app.get("/api/auth/status")
    async def get_auth_status():
        return {
            "supabase_configured": auth_service.is_configured,
            "studio_name": Config.STUDIO_NAME,
        }

    @app.get("/api/areas")
    async def list_areas(current_user: dict = Depends(get_current_user)):
        """Áreas que el usuario puede consultar: todas para el admin, la propia para un líder."""
        if current_user.get("role") == "admin":
            return {"areas": known_areas(), "assignable": Config.AREAS}
        return {"areas": [resolve_area(current_user, None)], "assignable": []}

    # -------------------------------------------------------------------------
    # API Administración de Usuarios (Exclusivo Administrador)
    # -------------------------------------------------------------------------
    @app.get("/api/admin/users")
    async def list_system_users(admin: dict = Depends(require_admin)):
        return auth_service.list_users()

    @app.post("/api/admin/users")
    async def create_system_user(payload: UserCreateAdmin, admin: dict = Depends(require_admin)):
        try:
            return auth_service.create_user(
                email=payload.email,
                password=payload.password,
                name=payload.name,
                role=payload.role,
                area=payload.area
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.put("/api/admin/users/{user_id}")
    async def update_system_user(user_id: str, payload: UserUpdateAdmin, admin: dict = Depends(require_admin)):
        try:
            success = auth_service.update_user(
                user_id=user_id,
                acting_user_id=admin["id"],
                name=payload.name,
                role=payload.role,
                area=payload.area,
                active=payload.active,
                password=payload.password
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        if not success:
            raise HTTPException(status_code=404, detail="Usuario no encontrado.")
        return {"status": "success", "message": "Usuario actualizado correctamente."}

    @app.delete("/api/admin/users/{user_id}")
    async def delete_system_user(user_id: str, admin: dict = Depends(require_admin)):
        if user_id == admin["id"]:
            raise HTTPException(status_code=400, detail="No puedes eliminar tu propia cuenta de administrador.")
        try:
            success = auth_service.delete_user(user_id)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        if not success:
            raise HTTPException(status_code=404, detail="Usuario no encontrado.")
        return {"status": "success", "message": "Usuario eliminado correctamente."}


    # -------------------------------------------------------------------------
    # API Métricas y Tablero (Rutas Protegidas)
    # -------------------------------------------------------------------------
    @app.get("/api/metrics")
    async def get_metrics(
        up_to: Optional[int] = None,
        area: Optional[str] = None,
        current_user: dict = Depends(get_current_user)
    ):
        service = get_service(current_user, area)
        matrix = service.get_metrics_matrix(
            precision_decimals=Config.DEFAULT_PRECISION,
            up_to_sprint=up_to
        )
        progs = [p.name for p in service.get_programmers(active_only=True)]

        return {
            "area": service.repository.area,
            "sprints": matrix.sprints,
            "sprint_names": matrix.sprint_names,
            "programmers": progs,
            "matrix": [
                {
                    "programmer_name": m.programmer_name,
                    "sprint_tasks": m.sprint_tasks,
                    "total_accumulated": m.total_accumulated,
                    "total_assigned": m.total_assigned,
                    "percentage": m.percentage,
                    "completion_rate": m.completion_rate,
                }
                for m in matrix.programmer_metrics
            ],
            "team_total_tasks": matrix.team_total_tasks,
            "team_total_assigned": matrix.team_total_assigned,
            "overall_completion_rate": matrix.overall_completion_rate,
            "sprint_totals": matrix.sprint_totals,
        }

    # -------------------------------------------------------------------------
    # API Sprints y Tareas (Rutas Protegidas)
    # -------------------------------------------------------------------------
    @app.get("/api/sprints")
    async def list_sprints(area: Optional[str] = None, current_user: dict = Depends(get_current_user)):
        service = get_service(current_user, area)
        return service.get_sprints_list()

    @app.get("/api/sprints/{sprint_number}")
    async def get_sprint_detail(
        sprint_number: int,
        area: Optional[str] = None,
        current_user: dict = Depends(get_current_user)
    ):
        service = get_service(current_user, area)
        detail = service.get_sprint_detail(sprint_number)
        if not detail:
            raise HTTPException(status_code=404, detail=f"Sprint {sprint_number} no encontrado.")
        return {
            "sprint_number": detail.sprint_number,
            "name": detail.name,
            "status": detail.status,
            "tasks": [
                {
                    "title": t.title,
                    "status": t.status,
                    "assigned_programmers": t.assigned_programmers
                }
                for t in detail.tasks
            ]
        }

    @app.post("/api/sprints")
    async def create_sprint(
        payload: SprintCreateRequest,
        area: Optional[str] = None,
        current_user: dict = Depends(get_current_user)
    ):
        service = get_service(current_user, area)
        tasks = [
            TaskItem(
                title=t.title.strip(),
                status=t.status,
                assigned_programmers=t.assigned_programmers
            )
            for t in payload.tasks
        ]
        sprint = service.save_sprint_with_tasks(
            sprint_number=payload.sprint_number,
            name=payload.name,
            status=payload.status,
            tasks=tasks
        )
        return {"status": "success", "sprint_number": sprint.sprint_number, "name": sprint.name}

    @app.put("/api/sprints/{sprint_number}")
    async def update_sprint(
        sprint_number: int,
        payload: SprintUpdateRequest,
        area: Optional[str] = None,
        current_user: dict = Depends(get_current_user)
    ):
        service = get_service(current_user, area)
        tasks = [
            TaskItem(
                title=t.title.strip(),
                status=t.status,
                assigned_programmers=t.assigned_programmers
            )
            for t in payload.tasks
        ]
        sprint = service.save_sprint_with_tasks(
            sprint_number=sprint_number,
            name=payload.name,
            status=payload.status,
            tasks=tasks
        )
        return {"status": "success", "sprint_number": sprint.sprint_number, "name": sprint.name}

    @app.delete("/api/sprints/{sprint_number}")
    async def delete_sprint(
        sprint_number: int,
        area: Optional[str] = None,
        current_user: dict = Depends(get_current_user)
    ):
        service = get_service(current_user, area)
        success = service.delete_sprint(sprint_number)
        if not success:
            raise HTTPException(status_code=404, detail=f"Sprint {sprint_number} no encontrado.")
        return {"status": "success", "message": f"Sprint {sprint_number} eliminado correctamente."}

    # -------------------------------------------------------------------------
    # API Integrantes (Rutas Protegidas)
    # -------------------------------------------------------------------------
    @app.get("/api/programmers")
    async def list_programmers(area: Optional[str] = None, current_user: dict = Depends(get_current_user)):
        service = get_service(current_user, area)
        progs = service.get_programmers(active_only=False)
        return [{"id": p.id, "name": p.name, "active": p.active} for p in progs]

    @app.get("/api/programmers/{name}/history")
    async def get_programmer_history(
        name: str,
        area: Optional[str] = None,
        current_user: dict = Depends(get_current_user)
    ):
        service = get_service(current_user, area)
        history = service.get_programmer_history(name)
        if not history:
            raise HTTPException(status_code=404, detail=f"Integrante '{name}' no encontrado.")
        return history

    @app.post("/api/programmers")
    async def add_programmer(
        payload: ProgrammerCreate,
        area: Optional[str] = None,
        current_user: dict = Depends(get_current_user)
    ):
        service = get_service(current_user, area)
        prog = service.register_programmer(payload.name)
        return {"status": "success", "programmer": {"name": prog.name}}

    @app.put("/api/programmers")
    async def update_programmer(
        payload: ProgrammerUpdate,
        area: Optional[str] = None,
        current_user: dict = Depends(get_current_user)
    ):
        service = get_service(current_user, area)
        success = service.update_programmer(
            old_name=payload.old_name,
            new_name=payload.new_name,
            active=payload.active if payload.active is not None else True
        )
        if not success:
            raise HTTPException(status_code=404, detail=f"Integrante '{payload.old_name}' no encontrado.")
        return {"status": "success", "message": f"Integrante '{payload.new_name}' actualizado."}

    @app.delete("/api/programmers/{name}")
    async def remove_programmer(
        name: str,
        area: Optional[str] = None,
        current_user: dict = Depends(get_current_user)
    ):
        service = get_service(current_user, area)
        success = service.remove_programmer(name)
        if not success:
            raise HTTPException(status_code=404, detail=f"Integrante '{name}' no encontrado.")
        return {"status": "success", "message": f"Integrante '{name}' eliminado."}

    # -------------------------------------------------------------------------
    # Exportación (Ruta Protegida)
    # -------------------------------------------------------------------------
    @app.get("/api/export")
    async def export_data(
        format: str = "csv",
        up_to: Optional[int] = None,
        area: Optional[str] = None,
        current_user: dict = Depends(get_current_user)
    ):
        service = get_service(current_user, area)
        if format.lower() == "md":
            content = service.export_to_markdown_string(up_to_sprint=up_to)
            return PlainTextResponse(
                content,
                media_type="text/markdown",
                headers={"Content-Disposition": "attachment; filename=taskmetrics_rendimiento.md"}
            )
        else:
            content = service.export_to_csv_string(up_to_sprint=up_to)
            return Response(
                content,
                media_type="text/csv",
                headers={"Content-Disposition": "attachment; filename=taskmetrics_rendimiento.csv"}
            )

    return app
