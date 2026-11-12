import csv
import io
from typing import Dict, List, Optional
from tabulate import tabulate

from src.models.schemas import MetricsMatrix, Programmer, SprintDetail, TaskItem
from src.database.base import BaseMetricsRepository
from src.core.calculator import MetricsCalculator


class TaskMetricsService:
    def __init__(self, repository: BaseMetricsRepository):
        self.repository = repository
        self.calculator = MetricsCalculator()

    # -------------------------------------------------------------------------
    # Gestión de Integrantes
    # -------------------------------------------------------------------------
    def register_programmer(self, name: str) -> Programmer:
        return self.repository.add_programmer(name.strip())

    def update_programmer(self, old_name: str, new_name: str, active: bool = True) -> bool:
        return self.repository.update_programmer(old_name, new_name, active)

    def remove_programmer(self, name: str) -> bool:
        return self.repository.remove_programmer(name.strip())

    def get_programmers(self, active_only: bool = True) -> List[Programmer]:
        return self.repository.get_programmers(active_only=active_only)

    def get_programmer_history(self, name: str) -> Optional[dict]:
        history = self.repository.get_programmer_history(name)
        if not history:
            return None

        # Incorporar cálculo de porcentaje de ingresos actual del integrante
        matrix = self.get_metrics_matrix()
        metric = next((m for m in matrix.programmer_metrics if m.programmer_name.lower() == name.lower()), None)
        if metric:
            history["revenue_percentage"] = metric.percentage
            history["completion_rate"] = metric.completion_rate
        else:
            history["revenue_percentage"] = 0.0
            history["completion_rate"] = 0.0

        return history

    # -------------------------------------------------------------------------
    # Gestión de Sprints y Tareas
    # -------------------------------------------------------------------------
    def save_sprint_with_tasks(
        self,
        sprint_number: int,
        name: str,
        status: str,
        tasks: List[TaskItem]
    ) -> SprintDetail:
        return self.repository.save_sprint_with_tasks(
            sprint_number=sprint_number,
            name=name.strip(),
            status=status,
            tasks=tasks
        )

    def get_sprints_list(self) -> List[dict]:
        return self.repository.get_sprints()

    def get_sprint_detail(self, sprint_number: int) -> Optional[SprintDetail]:
        return self.repository.get_sprint_detail(sprint_number)

    def delete_sprint(self, sprint_number: int) -> bool:
        return self.repository.delete_sprint(sprint_number)

    # -------------------------------------------------------------------------
    # Métricas y Tablero
    # -------------------------------------------------------------------------
    def get_metrics_matrix(
        self,
        precision_decimals: int = 4,
        up_to_sprint: Optional[int] = None
    ) -> MetricsMatrix:
        sprints, sprint_names, completed_data, assigned_data, programmers = self.repository.get_matrix_data()

        if up_to_sprint is not None:
            filtered_sprints = [s for s in sprints if s <= up_to_sprint]
        else:
            filtered_sprints = sprints

        return self.calculator.build_matrix(
            programmers=programmers,
            sprints=filtered_sprints,
            sprint_names=sprint_names,
            completed_task_data=completed_data,
            assigned_task_data=assigned_data,
            precision_decimals=precision_decimals
        )

    # -------------------------------------------------------------------------
    # Exportaciones (CSV / Markdown)
    # -------------------------------------------------------------------------
    def export_to_csv_string(
        self,
        precision_decimals: int = 4,
        up_to_sprint: Optional[int] = None
    ) -> str:
        matrix = self.get_metrics_matrix(precision_decimals=precision_decimals, up_to_sprint=up_to_sprint)
        headers = ["Programador"] + [f"Sprint {s}" for s in matrix.sprints] + ["Total Acumulado", "Participacion (%)", "Eficacia (%)"]
        rows = []

        for p in matrix.programmer_metrics:
            row = [p.programmer_name] + [p.sprint_tasks.get(s, 0) for s in matrix.sprints] + [
                p.total_accumulated,
                f"{p.percentage:.4f}%",
                f"{p.completion_rate:.1f}%"
            ]
            rows.append(row)

        team_row = ["TOTAL EQUIPO"] + [matrix.sprint_totals.get(s, 0) for s in matrix.sprints] + [
            matrix.team_total_tasks,
            "100.0000%" if matrix.team_total_tasks > 0 else "0.0000%",
            f"{matrix.overall_completion_rate:.1f}%"
        ]
        rows.append(team_row)

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(headers)
        writer.writerows(rows)
        return output.getvalue()

    def export_to_markdown_string(
        self,
        precision_decimals: int = 4,
        up_to_sprint: Optional[int] = None
    ) -> str:
        matrix = self.get_metrics_matrix(precision_decimals=precision_decimals, up_to_sprint=up_to_sprint)
        if not matrix.programmer_metrics:
            return "# Reporte de Rendimiento\n\nNo hay datos de integrantes registrados.\n"

        headers = ["Programador"] + [f"Sprint {s}" for s in matrix.sprints] + ["Total Acumulado", "Participación (%)", "Eficacia (%)"]
        rows = []

        for p in matrix.programmer_metrics:
            row = [p.programmer_name] + [p.sprint_tasks.get(s, 0) for s in matrix.sprints] + [
                p.total_accumulated,
                f"{p.percentage:.4f}%",
                f"{p.completion_rate:.1f}%"
            ]
            rows.append(row)

        team_row = ["TOTAL EQUIPO"] + [matrix.sprint_totals.get(s, 0) for s in matrix.sprints] + [
            matrix.team_total_tasks,
            "100.0000%" if matrix.team_total_tasks > 0 else "0.0000%",
            f"{matrix.overall_completion_rate:.1f}%"
        ]
        rows.append(team_row)

        table = tabulate(rows, headers=headers, tablefmt="github")
        return f"# Reporte de Rendimiento y Participación de Ingresos\n\n{table}\n"
