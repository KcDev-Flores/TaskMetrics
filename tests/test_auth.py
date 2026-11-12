import unittest
from fastapi.testclient import TestClient

from src.web.app import create_app


class TestSupabaseAuthAndProtectedRoutes(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.client = TestClient(self.app)

    def test_unauthenticated_request_rejected(self):
        # Intentar acceder a rutas protegidas sin token debe devolver 401
        res = self.client.get("/api/metrics")
        self.assertEqual(res.status_code, 401)
        self.assertIn("No autorizado", res.json().get("detail", ""))

        res = self.client.get("/api/sprints")
        self.assertEqual(res.status_code, 401)

        res = self.client.get("/api/programmers")
        self.assertEqual(res.status_code, 401)

        res = self.client.post("/api/programmers", json={"name": "Hacker"})
        self.assertEqual(res.status_code, 401)

    def test_invalid_token_rejected(self):
        # Token malformado o falso debe devolver 401
        headers = {"Authorization": "Bearer token-falso-invalido"}
        res = self.client.get("/api/metrics", headers=headers)
        self.assertEqual(res.status_code, 401)

    def test_auth_status_endpoint(self):
        res = self.client.get("/api/auth/status")
        self.assertEqual(res.status_code, 200)
        self.assertIn("supabase_configured", res.json())

    def test_auth_flow_and_protected_access(self):
        # 1. Registro de usuario
        test_email = "tester_auth@taskmetrics.com"
        test_pwd = "securePassword123"

        reg_res = self.client.post("/api/auth/register", json={
            "email": test_email,
            "password": test_pwd
        })
        self.assertIn(reg_res.status_code, [200, 400])

        # 2. Inicio de sesión
        login_res = self.client.post("/api/auth/login", json={
            "email": test_email,
            "password": test_pwd
        })
        self.assertEqual(login_res.status_code, 200)
        login_data = login_res.json()
        self.assertIn("access_token", login_data)
        token = login_data["access_token"]
        refresh_token = login_data.get("refresh_token")

        headers = {"Authorization": f"Bearer {token}"}

        # 3. Verificar /api/auth/me
        me_res = self.client.get("/api/auth/me", headers=headers)
        self.assertEqual(me_res.status_code, 200)
        self.assertEqual(me_res.json()["user"]["email"], test_email)

        # 4. Acceder a rutas protegidas con token exitosamente
        metrics_res = self.client.get("/api/metrics", headers=headers)
        self.assertEqual(metrics_res.status_code, 200)

        prog_res = self.client.get("/api/programmers", headers=headers)
        self.assertEqual(prog_res.status_code, 200)

        # 5. Operaciones de escritura protegidas
        add_prog_res = self.client.post("/api/programmers", json={"name": "DevAuthUser"}, headers=headers)
        self.assertEqual(add_prog_res.status_code, 200)

        # 6. Refrescar token
        if refresh_token:
            refresh_res = self.client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
            self.assertEqual(refresh_res.status_code, 200)
            self.assertIn("access_token", refresh_res.json())

        # 7. Logout
        logout_res = self.client.post("/api/auth/logout", headers=headers)
        self.assertEqual(logout_res.status_code, 200)

    def test_rbac_admin_vs_lider(self):
        # 1. Login como Admin
        admin_login = self.client.post("/api/auth/login", json={
            "email": "admin@taskmetrics.com",
            "password": "admin123"
        })
        self.assertEqual(admin_login.status_code, 200)
        admin_token = admin_login.json()["access_token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        # 2. Admin puede listar usuarios
        res_users = self.client.get("/api/admin/users", headers=admin_headers)
        self.assertEqual(res_users.status_code, 200)

        # 3. Admin crea un nuevo Líder
        leader_email = "lider_capo@taskmetrics.com"
        create_user_res = self.client.post("/api/admin/users", json={
            "email": leader_email,
            "password": "password123",
            "name": "Capo Líder",
            "role": "lider"
        }, headers=admin_headers)
        self.assertEqual(create_user_res.status_code, 200)

        # 4. Login como Líder
        leader_login = self.client.post("/api/auth/login", json={
            "email": leader_email,
            "password": "password123"
        })
        self.assertEqual(leader_login.status_code, 200)
        leader_token = leader_login.json()["access_token"]
        leader_headers = {"Authorization": f"Bearer {leader_token}"}

        # 5. Líder SÍ puede ver métricas y crear tareas
        leader_metrics = self.client.get("/api/metrics", headers=leader_headers)
        self.assertEqual(leader_metrics.status_code, 200)

        # 6. Líder NO puede acceder al módulo de administración de usuarios (debe dar 403 Forbidden)
        leader_admin_attempt = self.client.get("/api/admin/users", headers=leader_headers)
        self.assertEqual(leader_admin_attempt.status_code, 403)
        self.assertIn("Acceso restringido", leader_admin_attempt.json()["detail"])

        # Tampoco puede crear usuarios
        leader_create_attempt = self.client.post("/api/admin/users", json={
            "email": "hacker@test.com",
            "password": "password123",
            "name": "Hacker",
            "role": "admin"
        }, headers=leader_headers)
        self.assertEqual(leader_create_attempt.status_code, 403)



if __name__ == "__main__":
    unittest.main()

