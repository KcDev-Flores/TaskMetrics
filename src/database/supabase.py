from typing import Any, Dict, List, Optional, Tuple

from src.models.schemas import Programmer, SprintDetail, TaskItem
from .base import BaseMetricsRepository

PAGE_SIZE = 1000


class SupabaseMetricsRepository(BaseMetricsRepository):
    """
    Repositorio en la nube sobre PostgreSQL de Supabase (tablas programmers, sprints,
    tasks y task_assignments). Cada instancia opera sobre una sola área.

    Recibe un cliente creado con la llave service_role: el aislamiento entre áreas
    lo aplica este backend, y RLS deja sin acceso a las llaves públicas.
    """

    def __init__(self, client: Any, area: str):
        if not area:
            raise ValueError("El repositorio de Supabase requiere un área.")
        self.client = client
        self.area = area.strip().lower()

    def _fetch_all(self, build_query) -> List[dict]:
        """Recorre todas las páginas: PostgREST devuelve como máximo 1000 filas por petición."""
        rows: List[dict] = []
        start = 0
        while True:
            page = build_query().range(start, start + PAGE_SIZE - 1).execute().data or []
            rows.extend(page)
            if len(page) < PAGE_SIZE:
                return rows
            start += PAGE_SIZE

    def _find_programmer(self, name: str) -> Optional[dict]:
        """Busca por nombre dentro del área sin distinguir mayúsculas."""
        wanted = name.strip().casefold()
        rows = self._fetch_all(
            lambda: self.client.table("programmers").select("*").eq("area", self.area).order("name")
        )
        return next((r for r in rows if r["name"].casefold() == wanted), None)

    def _find_sprint(self, sprint_number: int) -> Optional[dict]:
        res = (
            self.client.table("sprints").select("*")
            .eq("area", self.area).eq("sprint_number", sprint_number)
            .limit(1).execute()
        )
        return res.data[0] if res.data else None

    @staticmethod
    def _to_programmer(row: dict) -> Programmer:
        return Programmer(name=row["name"], id=str(row["id"]), active=row.get("active", True))

    # -------------------------------------------------------------------------
    # Integrantes
    # -------------------------------------------------------------------------
    def add_programmer(self, name: str) -> Programmer:
        existing = self._find_programmer(name)
        if existing:
            return self._to_programmer(existing)
        res = self.client.table("programmers").insert(
            {"area": self.area, "name": name.strip(), "active": True}
        ).execute()
        return self._to_programmer(res.data[0])

    def update_programmer(self, old_name: str, new_name: str, active: bool = True) -> bool:
        existing = self._find_programmer(old_name)
        if not existing:
            return False
        self.client.table("programmers").update(
            {"name": new_name.strip(), "active": active}
        ).eq("id", existing["id"]).execute()
        return True

    def remove_programmer(self, name: str) -> bool:
        existing = self._find_programmer(name)
        if not existing:
            return False
        self.client.table("programmers").delete().eq("id", existing["id"]).execute()
        return True

    def get_programmers(self, active_only: bool = True) -> List[Programmer]:
        def query():
            q = self.client.table("programmers").select("*").eq("area", self.area)
            if active_only:
                q = q.eq("active", True)
            return q.order("name")

        return [self._to_programmer(row) for row in self._fetch_all(query)]

    # -------------------------------------------------------------------------
    # Sprints y tareas
    # -------------------------------------------------------------------------
    def save_sprint_with_tasks(
        self,
        sprint_number: int,
        name: str,
        status: str,
        tasks: List[TaskItem]
    ) -> SprintDetail:
        sprint = self._find_sprint(sprint_number)
        if sprint:
            sprint_id = sprint["id"]
            self.client.table("sprints").update({"name": name, "status": status}).eq("id", sprint_id).execute()
            # Las asignaciones se eliminan en cascada junto con las tareas
            self.client.table("tasks").delete().eq("sprint_id", sprint_id).execute()
        else:
            ins = self.client.table("sprints").insert({
                "area": self.area,
                "sprint_number": sprint_number,
                "name": name,
                "status": status
            }).execute()
            sprint_id = ins.data[0]["id"]

        created_tasks: List[TaskItem] = []
        for t in tasks:
            t_status = t.status if t.status in ["completed", "in_progress"] else "completed"
            t_ins = self.client.table("tasks").insert({
                "sprint_id": sprint_id,
                "title": t.title,
                "status": t_status
            }).execute()
            task_id = t_ins.data[0]["id"]

            assigned: Dict[str, str] = {}
            for dev_name in t.assigned_programmers:
                prog = self.add_programmer(dev_name)
                assigned[prog.id] = prog.name
            if assigned:
                self.client.table("task_assignments").insert([
                    {"task_id": task_id, "programmer_id": p_id, "completed": t_status == "completed"}
                    for p_id in assigned
                ]).execute()

            created_tasks.append(TaskItem(
                id=task_id,
                sprint_id=sprint_id,
                title=t.title,
                status=t_status,
                assigned_programmers=list(assigned.values())
            ))

        return SprintDetail(
            id=sprint_id,
            sprint_number=sprint_number,
            name=name,
            status=status,
            tasks=created_tasks
        )

    def get_sprints(self) -> List[dict]:
        rows = self._fetch_all(
            lambda: self.client.table("sprints")
            .select("id, sprint_number, name, status, tasks(id)")
            .eq("area", self.area).order("sprint_number")
        )
        return [
            {
                "id": r["id"],
                "sprint_number": r["sprint_number"],
                "name": r["name"],
                "status": r["status"],
                "task_count": len(r.get("tasks") or [])
            }
            for r in rows
        ]

    def get_sprint_detail(self, sprint_number: int) -> Optional[SprintDetail]:
        sprint = self._find_sprint(sprint_number)
        if not sprint:
            return None
        sprint_id = sprint["id"]

        task_rows = self._fetch_all(
            lambda: self.client.table("tasks")
            .select("*, task_assignments(programmer_id, programmers(name))")
            .eq("sprint_id", sprint_id).order("created_at")
        )
        tasks = [
            TaskItem(
                id=tr["id"],
                sprint_id=sprint_id,
                title=tr["title"],
                status=tr["status"],
                assigned_programmers=sorted(
                    ta["programmers"]["name"]
                    for ta in tr.get("task_assignments") or []
                    if ta.get("programmers")
                )
            )
            for tr in task_rows
        ]

        return SprintDetail(
            id=sprint_id,
            sprint_number=sprint["sprint_number"],
            name=sprint["name"],
            status=sprint["status"],
            tasks=tasks
        )

    def delete_sprint(self, sprint_number: int) -> bool:
        sprint = self._find_sprint(sprint_number)
        if not sprint:
            return False
        self.client.table("sprints").delete().eq("id", sprint["id"]).execute()
        return True

    # -------------------------------------------------------------------------
    # Métricas
    # -------------------------------------------------------------------------
    def _area_assignments(self, programmer_id: Optional[str] = None) -> List[dict]:
        def query():
            q = (
                self.client.table("task_assignments")
                .select(
                    "id, task_id, completed, programmer_id, programmers!inner(name), "
                    "tasks!inner(id, title, status, created_at, "
                    "sprints!inner(sprint_number, name, status, area))"
                )
                .eq("tasks.sprints.area", self.area)
            )
            if programmer_id:
                q = q.eq("programmer_id", programmer_id)
            return q.order("id")

        return self._fetch_all(query)

    def get_matrix_data(self) -> Tuple[List[int], Dict[int, str], Dict[str, Dict[int, int]], Dict[str, Dict[int, int]], List[str]]:
        progs = [p.name for p in self.get_programmers(active_only=True)]
        sprints_info = self.get_sprints()
        sprints = [s["sprint_number"] for s in sprints_info]
        sprint_names = {s["sprint_number"]: s["name"] for s in sprints_info}

        completed_data: Dict[str, Dict[int, int]] = {p: {} for p in progs}
        assigned_data: Dict[str, Dict[int, int]] = {p: {} for p in progs}

        for row in self._area_assignments():
            p_name = row["programmers"]["name"]
            if p_name not in completed_data:
                continue
            task = row["tasks"]
            s_num = task["sprints"]["sprint_number"]
            is_comp = task["status"] == "completed" and row.get("completed", True)
            completed_data[p_name][s_num] = completed_data[p_name].get(s_num, 0) + (1 if is_comp else 0)
            assigned_data[p_name][s_num] = assigned_data[p_name].get(s_num, 0) + 1

        return sprints, sprint_names, completed_data, assigned_data, progs

    def get_programmer_history(self, name: str) -> Optional[dict]:
        programmer = self._find_programmer(name)
        if not programmer:
            return None
        p_id = programmer["id"]

        own = self._area_assignments(programmer_id=p_id)
        own.sort(key=lambda r: (r["tasks"]["sprints"]["sprint_number"], r["tasks"]["created_at"]))

        co_workers: Dict[str, List[str]] = {}
        task_ids = [r["task_id"] for r in own]
        for i in range(0, len(task_ids), 100):
            chunk = task_ids[i:i + 100]
            others = self._fetch_all(
                lambda: self.client.table("task_assignments")
                .select("id, task_id, programmers(name)")
                .in_("task_id", chunk).neq("programmer_id", p_id).order("id")
            )
            for o in others:
                if o.get("programmers"):
                    co_workers.setdefault(o["task_id"], []).append(o["programmers"]["name"])

        sprints_map: Dict[int, dict] = {}
        total_completed = 0
        for item in own:
            task = item["tasks"]
            sprint = task["sprints"]
            s_num = sprint["sprint_number"]
            entry = sprints_map.setdefault(s_num, {
                "sprint_number": s_num,
                "sprint_name": sprint["name"],
                "sprint_status": sprint["status"],
                "tasks": []
            })
            is_comp = bool(task["status"] == "completed" and item.get("completed", True))
            total_completed += 1 if is_comp else 0
            entry["tasks"].append({
                "title": task["title"],
                "status": task["status"],
                "completed": is_comp,
                "co_workers": sorted(co_workers.get(item["task_id"], []))
            })

        return {
            "name": programmer["name"],
            "active": programmer.get("active", True),
            "total_completed": total_completed,
            "total_assigned": len(own),
            "sprints": list(sprints_map.values())
        }

