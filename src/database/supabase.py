import os
from typing import Dict, List, Optional, Tuple
from src.models.schemas import Programmer, SprintDetail, TaskItem
from .base import BaseMetricsRepository


class SupabaseMetricsRepository(BaseMetricsRepository):
    """
    Repositorio persistente en la nube conectado con PostgreSQL en Supabase.
    Mapea a las tablas relacionales: programmers, sprints, tasks y task_assignments.
    """

    def __init__(self, url: Optional[str] = None, key: Optional[str] = None, auth_token: Optional[str] = None):
        from supabase import create_client, Client
        self.url = url or os.getenv("SUPABASE_URL")
        self.key = key or os.getenv("SUPABASE_KEY")
        if not self.url or not self.key or "your-project-ref" in self.url:
            raise ValueError(
                "Credenciales de Supabase no configuradas. "
                "Define SUPABASE_URL y SUPABASE_KEY en .env"
            )
        self.client: Client = create_client(self.url, self.key)
        if auth_token:
            self.set_auth_token(auth_token)

    def set_auth_token(self, token: Optional[str]) -> None:
        """Asigna el JWT del usuario autenticado para que PostgREST aplique las políticas RLS."""
        if token and hasattr(self, "client"):
            self.client.postgrest.auth(token)


    def add_programmer(self, name: str) -> Programmer:
        clean_name = name.strip()
        response = self.client.table("programmers").select("*").eq("name", clean_name).execute()
        if response.data and len(response.data) > 0:
            row = response.data[0]
            return Programmer(name=row["name"], id=str(row["id"]), active=row.get("active", True))

        insert_res = self.client.table("programmers").insert({"name": clean_name, "active": True}).execute()
        row = insert_res.data[0]
        return Programmer(name=row["name"], id=str(row["id"]), active=row.get("active", True))

    def update_programmer(self, old_name: str, new_name: str, active: bool = True) -> bool:
        res = self.client.table("programmers").update({
            "name": new_name.strip(),
            "active": active
        }).eq("name", old_name.strip()).execute()
        return bool(res.data and len(res.data) > 0)

    def remove_programmer(self, name: str) -> bool:
        res = self.client.table("programmers").delete().eq("name", name.strip()).execute()
        return bool(res.data and len(res.data) > 0)

    def get_programmers(self, active_only: bool = True) -> List[Programmer]:
        query = self.client.table("programmers").select("*")
        if active_only:
            query = query.eq("active", True)
        res = query.order("name").execute()
        return [
            Programmer(name=row["name"], id=str(row["id"]), active=row.get("active", True))
            for row in res.data
        ]

    def save_sprint_with_tasks(
        self,
        sprint_number: int,
        name: str,
        status: str,
        tasks: List[TaskItem]
    ) -> SprintDetail:
        # 1. Obtener o insertar sprint
        s_res = self.client.table("sprints").select("*").eq("sprint_number", sprint_number).execute()
        if s_res.data and len(s_res.data) > 0:
            sprint_id = s_res.data[0]["id"]
            self.client.table("sprints").update({"name": name, "status": status}).eq("id", sprint_id).execute()
            # Eliminar tareas anteriores en cascada
            self.client.table("tasks").delete().eq("sprint_id", sprint_id).execute()
        else:
            ins = self.client.table("sprints").insert({
                "sprint_number": sprint_number,
                "name": name,
                "status": status
            }).execute()
            sprint_id = ins.data[0]["id"]

        # 2. Insertar tareas y asignaciones
        created_tasks: List[TaskItem] = []
        for t in tasks:
            t_status = t.status if t.status in ["completed", "in_progress"] else "completed"
            t_ins = self.client.table("tasks").insert({
                "sprint_id": sprint_id,
                "title": t.title,
                "status": t_status
            }).execute()
            task_id = t_ins.data[0]["id"]

            assigned_names = []
            for dev_name in t.assigned_programmers:
                prog = self.add_programmer(dev_name)
                self.client.table("task_assignments").insert({
                    "task_id": task_id,
                    "programmer_id": prog.id,
                    "completed": (t_status == "completed")
                }).execute()
                assigned_names.append(prog.name)

            created_tasks.append(TaskItem(
                id=task_id,
                sprint_id=sprint_id,
                title=t.title,
                status=t_status,
                assigned_programmers=assigned_names
            ))

        return SprintDetail(
            id=sprint_id,
            sprint_number=sprint_number,
            name=name,
            status=status,
            tasks=created_tasks
        )

    def get_sprints(self) -> List[dict]:
        res = self.client.table("sprints").select("id, sprint_number, name, status, tasks(id)").order("sprint_number").execute()
        result = []
        for r in res.data:
            result.append({
                "id": r["id"],
                "sprint_number": r["sprint_number"],
                "name": r["name"],
                "status": r["status"],
                "task_count": len(r.get("tasks", []))
            })
        return result

    def get_sprint_detail(self, sprint_number: int) -> Optional[SprintDetail]:
        s_res = self.client.table("sprints").select("*").eq("sprint_number", sprint_number).execute()
        if not s_res.data:
            return None
        s_row = s_res.data[0]
        sprint_id = s_row["id"]

        t_res = self.client.table("tasks").select("*, task_assignments(programmer_id, programmers(name))").eq("sprint_id", sprint_id).execute()
        tasks = []
        for tr in t_res.data:
            dev_names = []
            for ta in tr.get("task_assignments", []):
                p_info = ta.get("programmers")
                if p_info:
                    dev_names.append(p_info["name"])
            tasks.append(TaskItem(
                id=tr["id"],
                sprint_id=sprint_id,
                title=tr["title"],
                status=tr["status"],
                assigned_programmers=dev_names
            ))

        return SprintDetail(
            id=sprint_id,
            sprint_number=s_row["sprint_number"],
            name=s_row["name"],
            status=s_row["status"],
            tasks=tasks
        )

    def delete_sprint(self, sprint_number: int) -> bool:
        res = self.client.table("sprints").delete().eq("sprint_number", sprint_number).execute()
        return bool(res.data and len(res.data) > 0)

    def get_matrix_data(self) -> Tuple[List[int], Dict[int, str], Dict[str, Dict[int, int]], Dict[str, Dict[int, int]], List[str]]:
        progs = [p.name for p in self.get_programmers(active_only=True)]
        sprints_info = self.get_sprints()
        sprints = [s["sprint_number"] for s in sprints_info]
        sprint_names = {s["sprint_number"]: s["name"] for s in sprints_info}

        completed_data: Dict[str, Dict[int, int]] = {p: {} for p in progs}
        assigned_data: Dict[str, Dict[int, int]] = {p: {} for p in progs}

        # Consulta todas las asignaciones
        res = self.client.table("task_assignments").select("completed, programmers(name), tasks(status, sprints(sprint_number))").execute()
        for row in res.data:
            p_name = row.get("programmers", {}).get("name")
            t_info = row.get("tasks", {})
            s_num = t_info.get("sprints", {}).get("sprint_number") if t_info.get("sprints") else None

            if p_name and s_num and p_name in completed_data:
                is_comp = (t_info.get("status") == "completed" and row.get("completed", True))
                completed_data[p_name][s_num] = completed_data[p_name].get(s_num, 0) + (1 if is_comp else 0)
                assigned_data[p_name][s_num] = assigned_data[p_name].get(s_num, 0) + 1

        return sprints, sprint_names, completed_data, assigned_data, progs

    def get_programmer_history(self, name: str) -> Optional[dict]:
        clean_name = name.strip()
        p_res = self.client.table("programmers").select("*").eq("name", clean_name).execute()
        if not p_res.data:
            return None
        p_row = p_res.data[0]
        p_id = p_row["id"]

        assign_res = self.client.table("task_assignments").select(
            "task_id, completed, tasks(id, title, status, sprints(sprint_number, name, status))"
        ).eq("programmer_id", p_id).execute()

        sprints_map = {}
        total_completed = 0
        total_assigned = len(assign_res.data)

        for item in assign_res.data:
            t = item.get("tasks")
            if not t:
                continue
            s = t.get("sprints")
            if not s:
                continue

            s_num = s["sprint_number"]
            if s_num not in sprints_map:
                sprints_map[s_num] = {
                    "sprint_number": s_num,
                    "sprint_name": s["name"],
                    "sprint_status": s["status"],
                    "tasks": []
                }

            # Buscar compañeros en esa tarea
            co_res = self.client.table("task_assignments").select("programmers(name)").eq("task_id", t["id"]).neq("programmer_id", p_id).execute()
            co_workers = [c["programmers"]["name"] for c in co_res.data if c.get("programmers")]

            is_comp = bool(t.get("status") == "completed" and item.get("completed", True))
            if is_comp:
                total_completed += 1

            sprints_map[s_num]["tasks"].append({
                "title": t["title"],
                "status": t["status"],
                "completed": is_comp,
                "co_workers": co_workers
            })

        return {
            "name": p_row["name"],
            "active": p_row.get("active", True),
            "total_completed": total_completed,
            "total_assigned": total_assigned,
            "sprints": list(sprints_map.values())
        }
