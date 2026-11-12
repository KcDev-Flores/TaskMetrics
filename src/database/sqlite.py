from contextlib import contextmanager
import os
import sqlite3
from typing import Dict, List, Optional, Tuple
from uuid import uuid4

from src.models.schemas import Programmer, SprintDetail, TaskItem
from .base import BaseMetricsRepository


class SQLiteMetricsRepository(BaseMetricsRepository):
    """
    Repositorio persistente no volátil utilizando SQLite (PostgreSQL-compatible DDL local).
    Garantiza que la información nunca se pierda entre reinicios.
    """

    def __init__(self, db_path: Optional[str] = None):
        if not db_path:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            db_dir = os.path.join(base_dir, "database")
            os.makedirs(db_dir, exist_ok=True)
            self.db_path = os.path.join(db_dir, "taskmetrics.db")
        else:
            self.db_path = db_path

        self._init_db()

    @contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self):
        with self._get_connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS programmers (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS sprints (
                    id TEXT PRIMARY KEY,
                    sprint_number INTEGER NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'completed',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    sprint_id TEXT NOT NULL REFERENCES sprints(id) ON DELETE CASCADE,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'completed',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS task_assignments (
                    id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
                    programmer_id TEXT NOT NULL REFERENCES programmers(id) ON DELETE CASCADE,
                    completed INTEGER NOT NULL DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(task_id, programmer_id)
                );

                CREATE TABLE IF NOT EXISTS user_profiles (
                    id TEXT PRIMARY KEY,
                    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    name TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'lider',
                    password TEXT NOT NULL DEFAULT '',
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # Sembrar admin inicial por defecto si la tabla está vacía
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) as count FROM user_profiles")
            if cur.fetchone()["count"] == 0:
                cur.execute(
                    "INSERT INTO user_profiles (id, email, name, role, password, active) VALUES (?, ?, ?, ?, ?, ?)",
                    (str(uuid4()), "admin@taskmetrics.com", "Administrador Principal", "admin", "admin123", 1)
                )
                conn.commit()

    def add_programmer(self, name: str) -> Programmer:
        clean_name = name.strip()
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT id, name, active FROM programmers WHERE name = ?", (clean_name,))
            row = cur.fetchone()
            if row:
                return Programmer(id=row["id"], name=row["name"], active=bool(row["active"]))

            new_id = str(uuid4())
            cur.execute("INSERT INTO programmers (id, name, active) VALUES (?, ?, 1)", (new_id, clean_name))
            conn.commit()
            return Programmer(id=new_id, name=clean_name, active=True)

    def update_programmer(self, old_name: str, new_name: str, active: bool = True) -> bool:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE programmers SET name = ?, active = ? WHERE name = ?",
                (new_name.strip(), 1 if active else 0, old_name.strip())
            )
            conn.commit()
            return cur.rowcount > 0

    def remove_programmer(self, name: str) -> bool:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM programmers WHERE name = ?", (name.strip(),))
            conn.commit()
            return cur.rowcount > 0

    def get_programmers(self, active_only: bool = True) -> List[Programmer]:
        with self._get_connection() as conn:
            cur = conn.cursor()
            if active_only:
                cur.execute("SELECT id, name, active FROM programmers WHERE active = 1 ORDER BY name ASC")
            else:
                cur.execute("SELECT id, name, active FROM programmers ORDER BY name ASC")
            rows = cur.fetchall()
            return [Programmer(id=r["id"], name=r["name"], active=bool(r["active"])) for r in rows]

    def save_sprint_with_tasks(
        self,
        sprint_number: int,
        name: str,
        status: str,
        tasks: List[TaskItem]
    ) -> SprintDetail:
        with self._get_connection() as conn:
            cur = conn.cursor()
            # 1. Obtener o crear sprint
            cur.execute("SELECT id FROM sprints WHERE sprint_number = ?", (sprint_number,))
            row = cur.fetchone()
            if row:
                sprint_id = row["id"]
                cur.execute("UPDATE sprints SET name = ?, status = ? WHERE id = ?", (name, status, sprint_id))
                # Limpiar tareas anteriores para sobreescribir limpiamente (cascada elimina asignaciones)
                cur.execute("DELETE FROM tasks WHERE sprint_id = ?", (sprint_id,))
            else:
                sprint_id = str(uuid4())
                cur.execute("INSERT INTO sprints (id, sprint_number, name, status) VALUES (?, ?, ?, ?)",
                            (sprint_id, sprint_number, name, status))

            # 2. Guardar tareas y asignaciones
            created_tasks: List[TaskItem] = []
            for t in tasks:
                t_id = str(uuid4())
                t_status = t.status if t.status in ["completed", "in_progress"] else "completed"
                cur.execute("INSERT INTO tasks (id, sprint_id, title, status) VALUES (?, ?, ?, ?)",
                            (t_id, sprint_id, t.title, t_status))

                is_task_completed = (t_status == "completed")
                assigned_devs: List[str] = []

                for dev_name in t.assigned_programmers:
                    # Asegurar existencia del programador
                    cur.execute("SELECT id, name FROM programmers WHERE name = ?", (dev_name.strip(),))
                    p_row = cur.fetchone()
                    if not p_row:
                        p_id = str(uuid4())
                        cur.execute("INSERT INTO programmers (id, name, active) VALUES (?, ?, 1)", (p_id, dev_name.strip()))
                    else:
                        p_id = p_row["id"]

                    assign_id = str(uuid4())
                    cur.execute(
                        "INSERT OR REPLACE INTO task_assignments (id, task_id, programmer_id, completed) VALUES (?, ?, ?, ?)",
                        (assign_id, t_id, p_id, 1 if is_task_completed else 0)
                    )
                    assigned_devs.append(dev_name.strip())

                created_tasks.append(TaskItem(
                    id=t_id,
                    sprint_id=sprint_id,
                    title=t.title,
                    status=t_status,
                    assigned_programmers=assigned_devs
                ))

            conn.commit()
            return SprintDetail(
                id=sprint_id,
                sprint_number=sprint_number,
                name=name,
                status=status,
                tasks=created_tasks
            )

    def get_sprints(self) -> List[dict]:
        with self._get_connection() as conn:
            cur = conn.cursor()
            query = """
                SELECT s.id, s.sprint_number, s.name, s.status,
                       COUNT(t.id) as task_count
                FROM sprints s
                LEFT JOIN tasks t ON s.id = t.sprint_id
                GROUP BY s.id, s.sprint_number, s.name, s.status
                ORDER BY s.sprint_number ASC
            """
            cur.execute(query)
            return [dict(row) for row in cur.fetchall()]

    def get_sprint_detail(self, sprint_number: int) -> Optional[SprintDetail]:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT id, sprint_number, name, status FROM sprints WHERE sprint_number = ?", (sprint_number,))
            s_row = cur.fetchone()
            if not s_row:
                return None

            sprint_id = s_row["id"]
            cur.execute("SELECT id, title, status FROM tasks WHERE sprint_id = ? ORDER BY rowid ASC", (sprint_id,))
            tasks_rows = cur.fetchall()

            task_items: List[TaskItem] = []
            for tr in tasks_rows:
                t_id = tr["id"]
                cur.execute("""
                    SELECT p.name
                    FROM task_assignments ta
                    JOIN programmers p ON ta.programmer_id = p.id
                    WHERE ta.task_id = ?
                    ORDER BY p.name ASC
                """, (t_id,))
                devs = [r["name"] for r in cur.fetchall()]
                task_items.append(TaskItem(
                    id=t_id,
                    sprint_id=sprint_id,
                    title=tr["title"],
                    status=tr["status"],
                    assigned_programmers=devs
                ))

            return SprintDetail(
                id=sprint_id,
                sprint_number=s_row["sprint_number"],
                name=s_row["name"],
                status=s_row["status"],
                tasks=task_items
            )

    def delete_sprint(self, sprint_number: int) -> bool:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM sprints WHERE sprint_number = ?", (sprint_number,))
            conn.commit()
            return cur.rowcount > 0

    def get_matrix_data(self) -> Tuple[List[int], Dict[int, str], Dict[str, Dict[int, int]], Dict[str, Dict[int, int]], List[str]]:
        with self._get_connection() as conn:
            cur = conn.cursor()

            # 1. Programadores activos
            cur.execute("SELECT name FROM programmers WHERE active = 1 ORDER BY name ASC")
            progs = [r["name"] for r in cur.fetchall()]

            # 2. Sprints ordenados
            cur.execute("SELECT sprint_number, name FROM sprints ORDER BY sprint_number ASC")
            sprint_rows = cur.fetchall()
            sprints = [r["sprint_number"] for r in sprint_rows]
            sprint_names = {r["sprint_number"]: r["name"] for r in sprint_rows}

            # 3. Datos de asignaciones completadas y totales
            completed_data: Dict[str, Dict[int, int]] = {p: {} for p in progs}
            assigned_data: Dict[str, Dict[int, int]] = {p: {} for p in progs}

            query = """
                SELECT p.name as prog_name, s.sprint_number,
                       SUM(CASE WHEN (t.status = 'completed' AND ta.completed = 1) THEN 1 ELSE 0 END) as completed_tasks,
                       COUNT(ta.id) as assigned_tasks
                FROM task_assignments ta
                JOIN tasks t ON ta.task_id = t.id
                JOIN sprints s ON t.sprint_id = s.id
                JOIN programmers p ON ta.programmer_id = p.id
                GROUP BY p.name, s.sprint_number
            """
            cur.execute(query)
            for r in cur.fetchall():
                p_name = r["prog_name"]
                s_num = r["sprint_number"]
                if p_name in completed_data:
                    completed_data[p_name][s_num] = r["completed_tasks"]
                    assigned_data[p_name][s_num] = r["assigned_tasks"]

            return sprints, sprint_names, completed_data, assigned_data, progs

    def get_programmer_history(self, name: str) -> Optional[dict]:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT id, name, active FROM programmers WHERE name = ?", (name.strip(),))
            p_row = cur.fetchone()
            if not p_row:
                return None

            p_id = p_row["id"]
            p_name = p_row["name"]

            query = """
                SELECT t.id as task_id, t.title, t.status as task_status,
                       s.id as sprint_id, s.sprint_number, s.name as sprint_name, s.status as sprint_status,
                       ta.completed as assignment_completed
                FROM task_assignments ta
                JOIN tasks t ON ta.task_id = t.id
                JOIN sprints s ON t.sprint_id = s.id
                WHERE ta.programmer_id = ?
                ORDER BY s.sprint_number ASC, t.created_at ASC
            """
            cur.execute(query, (p_id,))
            rows = cur.fetchall()

            sprints_map = {}
            total_completed = 0
            total_assigned = len(rows)

            for r in rows:
                s_num = r["sprint_number"]
                if s_num not in sprints_map:
                    sprints_map[s_num] = {
                        "sprint_number": s_num,
                        "sprint_name": r["sprint_name"],
                        "sprint_status": r["sprint_status"],
                        "tasks": []
                    }

                # Buscar colaboradores en esta tarea
                cur.execute("""
                    SELECT p.name
                    FROM task_assignments ta2
                    JOIN programmers p ON ta2.programmer_id = p.id
                    WHERE ta2.task_id = ? AND ta2.programmer_id != ?
                    ORDER BY p.name ASC
                """, (r["task_id"], p_id))
                co_workers = [cr["name"] for cr in cur.fetchall()]

                is_comp = bool(r["task_status"] == "completed" and r["assignment_completed"] == 1)
                if is_comp:
                    total_completed += 1

                sprints_map[s_num]["tasks"].append({
                    "title": r["title"],
                    "status": r["task_status"],
                    "completed": is_comp,
                    "co_workers": co_workers
                })

            return {
                "name": p_name,
                "active": bool(p_row["active"]),
                "total_completed": total_completed,
                "total_assigned": total_assigned,
                "sprints": list(sprints_map.values())
            }

    # -------------------------------------------------------------------------
    # Gestión de Usuarios y Roles
    # -------------------------------------------------------------------------
    def get_user_profile(self, user_id_or_email: str) -> Optional[dict]:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, email, name, role, active, created_at FROM user_profiles WHERE id = ? OR LOWER(email) = LOWER(?)",
                (user_id_or_email, user_id_or_email)
            )
            row = cur.fetchone()
            if row:
                return dict(row)
            return None

    def list_user_profiles(self) -> List[dict]:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT id, email, name, role, active, created_at FROM user_profiles ORDER BY name ASC")
            return [dict(r) for r in cur.fetchall()]

    def upsert_user_profile(
        self,
        user_id: str,
        email: str,
        name: str,
        role: str = "lider",
        password: str = "",
        active: bool = True
    ) -> dict:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT id FROM user_profiles WHERE id = ? OR LOWER(email) = LOWER(?)", (user_id, email.lower()))
            existing = cur.fetchone()
            if existing:
                cur.execute(
                    "UPDATE user_profiles SET name = ?, role = ?, active = ? WHERE id = ?",
                    (name, role, 1 if active else 0, existing["id"])
                )
            else:
                cur.execute(
                    "INSERT INTO user_profiles (id, email, name, role, password, active) VALUES (?, ?, ?, ?, ?, ?)",
                    (user_id, email.lower(), name, role, password, 1 if active else 0)
                )
            conn.commit()
            return self.get_user_profile(user_id) or {
                "id": user_id, "email": email, "name": name, "role": role, "active": active
            }

    def update_user_profile(
        self,
        user_id: str,
        name: Optional[str] = None,
        role: Optional[str] = None,
        active: Optional[bool] = None,
        password: Optional[str] = None
    ) -> bool:
        with self._get_connection() as conn:
            cur = conn.cursor()
            fields = []
            vals = []
            if name is not None:
                fields.append("name = ?")
                vals.append(name.strip())
            if role is not None:
                fields.append("role = ?")
                vals.append(role)
            if active is not None:
                fields.append("active = ?")
                vals.append(1 if active else 0)
            if password is not None and len(password) >= 6:
                fields.append("password = ?")
                vals.append(password)
            if not fields:
                return False
            vals.append(user_id)
            cur.execute(f"UPDATE user_profiles SET {', '.join(fields)} WHERE id = ?", vals)
            conn.commit()
            return cur.rowcount > 0

    def delete_user_profile(self, user_id: str) -> bool:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM user_profiles WHERE id = ?", (user_id,))
            conn.commit()
            return cur.rowcount > 0

