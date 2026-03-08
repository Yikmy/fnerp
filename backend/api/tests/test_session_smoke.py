import json

from django.contrib.auth import get_user_model
from django.test import Client, TestCase


class SessionAuthSmokeTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.username = "root"
        self.password = "pass123456"
        get_user_model().objects.create_superuser(
            username=self.username,
            password=self.password,
            email="root@example.com",
        )

    def test_session_cookie_auth_flow(self):
        login_response = self.client.post(
            "/api/auth/login/",
            data=json.dumps({"username": self.username, "password": self.password}),
            content_type="application/json",
        )
        self.assertEqual(login_response.status_code, 200)
        self.assertIn("sessionid", login_response.cookies)
        self.assertIn("sessionid", self.client.cookies)

        login_payload = login_response.json()
        self.assertTrue(login_payload["success"])
        self.assertTrue(login_payload["data"]["is_authenticated"])

        session_response = self.client.get("/api/auth/session/")
        self.assertEqual(session_response.status_code, 200)
        session_payload = session_response.json()
        self.assertTrue(session_payload["success"])
        self.assertTrue(session_payload["data"]["is_authenticated"])
        self.assertEqual(session_payload["data"]["user"]["username"], self.username)

        logout_response = self.client.post("/api/auth/logout/")
        self.assertEqual(logout_response.status_code, 200)
        logout_payload = logout_response.json()
        self.assertTrue(logout_payload["success"])
        self.assertFalse(logout_payload["data"]["is_authenticated"])

        session_after_logout_response = self.client.get("/api/auth/session/")
        self.assertEqual(session_after_logout_response.status_code, 401)
        after_logout_payload = session_after_logout_response.json()
        self.assertFalse(after_logout_payload["success"])
        self.assertEqual(after_logout_payload["error"]["code"], "authentication_required")
