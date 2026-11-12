from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple
from src.models.schemas import Programmer, SprintDetail, TaskItem


class BaseMetricsRepository(ABC):
    @abstractmethod
    def add_programmer(self, name: str) -> Programmer:
        pass

    @abstractmethod
    def update_programmer(self, old_name: str, new_name: str, active: bool = True) -> bool:
        pass

    @abstractmethod
    def remove_programmer(self, name: str) -> bool:
        pass

    @abstractmethod
    def get_programmers(self, active_only: bool = True) -> List[Programmer]:
        pass

    @abstractmethod
    def save_sprint_with_tasks(
        self,
        sprint_number: int,
        name: str,
        status: str,
        tasks: List[TaskItem]
    ) -> SprintDetail:
        pass

    @abstractmethod
    def get_sprints(self) -> List[dict]:
        """Devuelve lista de [{sprint_number, name, status, task_count}]"""
        pass

    @abstractmethod
    def get_sprint_detail(self, sprint_number: int) -> Optional[SprintDetail]:
        pass

    @abstractmethod
    def delete_sprint(self, sprint_number: int) -> bool:
        pass

    @abstractmethod
    def get_matrix_data(self) -> Tuple[List[int], Dict[int, str], Dict[str, Dict[int, int]], Dict[str, Dict[int, int]], List[str]]:
        """
        Retorna:
          (sprints, sprint_names, completed_data, assigned_data, programmers_names)
        """
        pass

    @abstractmethod
    def get_programmer_history(self, name: str) -> Optional[dict]:
        """
        Retorna el historial completo de sprints y tareas realizadas por un integrante,
        incluyendo compañeros colaboradores en cada tarea.
        """
        pass
