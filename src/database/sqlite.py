from contextlib import contextmanager
import hashlib
import hmac
import os
import secrets
import sqlite3
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from src.core.config import Config
from src.models.schemas import Programmer, SprintDetail, TaskItem
from .base import BaseMetricsRepository

DEFAULT_AREA = "general"
_HASH_PREFIX = "pbkdf2$"
_PROFILE_COLUMNS = "id, username, name, role, area, active, created_at"


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 200_000).hex()
    return f"{_HASH_PREFIX}{salt}${digest}"


def _password_matches(stored: str, password: str) -> bool:
    if not stored:
        return False
    if not stored.startswith(_HASH_PREFIX):
        # Bases locales antiguas guardaban la contraseña en texto plano
        return hmac.compare_digest(stored, password)
    try:
        _, salt, digest = stored.split("$")
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 200_000).hex()
    except ValueError:
        return False
    return hmac.compare_digest(candidate, digest)


class SQLiteMetricsRepository(BaseMetricsRepository):
    """
    Repositorio persistente local en SQLite (modo sin Supabase).
    Cada instancia opera sobre una sola área: integrantes y sprints de otras áreas no son visibles.
    """

    def __init__(self, db_path: Optional[str] = None, area: str = DEFAULT_AREA):
        db_path = db_path or Config.SQLITE_PATH
        if not db_path:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            db_dir = os.path.join(base_dir, "database")
            os.makedirs(db_dir, exist_ok=True)
            self.db_path = os.path.join(db_dir, "taskmetrics.db")
        else:
            self.db_path = db_path
        self.area = (area or DEFAULT_AREA).strip().lower()

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

    _SCOPED_TABLES_DDL = """
        CREATE TABLE IF NOT EXISTS programmers (
            id TEXT PRIMARY KEY,
            area TEXT NOT NULL DEFAULT 'general',
            name TEXT NOT NULL COLLATE NOCASE,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(area, name)
        );

        CREATE TABLE IF NOT EXISTS sprints (
            id TEXT PRIMARY KEY,
            area TEXT NOT NULL DEFAULT 'general',
            sprint_number INTEGER NOT NULL,
            name TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'completed',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(area, sprint_number)
        );
    """

    def _migrate_legacy_schema(self, conn: sqlite3.Connection) -> None:
        """Bases creadas antes de las áreas: integrantes y sprints eran globales."""
        columns = [r["name"] for r in conn.execute("PRAGMA table_info(sprints)")]
        if not columns or "area" in columns:
            return
        conn.commit()
        conn.execute("PRAGMA foreign_keys = OFF;")
        # Evita que el RENAME reescriba las llaves foráneas de tasks/task_assignments
        conn.execute("PRAGMA legacy_alter_table = ON;")
        try:
            conn.executescript(
                """
                BEGIN;
                ALTER TABLE programmers RENAME TO _legacy_programmers;
                ALTER TABLE sprints RENAME TO _legacy_sprints;
                """
                + self._SCOPED_TABLES_DDL
                + """
                INSERT INTO programmers (id, area, name, active, created_at)
                    SELECT id, 'general', name, active, created_at FROM _legacy_programmers;
                INSERT INTO sprints (id, area, sprint_number, name, status, created_at)
                    SELECT id, 'general', sprint_number, name, status, created_at FROM _legacy_sprints;
                DROP TABLE _legacy_programmers;
                DROP TABLE _legacy_sprints;
                COMMIT;
                """
            )
        finally:
            conn.execute("PRAGMA legacy_alter_table = OFF;")
            conn.execute("PRAGMA foreign_keys = ON;")

    def _init_db(self):
        with self._get_connection() as conn:
            self._migrate_legacy_schema(conn)
            # Antes las cuentas se identificaban por correo; el valor se conserva como usuario
            legacy_profile = [r["name"] for r in conn.execute("PRAGMA table_info(user_profiles)")]
            if "email" in legacy_profile and "username" not in legacy_profile:
                conn.execute("ALTER TABLE user_profiles RENAME COLUMN email TO username")
                conn.commit()
            conn.executescript(self._SCOPED_TABLES_DDL + """
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
                    username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    name TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'lider',
                    area TEXT,
                    password TEXT NOT NULL DEFAULT '',
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS local_sessions (
                    token TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
                    kind TEXT NOT NULL DEFAULT 'access',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            profile_columns = [r["name"] for r in conn.execute("PRAGMA table_info(user_profiles)")]
            if "area" not in profile_columns:
                conn.execute("ALTER TABLE user_profiles ADD COLUMN area TEXT")

            # Admin inicial del modo local si todavía no hay usuarios
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) as count FROM user_profiles")
            if cur.fetchone()["count"] == 0:
                cur.execute(
                    "INSERT INTO user_profiles (id, username, name, role, password, active) VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        str(uuid4()),
                        Config.LOCAL_ADMIN_USERNAME,
                        "Administrador Principal",
                        "admin",
                        hash_password(Config.LOCAL_ADMIN_PASSWORD),
                        1,
                    )
                )
            conn.commit()

    def list_areas(self) -> List[str]:
        """Áreas que ya tienen integrantes o sprints registrados."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT area FROM programmers UNION SELECT area FROM sprints ORDER BY area"
            ).fetchall()
            return [r["area"] for r in rows]

    def add_programmer(self, name: str) -> Programmer:
        clean_name = name.strip()
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT id, name, active FROM programmers WHERE area = ? AND name = ?", (self.area, clean_name))
            row = cur.fetchone()
            if row:
                return Programmer(id=row["id"], name=row["name"], active=bool(row["active"]))

            new_id = str(uuid4())
            cur.execute("INSERT INTO programmers (id, area, name, active) VALUES (?, ?, ?, 1)", (new_id, self.area, clean_name))
            conn.commit()
            return Programmer(id=new_id, name=clean_name, active=True)

    def update_programmer(self, old_name: str, new_name: str, active: bool = True) -> bool:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE programmers SET name = ?, active = ? WHERE area = ? AND name = ?",
                (new_name.strip(), 1 if active else 0, self.area, old_name.strip())
            )
            conn.commit()
            return cur.rowcount > 0

    def remove_programmer(self, name: str) -> bool:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM programmers WHERE area = ? AND name = ?", (self.area, name.strip()))
            conn.commit()
            return cur.rowcount > 0

    def get_programmers(self, active_only: bool = True) -> List[Programmer]:
        with self._get_connection() as conn:
            cur = conn.cursor()
            if active_only:
                cur.execute("SELECT id, name, active FROM programmers WHERE area = ? AND active = 1 ORDER BY name ASC", (self.area,))
            else:
                cur.execute("SELECT id, name, active FROM programmers WHERE area = ? ORDER BY name ASC", (self.area,))
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
            cur.execute("SELECT id FROM sprints WHERE area = ? AND sprint_number = ?", (self.area, sprint_number))
            row = cur.fetchone()
            if row:
                sprint_id = row["id"]
                cur.execute("UPDATE sprints SET name = ?, status = ? WHERE id = ?", (name, status, sprint_id))
                # Limpiar tareas anteriores para sobreescribir limpiamente (cascada elimina asignaciones)
                cur.execute("DELETE FROM tasks WHERE sprint_id = ?", (sprint_id,))
            else:
                sprint_id = str(uuid4())
                cur.execute("INSERT INTO sprints (id, area, sprint_number, name, status) VALUES (?, ?, ?, ?, ?)",
                            (sprint_id, self.area, sprint_number, name, status))

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
                    cur.execute("SELECT id, name FROM programmers WHERE area = ? AND name = ?", (self.area, dev_name.strip()))
                    p_row = cur.fetchone()
                    if not p_row:
                        p_id = str(uuid4())
                        cur.execute("INSERT INTO programmers (id, area, name, active) VALUES (?, ?, ?, 1)", (p_id, self.area, dev_name.strip()))
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
                WHERE s.area = ?
                GROUP BY s.id, s.sprint_number, s.name, s.status
                ORDER BY s.sprint_number ASC
            """
            cur.execute(query, (self.area,))
            return [dict(row) for row in cur.fetchall()]

    def get_sprint_detail(self, sprint_number: int) -> Optional[SprintDetail]:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT id, sprint_number, name, status FROM sprints WHERE area = ? AND sprint_number = ?", (self.area, sprint_number))
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
            cur.execute("DELETE FROM sprints WHERE area = ? AND sprint_number = ?", (self.area, sprint_number))
            conn.commit()
            return cur.rowcount > 0

    def get_matrix_data(self) -> Tuple[List[int], Dict[int, str], Dict[str, Dict[int, int]], Dict[str, Dict[int, int]], List[str]]:
        with self._get_connection() as conn:
            cur = conn.cursor()

            # 1. Programadores activos
            cur.execute("SELECT name FROM programmers WHERE area = ? AND active = 1 ORDER BY name ASC", (self.area,))
            progs = [r["name"] for r in cur.fetchall()]

            # 2. Sprints ordenados
            cur.execute("SELECT sprint_number, name FROM sprints WHERE area = ? ORDER BY sprint_number ASC", (self.area,))
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
                WHERE s.area = ? AND p.area = ?
                GROUP BY p.name, s.sprint_number
            """
            cur.execute(query, (self.area, self.area))
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
            cur.execute("SELECT id, name, active FROM programmers WHERE area = ? AND name = ?", (self.area, name.strip()))
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
    # Usuarios y sesiones del modo local
    # -------------------------------------------------------------------------
    @staticmethod
    def _profile(row: Optional[sqlite3.Row]) -> Optional[dict]:
        if not row:
            return None
        profile = dict(row)
        profile["active"] = bool(profile["active"])
        return profile

    def get_user_profile(self, user_id_or_username: str) -> Optional[dict]:
        with self._get_connection() as conn:
            row = conn.execute(
                f"SELECT {_PROFILE_COLUMNS} FROM user_profiles WHERE id = ? OR LOWER(username) = LOWER(?)",
                (user_id_or_username, user_id_or_username)
            ).fetchone()
            return self._profile(row)

    def list_user_profiles(self) -> List[dict]:
        with self._get_connection() as conn:
            rows = conn.execute(f"SELECT {_PROFILE_COLUMNS} FROM user_profiles ORDER BY name ASC").fetchall()
            return [self._profile(r) for r in rows]

    def verify_credentials(self, username: str, password: str) -> Optional[dict]:
        """Devuelve el perfil si la contraseña es correcta; None en caso contrario."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT id, password FROM user_profiles WHERE LOWER(username) = LOWER(?)", (username,)
            ).fetchone()
            if not row or not _password_matches(row["password"], password):
                return None
            if not row["password"].startswith(_HASH_PREFIX):
                conn.execute(
                    "UPDATE user_profiles SET password = ? WHERE id = ?",
                    (hash_password(password), row["id"])
                )
                conn.commit()
        return self.get_user_profile(row["id"])

    def create_user_profile(
        self,
        username: str,
        name: str,
        role: str,
        area: Optional[str],
        password: str,
    ) -> dict:
        user_id = str(uuid4())
        with self._get_connection() as conn:
            try:
                conn.execute(
                    "INSERT INTO user_profiles (id, username, name, role, area, password, active) VALUES (?, ?, ?, ?, ?, ?, 1)",
                    (user_id, username.lower(), name, role, area, hash_password(password))
                )
                conn.commit()
            except sqlite3.IntegrityError:
                raise ValueError(f"Ya existe el usuario '{username}'.")
        return self.get_user_profile(user_id)

    def update_user_profile(self, user_id: str, changes: Dict[str, Any]) -> bool:
        """`changes` admite: name, role, area, active y password."""
        fields = []
        vals: List[Any] = []
        for column in ("name", "role", "area"):
            if column in changes:
                fields.append(f"{column} = ?")
                vals.append(changes[column])
        if "active" in changes:
            fields.append("active = ?")
            vals.append(1 if changes["active"] else 0)
        if changes.get("password"):
            fields.append("password = ?")
            vals.append(hash_password(changes["password"]))
        if not fields:
            return self.get_user_profile(user_id) is not None
        vals.append(user_id)
        with self._get_connection() as conn:
            cur = conn.execute(f"UPDATE user_profiles SET {', '.join(fields)} WHERE id = ?", vals)
            if "active" in changes and not changes["active"]:
                conn.execute("DELETE FROM local_sessions WHERE user_id = ?", (user_id,))
            conn.commit()
            return cur.rowcount > 0

    def delete_user_profile(self, user_id: str) -> bool:
        with self._get_connection() as conn:
            cur = conn.execute("DELETE FROM user_profiles WHERE id = ?", (user_id,))
            conn.commit()
            return cur.rowcount > 0

    def create_session(self, user_id: str, kind: str = "access") -> str:
        token = secrets.token_urlsafe(32)
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO local_sessions (token, user_id, kind) VALUES (?, ?, ?)",
                (token, user_id, kind)
            )
            conn.commit()
        return token

    def get_session_profile(self, token: str, kind: str = "access") -> Optional[dict]:
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT user_id FROM local_sessions WHERE token = ? AND kind = ?", (token, kind)
            ).fetchone()
        return self.get_user_profile(row["user_id"]) if row else None

    def delete_session(self, token: str) -> None:
        with self._get_connection() as conn:
            conn.execute("DELETE FROM local_sessions WHERE token = ?", (token,))
            conn.commit()
