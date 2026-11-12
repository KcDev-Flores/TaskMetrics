from typing import Dict, List, Optional
from uuid import uuid4
from src.models.schemas import Programmer, Sprint, SprintTask
from .base import BaseMetricsRepository


class InMemoryRepository(BaseMetricsRepository):
    """Repositorio en memoria para modo local, tests y pruebas sin conexión."""

    def __init__(self):
        self.programmers: Dict[str, Programmer] = {}
        self.sprints: Dict[str, Sprint] = {}
        self.tasks: Dict[str, SprintTask] = {}

    def add_programmer(self, name: str) -> Programmer:
        clean_name = name.strip()
        for p in self.programmers.values():
            if p.name.lower() == clean_name.lower():
                return p
        new_prog = Programmer(name=clean_name, id=str(uuid4()), active=True)
        self.programmers[new_prog.id] = new_prog
        return new_prog

    def get_programmers(self, active_only: bool = True) -> List[Programmer]:
        progs = list(self.programmers.values())
        if active_only:
            progs = [p for p in progs if p.active]
        return sorted(progs, key=lambda x: x.name)

    def remove_programmer(self, name: str) -> bool:
        target_id = None
        for p_id, p in list(self.programmers.items()):
            if p.name.lower() == name.lower().strip():
                target_id = p_id
                del self.programmers[p_id]
                break
        if target_id:
            keys_to_del = [k for k, t in self.tasks.items() if t.programmer_id == target_id]
            for k in keys_to_del:
                del self.tasks[k]
            return True
        return False

    def create_or_get_sprint(self, sprint_number: int, name: Optional[str] = None) -> Sprint:
        for s in self.sprints.values():
            if s.sprint_number == sprint_number:
                return s
        new_sprint = Sprint(
            sprint_number=sprint_number,
            id=str(uuid4()),
            name=name or f"Sprint {sprint_number}",
            closed=False
        )
        self.sprints[new_sprint.id] = new_sprint
        return new_sprint

    def get_sprints(self) -> List[Sprint]:
        return sorted(list(self.sprints.values()), key=lambda x: x.sprint_number)

    def delete_sprint(self, sprint_number: int) -> bool:
        target_id = None
        for s_id, s in list(self.sprints.items()):
            if s.sprint_number == sprint_number:
                target_id = s_id
                del self.sprints[s_id]
                break
        if target_id:
            keys_to_del = [k for k, t in self.tasks.items() if t.sprint_id == target_id]
            for k in keys_to_del:
                del self.tasks[k]
            return True
        return False

    def record_sprint_task(self, programmer_id: str, sprint_id: str, tasks_completed: int) -> SprintTask:
        key = f"{programmer_id}:{sprint_id}"
        record = SprintTask(
            programmer_id=programmer_id,
            sprint_id=sprint_id,
            tasks_completed=tasks_completed
        )
        self.tasks[key] = record
        return record

    def get_all_task_records(self) -> Dict[str, Dict[int, int]]:
        result: Dict[str, Dict[int, int]] = {p.name: {} for p in self.programmers.values()}
        for key, record in self.tasks.items():
            prog = self.programmers.get(record.programmer_id)
            sprint = self.sprints.get(record.sprint_id)
            if prog and sprint:
                if prog.name not in result:
                    result[prog.name] = {}
                result[prog.name][sprint.sprint_number] = record.tasks_completed
        return result

