import unittest
from fastapi.testclient import TestClient

from src.web.app import create_app

ADMIN = {"email": "admin@taskmetrics.com", "password": "admin123"}


class TestAuthAndAreas(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(create_app())

    def login(self, email, password):
        res = self.client.post("/api/auth/login", json={"email": email, "password": password})
        self.assertEqual(res.status_code, 200, res.text)
        return {"Authorization": f"Bearer {res.json()['access_token']}"}, res.json()

    def ensure_leader(self, email, area, password="password123"):
        admin_headers, _ = self.login(**ADMIN)
        res = self.client.post("/api/admin/users", json={
            "email": email, "password": password, "name": email.split("@")[0], "role": "lider", "area": area
        }, headers=admin_headers)
        self.assertIn(res.status_code, [200, 400], res.text)
        return self.login(email, password)[0]

    def test_unauthenticated_request_rejected(self):
        res = self.client.get("/api/metrics")
        self.assertEqual(res.status_code, 401)
        self.assertIn("No autorizado", res.json().get("detail", ""))

        self.assertEqual(self.client.get("/api/sprints").status_code, 401)
        self.assertEqual(self.client.get("/api/programmers").status_code, 401)
        self.assertEqual(self.client.get("/api/areas").status_code, 401)
        self.assertEqual(self.client.post("/api/programmers", json={"name": "Hacker"}).status_code, 401)

    def test_invalid_or_forged_token_rejected(self):
        for token in ("token-falso-invalido", "dev-token-admin@taskmetrics.com", "dev-token-nadie_admin@x.com"):
            headers = {"Authorization": f"Bearer {token}"}
            self.assertEqual(self.client.get("/api/metrics", headers=headers).status_code, 401)
            self.assertEqual(self.client.get("/api/admin/users", headers=headers).status_code, 401)

    def test_public_registration_is_closed(self):
        res = self.client.post("/api/auth/register", json={"email": "intruso@x.com", "password": "123456"})
        self.assertIn(res.status_code, [404, 405])
        login = self.client.post("/api/auth/login", json={"email": "intruso@x.com", "password": "123456"})
        self.assertEqual(login.status_code, 401)

    def test_wrong_password_rejected(self):
        res = self.client.post("/api/auth/login", json={"email": ADMIN["email"], "password": "incorrecta"})
        self.assertEqual(res.status_code, 401)

    def test_auth_status_endpoint(self):
        res = self.client.get("/api/auth/status")
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.json()["supabase_configured"])

    def test_session_flow(self):
        headers = self.ensure_leader("lider_sesion@taskmetrics.com", "builder")
        _, session = self.login("lider_sesion@taskmetrics.com", "password123")

        me = self.client.get("/api/auth/me", headers=headers)
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()["user"]["area"], "builder")
        self.assertNotIn("token", me.json()["user"])

        refreshed = self.client.post("/api/auth/refresh", json={"refresh_token": session["refresh_token"]})
        self.assertEqual(refreshed.status_code, 200)
        self.assertIn("access_token", refreshed.json())

        self.assertEqual(self.client.post("/api/auth/logout", headers=headers).status_code, 200)
        self.assertEqual(self.client.get("/api/auth/me", headers=headers).status_code, 401)

    def test_only_admin_manages_users(self):
        admin_headers, _ = self.login(**ADMIN)
        self.assertEqual(self.client.get("/api/admin/users", headers=admin_headers).status_code, 200)

        leader_headers = self.ensure_leader("lider_capo@taskmetrics.com", "blockbench")
        self.assertEqual(self.client.get("/api/metrics", headers=leader_headers).status_code, 200)

        attempt = self.client.get("/api/admin/users", headers=leader_headers)
        self.assertEqual(attempt.status_code, 403)
        self.assertIn("Acceso restringido", attempt.json()["detail"])

        create_attempt = self.client.post("/api/admin/users", json={
            "email": "hacker@test.com", "password": "password123", "name": "Hacker", "role": "admin"
        }, headers=leader_headers)
        self.assertEqual(create_attempt.status_code, 403)

    def test_leader_requires_valid_area(self):
        admin_headers, _ = self.login(**ADMIN)
        for area in (None, "inexistente"):
            res = self.client.post("/api/admin/users", json={
                "email": "sin_area@taskmetrics.com", "password": "password123", "name": "Sin Área",
                "role": "lider", "area": area
            }, headers=admin_headers)
            self.assertEqual(res.status_code, 400, res.text)

    def test_duplicate_email_rejected(self):
        admin_headers, _ = self.login(**ADMIN)
        payload = {"email": "repetido@taskmetrics.com", "password": "password123", "name": "Uno",
                   "role": "lider", "area": "doblaje"}
        self.client.post("/api/admin/users", json=payload, headers=admin_headers)
        again = self.client.post("/api/admin/users", json=payload, headers=admin_headers)
        self.assertEqual(again.status_code, 400)

    def test_leaders_only_see_their_own_area(self):
        builder = self.ensure_leader("lider_builder@taskmetrics.com", "builder")
        doblaje = self.ensure_leader("lider_doblaje@taskmetrics.com", "doblaje")

        sprint = {"sprint_number": 1, "name": "Sprint Builder", "status": "completed", "tasks": [
            {"title": "Spawn", "status": "completed", "assigned_programmers": ["Solo Builder"]}
        ]}
        self.assertEqual(self.client.post("/api/sprints", json=sprint, headers=builder).status_code, 200)

        # Otra área no ve nada, ni pidiendo el área ajena por parámetro
        for url in ("/api/programmers", "/api/programmers?area=builder"):
            names = [p["name"] for p in self.client.get(url, headers=doblaje).json()]
            self.assertNotIn("Solo Builder", names)
        self.assertEqual(self.client.get("/api/sprints/1?area=builder", headers=doblaje).status_code, 404)
        self.assertEqual(self.client.get("/api/metrics?area=builder", headers=doblaje).json()["area"], "doblaje")
        self.assertEqual(self.client.delete("/api/sprints/1?area=builder", headers=doblaje).status_code, 404)

        # El mismo número de sprint y el mismo nombre pueden existir en otra área
        sprint_doblaje = {"sprint_number": 1, "name": "Sprint Doblaje", "status": "completed", "tasks": [
            {"title": "Voces", "status": "completed", "assigned_programmers": ["Solo Builder", "Voz"]}
        ]}
        self.assertEqual(self.client.post("/api/sprints", json=sprint_doblaje, headers=doblaje).status_code, 200)
        builder_metrics = self.client.get("/api/metrics", headers=builder).json()
        self.assertEqual(builder_metrics["programmers"], ["Solo Builder"])
        self.assertEqual(builder_metrics["sprint_names"]["1"], "Sprint Builder")
        self.assertEqual(builder_metrics["matrix"][0]["percentage"], 100.0)

        # El admin consulta cualquier área
        admin_headers, _ = self.login(**ADMIN)
        admin_view = self.client.get("/api/metrics?area=doblaje", headers=admin_headers).json()
        self.assertEqual(sorted(admin_view["programmers"]), ["Solo Builder", "Voz"])
        self.assertEqual(self.client.get("/api/metrics?area=nope", headers=admin_headers).status_code, 400)
        areas = self.client.get("/api/areas", headers=admin_headers).json()["areas"]
        self.assertTrue({"diseñador", "blockbench", "builder", "doblaje"} <= set(areas))
        self.assertEqual(self.client.get("/api/areas", headers=builder).json()["areas"], ["builder"])

    def test_admin_edits_and_deactivates_user(self):
        admin_headers, admin_session = self.login(**ADMIN)
        headers = self.ensure_leader("lider_editable@taskmetrics.com", "builder")
        users = self.client.get("/api/admin/users", headers=admin_headers).json()
        target = next(u for u in users if u["email"] == "lider_editable@taskmetrics.com")

        res = self.client.put(f"/api/admin/users/{target['id']}", json={
            "area": "doblaje", "password": "nuevaClave123"
        }, headers=admin_headers)
        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual(self.client.get("/api/auth/me", headers=headers).json()["user"]["area"], "doblaje")
        old = self.client.post("/api/auth/login", json={"email": target["email"], "password": "password123"})
        self.assertEqual(old.status_code, 401)
        self.login(target["email"], "nuevaClave123")

        self.client.put(f"/api/admin/users/{target['id']}", json={"active": False}, headers=admin_headers)
        self.assertEqual(self.client.get("/api/auth/me", headers=headers).status_code, 401)
        blocked = self.client.post("/api/auth/login", json={"email": target["email"], "password": "nuevaClave123"})
        self.assertEqual(blocked.status_code, 401)

        # El admin no puede dejarse sin acceso a sí mismo
        own_id = admin_session["user"]["id"]
        for change in ({"role": "lider", "area": "builder"}, {"active": False}):
            res = self.client.put(f"/api/admin/users/{own_id}", json=change, headers=admin_headers)
            self.assertEqual(res.status_code, 400)
        self.assertEqual(self.client.delete(f"/api/admin/users/{own_id}", headers=admin_headers).status_code, 400)

        self.assertEqual(self.client.delete(f"/api/admin/users/{target['id']}", headers=admin_headers).status_code, 200)
        self.assertEqual(self.client.delete(f"/api/admin/users/{target['id']}", headers=admin_headers).status_code, 404)


if __name__ == "__main__":
    unittest.main()
