import os
import tempfile
import unittest
from fastapi.testclient import TestClient

from src.core.calculator import MetricsCalculator
from src.database.sqlite import SQLiteMetricsRepository
from src.services.metrics_service import TaskMetricsService
from src.models.schemas import TaskItem
from src.web.app import create_app


class TestMetricsCalculator(unittest.TestCase):
    def test_percentage_calculation(self):
        pct = MetricsCalculator.calculate_percentage(40, 118, precision_decimals=4)
        self.assertEqual(pct, 33.8983)

    def test_zero_division(self):
        self.assertEqual(MetricsCalculator.calculate_percentage(0, 0), 0.0)

    def test_matrix_builder(self):
        programmers = ["Capo", "Dylan", "Fabi"]
        sprints = [1]
        sprint_names = {1: "Sprint 1"}
        completed_data = {
            "Capo": {1: 10},
            "Dylan": {1: 10},
            "Fabi": {1: 8},
        }
        assigned_data = {
            "Capo": {1: 10},
            "Dylan": {1: 10},
            "Fabi": {1: 10},
        }
        matrix = MetricsCalculator.build_matrix(
            programmers=programmers,
            sprints=sprints,
            sprint_names=sprint_names,
            completed_task_data=completed_data,
            assigned_task_data=assigned_data
        )

        self.assertEqual(matrix.team_total_tasks, 28)
        self.assertEqual(matrix.team_total_assigned, 30)
        # 28 / 30 = 93.3%
        self.assertEqual(matrix.overall_completion_rate, 93.3)

        fabi = next(m for m in matrix.programmer_metrics if m.programmer_name == "Fabi")
        self.assertEqual(fabi.completion_rate, 80.0)


class TestSQLiteMetricsRepository(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        db_path = os.path.join(self.temp_dir.name, "test.db")
        self.repo = SQLiteMetricsRepository(db_path=db_path)
        self.service = TaskMetricsService(self.repo)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_shared_task_assignment_flow(self):
        # 1. Registrar integrantes
        self.service.register_programmer("Capo")
        self.service.register_programmer("Fabi")
        self.service.register_programmer("Dylan")
        self.service.register_programmer("Dreymor")

        # 2. Guardar Sprint 1 con tareas compartidas (como en el ejemplo del usuario)
        tasks = [
            TaskItem(title="Tarea 1: Motor", status="completed", assigned_programmers=["Capo", "Dreymor"]),
            TaskItem(title="Tarea 2: Texturas", status="completed", assigned_programmers=["Fabi"]),
            TaskItem(title="Tarea 3: Sonidos", status="completed", assigned_programmers=["Dylan"]),
        ]
        sprint = self.service.save_sprint_with_tasks(1, "Sprint 1", "completed", tasks)
        self.assertEqual(sprint.sprint_number, 1)

        # 3. Verificar matriz
        matrix = self.service.get_metrics_matrix()
        # Capo: 1, Dreymor: 1, Fabi: 1, Dylan: 1 -> Total equipo = 4
        self.assertEqual(matrix.team_total_tasks, 4)

        capo_m = next(m for m in matrix.programmer_metrics if m.programmer_name == "Capo")
        self.assertEqual(capo_m.total_accumulated, 1)
        self.assertEqual(capo_m.percentage, 25.0)

        # 4. Modificar sprint
        tasks.append(TaskItem(title="Tarea 4: Entidades", status="completed", assigned_programmers=["Capo"]))
        self.service.save_sprint_with_tasks(1, "Sprint 1", "completed", tasks)

        matrix_updated = self.service.get_metrics_matrix()
        # Capo: 2, Dreymor: 1, Fabi: 1, Dylan: 1 -> Total = 5
        self.assertEqual(matrix_updated.team_total_tasks, 5)
        capo_m2 = next(m for m in matrix_updated.programmer_metrics if m.programmer_name == "Capo")
        self.assertEqual(capo_m2.total_accumulated, 2)
        self.assertEqual(capo_m2.percentage, 40.0)

    def test_delete_sprint(self):
        tasks = [TaskItem(title="Tarea A", status="completed", assigned_programmers=["Capo"])]
        self.service.save_sprint_with_tasks(1, "Sprint 1", "completed", tasks)
        self.service.save_sprint_with_tasks(2, "Sprint 2", "completed", tasks)

        matrix = self.service.get_metrics_matrix()
        self.assertEqual(len(matrix.sprints), 2)

        # Borrar sprint 1
        self.service.delete_sprint(1)
        matrix_after = self.service.get_metrics_matrix()
        self.assertEqual(len(matrix_after.sprints), 1)
        self.assertEqual(matrix_after.sprints, [2])


class TestWebAPI(unittest.TestCase):
    def setUp(self):
        import tempfile
        from src.database.sqlite import SQLiteMetricsRepository
        from src.services.metrics_service import TaskMetricsService

        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.temp_db.close()
        self.repo = SQLiteMetricsRepository(db_path=self.temp_db.name)

        self.app = create_app()
        # Sobrescribir get_service en la app de prueba para usar base aislada
        self.client = TestClient(self.app)

        # Iniciar sesión de prueba con usuario confirmado
        login_res = self.client.post("/api/auth/login", json={
            "email": "admin@taskmetrics.com",
            "password": "admin123"
        })
        self.token = login_res.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}

    def tearDown(self):
        import os
        try:
            if os.path.exists(self.temp_db.name):
                os.remove(self.temp_db.name)
        except Exception:
            pass

    def test_api_routes(self):
        # 1. Dashboard HTML (público)
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)

        # 2. Integrantes (protegido)
        res_add = self.client.post("/api/programmers", json={"name": "Capo"}, headers=self.headers)
        self.assertEqual(res_add.status_code, 200)

        res_list = self.client.get("/api/programmers", headers=self.headers)
        self.assertEqual(res_list.status_code, 200)
        self.assertTrue(any(p["name"] == "Capo" for p in res_list.json()))

        # 3. Sprints (protegido)
        sprint_payload = {
            "sprint_number": 1,
            "name": "Sprint 1 Inicial",
            "status": "completed",
            "tasks": [
                {"title": "Tarea 1", "status": "completed", "assigned_programmers": ["Capo"]}
            ]
        }
        res_sprint = self.client.post("/api/sprints", json=sprint_payload, headers=self.headers)
        self.assertEqual(res_sprint.status_code, 200)

        # 4. Metrics (protegido)
        res_metrics = self.client.get("/api/metrics", headers=self.headers)
        self.assertEqual(res_metrics.status_code, 200)
        m_data = res_metrics.json()
        self.assertGreaterEqual(m_data["team_total_tasks"], 1)

        # 5. Historial detallado por integrante (protegido)
        res_history = self.client.get("/api/programmers/Capo/history", headers=self.headers)
        self.assertEqual(res_history.status_code, 200)
        h_data = res_history.json()
        self.assertEqual(h_data["name"], "Capo")
        self.assertGreaterEqual(h_data["total_completed"], 1)
        self.assertGreaterEqual(len(h_data["sprints"]), 1)

        # 6. Export (protegido)
        res_exp = self.client.get("/api/export?format=csv", headers=self.headers)
        self.assertEqual(res_exp.status_code, 200)
        self.assertIn("Capo", res_exp.text)



if __name__ == "__main__":
    unittest.main()
