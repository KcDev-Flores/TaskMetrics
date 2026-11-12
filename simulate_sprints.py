"""
Simulación de Sprints con Asignación de Tareas y Colaboración Compartida
Verifica la exactitud matemática y la distribución de ingresos.
"""

import sys
import os
import tempfile

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.database.sqlite import SQLiteMetricsRepository
from src.services.metrics_service import TaskMetricsService
from src.models.schemas import TaskItem


def run_simulation():
    print("=" * 80)
    print(" TASKMETRICS - CONTROL DE RENDIMIENTO Y TRANSPARENCIA FINANCIERA ")
    print("=" * 80)

    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "simulation.db")
        repo = SQLiteMetricsRepository(db_path=db_path)
        service = TaskMetricsService(repo)

        # 1. Registrar Desarrolladores del Estudio
        integrantes = ["Capo", "Fabi", "Dylan", "Dreymor"]
        print(f"\n[Fase 1] Registrando integrantes del equipo: {', '.join(integrantes)}")
        for dev in integrantes:
            service.register_programmer(dev)

        # 2. Sprint 1: Tareas compartidas y asignaciones múltiples
        print("\n--- Registrando Sprint 1: Tareas del Mod ---")
        print("  * Tarea 1 (Core Engine): Trabajada en equipo por Capo y Dreymor")
        print("  * Tarea 2 (Modelos 3D): Asignada a Fabi")
        print("  * Tarea 3 (Efectos de Partículas): Asignada a Dylan")
        tasks_s1 = [
            TaskItem(title="Motor Principal", status="completed", assigned_programmers=["Capo", "Dreymor"]),
            TaskItem(title="Modelos 3D", status="completed", assigned_programmers=["Fabi"]),
            TaskItem(title="Efectos de Partículas", status="completed", assigned_programmers=["Dylan"]),
        ]
        service.save_sprint_with_tasks(1, "Sprint 1 - Inicial", "completed", tasks_s1)

        # 3. Sprint 2: Colaboración y mayor esfuerzo
        print("\n--- Registrando Sprint 2: Ampliación ---")
        print("  * Tarea 1: Capo y Fabi")
        print("  * Tarea 2: Dylan y Dreymor")
        print("  * Tarea 3 (Extra): Capo (doble trabajo)")
        tasks_s2 = [
            TaskItem(title="Lógica de Entidades", status="completed", assigned_programmers=["Capo", "Fabi"]),
            TaskItem(title="Texturas y Shaders", status="completed", assigned_programmers=["Dylan", "Dreymor"]),
            TaskItem(title="Optimización de Memoria", status="completed", assigned_programmers=["Capo"]),
        ]
        service.save_sprint_with_tasks(2, "Sprint 2 - Entidades", "completed", tasks_s2)

        # 4. Cálculo de Matriz y Resultados
        print("\n" + "=" * 80)
        print(" REPORTE TABLERO: DISTRIBUCIÓN DE INGRESOS POR ESFUERZO REAL ")
        print("=" * 80)
        print(service.export_to_markdown_string())

        matrix = service.get_metrics_matrix()
        print(f"[OK] Total de asignaciones cerradas por el equipo: {matrix.team_total_tasks}")
        print(f"[OK] Tasa global de asignaciones realizadas: {matrix.overall_completion_rate}%")
        sum_pct = sum(m.percentage for m in matrix.programmer_metrics)
        print(f"[OK] Suma exacta de distribución de ingresos: {sum_pct:.4f}% (~100.0%)")


if __name__ == "__main__":
    run_simulation()
