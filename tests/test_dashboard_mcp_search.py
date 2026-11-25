import unittest
from unittest.mock import patch

from app import create_app
from app.config import TestConfig
from app.extensions import db
from app.models import User


class IsolatedTestConfig(TestConfig):
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


class TestDashboardMcpSearch(unittest.TestCase):
    def setUp(self):
        self.app = create_app(IsolatedTestConfig)
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        user = User(name="Dashboard Search", email="dashboard-search@example.com", role="business_analyst")
        user.set_password("Secret123!")
        db.session.add(user)
        db.session.commit()

        with self.client.session_transaction() as session:
            session["_user_id"] = str(user.id)
            session["_fresh"] = True

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
        self.app_context.pop()

    @patch("app.services.mcp_service.mcp_search_duckduckgo")
    def test_dashboard_search_uses_mcp_and_shows_web_results(self, search):
        search.return_value = [
            {
                "title": "EO Jakarta",
                "url": "https://example.com/eo",
                "snippet": "Event organizer",
            },
            {"title": "Unsafe link", "url": "javascript:alert(1)", "snippet": ""},
        ]

        response = self.client.get("/", query_string={"q": "EO Jakarta"})

        self.assertEqual(response.status_code, 200)
        search.assert_called_once_with("EO Jakarta", max_results=10, region="id-id")
        self.assertIn(b"EO Jakarta", response.data)
        self.assertIn(b"Cari via MCP", response.data)
        self.assertNotIn(b"javascript:alert", response.data)

    @patch("app.services.mcp_service.mcp_search_duckduckgo")
    def test_dashboard_search_rejects_overlong_query(self, search):
        response = self.client.get("/", query_string={"q": "x" * 201})

        self.assertEqual(response.status_code, 200)
        search.assert_not_called()
        self.assertIn("Kata kunci maksimal 200 karakter.".encode(), response.data)

    @patch("app.services.mcp_service.mcp_search_duckduckgo", side_effect=RuntimeError("MCP unavailable"))
    def test_dashboard_search_surfaces_mcp_errors(self, search):
        response = self.client.get("/", query_string={"q": "EO Jakarta"})

        self.assertEqual(response.status_code, 200)
        self.assertIn("Pencarian MCP sedang bermasalah.".encode(), response.data)


if __name__ == "__main__":
    unittest.main()
