from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List
from src.models.schemas import ProgrammerMetric, MetricsMatrix


class MetricsCalculator:
    """
    Motor matemático con alta fidelidad decimal (sin discrepancias de punto flotante).
    Calcula:
      1. Porcentaje de ingresos (% participación en base al trabajo completado).
      2. Tasa de eficiencia / completitud global e individual.
    """

    @staticmethod
    def calculate_percentage(
        numerator: int,
        denominator: int,
        precision_decimals: int = 4
    ) -> float:
        if denominator <= 0:
            return 0.0

        num = Decimal(str(numerator))
        denom = Decimal(str(denominator))
        pct = (num / denom) * Decimal("100")

        quantize_format = Decimal("1." + ("0" * precision_decimals))
        return float(pct.quantize(quantize_format, rounding=ROUND_HALF_UP))

    @classmethod
    def build_matrix(
        cls,
        programmers: List[str],
        sprints: List[int],
        sprint_names: Dict[int, str],
        completed_task_data: Dict[str, Dict[int, int]],
        assigned_task_data: Dict[str, Dict[int, int]],
        precision_decimals: int = 4
    ) -> MetricsMatrix:
        sorted_sprints = sorted(sprints)
        programmer_metrics: List[ProgrammerMetric] = []
        sprint_totals: Dict[int, int] = {s: 0 for s in sorted_sprints}

        team_total_completed = 0
        team_total_assigned = 0

        for prog in sorted(programmers):
            prog_sprint_completed: Dict[int, int] = {}
            total_prog_completed = 0
            total_prog_assigned = 0

            for s in sorted_sprints:
                comp = completed_task_data.get(prog, {}).get(s, 0)
                assg = assigned_task_data.get(prog, {}).get(s, 0)

                prog_sprint_completed[s] = comp
                sprint_totals[s] += comp
                total_prog_completed += comp
                total_prog_assigned += max(assg, comp)

            team_total_completed += total_prog_completed
            team_total_assigned += total_prog_assigned

            completion_rate = cls.calculate_percentage(
                total_prog_completed,
                total_prog_assigned if total_prog_assigned > 0 else total_prog_completed,
                precision_decimals=1
            )

            metric = ProgrammerMetric(
                programmer_name=prog,
                sprint_tasks=prog_sprint_completed,
                total_accumulated=total_prog_completed,
                total_assigned=total_prog_assigned,
                percentage=0.0,
                completion_rate=completion_rate
            )
            programmer_metrics.append(metric)

        # Calcular porcentaje de participación de ingresos para cada integrante
        for metric in programmer_metrics:
            metric.percentage = cls.calculate_percentage(
                metric.total_accumulated,
                team_total_completed,
                precision_decimals=precision_decimals
            )

        overall_rate = cls.calculate_percentage(
            team_total_completed,
            team_total_assigned if team_total_assigned > 0 else team_total_completed,
            precision_decimals=1
        )

        return MetricsMatrix(
            sprints=sorted_sprints,
            sprint_names=sprint_names,
            programmer_metrics=programmer_metrics,
            team_total_tasks=team_total_completed,
            team_total_assigned=team_total_assigned,
            overall_completion_rate=overall_rate,
            sprint_totals=sprint_totals
        )
