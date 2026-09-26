"""Test Suite untuk Fase 7: Authentication, RBAC Hardening, & Final Integration.

Memverifikasi:
1. Akses Admin: Superuser memiliki akses ke seluruh workspace dan panel admin.
2. Akses Business Analyst: Akses ke Company, Event, Marketing; 403 Forbidden ke Admin panel.
3. Akses Marketing: Akses ke Marketing, Event, Company detail; 403 Forbidden ke Admin panel.
4. Akses Management: Akses ke Reporting & executive dashboard; 403 Forbidden ke Admin panel.
5. Proteksi Pengguna Non-Aktif: Pengguna dengan is_active_flag=False ditolak login.
6. Proteksi Unauthenticated: Akses langsung tanpa login dialihkan (302) ke /login.
7. Integritas Navigasi Terpadu: Seluruh endpoint utama merespons tanpa broken routes / 500 error.
"""

import unittest
from app import create_app
from app.extensions import db
from app.models import User, Organization, Event, EventParticipant, utc_now
from app.config import TestConfig


class TestPhase7RBACIntegration(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app.config["TESTING"] = True
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Siapkan 4 user dengan role berbeda
        self.users = {}
        role_configs = [
            ("admin", "admin_phase7@example.com", "Admin P7"),
            ("business_analyst", "ba_phase7@example.com", "BA P7"),
            ("marketing", "mkt_phase7@example.com", "Marketing P7"),
            ("management", "mgmt_phase7@example.com", "Management P7"),
        ]

        for role, email, name in role_configs:
            u = User.query.filter_by(email=email).first()
            if not u:
                u = User(name=name, email=email, role=role, is_active_flag=True)
                db.session.add(u)
            u.set_password("Secret123!")
            u.is_active_flag = True
            self.users[role] = u

        # User tidak aktif
        inactive_u = User.query.filter_by(email="inactive_phase7@example.com").first()
        if not inactive_u:
            inactive_u = User(name="Inactive User", email="inactive_phase7@example.com", role="marketing", is_active_flag=False)
            db.session.add(inactive_u)
        inactive_u.set_password("Secret123!")
        inactive_u.is_active_flag = False
        self.users["inactive"] = inactive_u

        # Seed 1 org untuk test detail
        self.org = Organization.query.filter_by(name="[TEST] PT RBAC Verified").first()
        if not self.org:
            self.org = Organization(
                name="[TEST] PT RBAC Verified",
                industry="Testing",
                priority_tier="B - WARM",
                opportunity_score=70,
                created_at=utc_now()
            )
            db.session.add(self.org)

        db.session.commit()

    def tearDown(self):
        db.session.rollback()
        self.app_context.pop()

    def test_01_unauthenticated_access(self):
        """Memverifikasi pengguna tanpa sesi diarahkan ke halaman login (302)."""
        client = self.app.test_client()
        protected_routes = [
            "/market-analysis/",
            "/events/",
            "/marketing/dashboard",
            "/admin/",
            "/admin/users",
        ]
        for route in protected_routes:
            res = client.get(route)
            self.assertEqual(res.status_code, 302, f"Route {route} harus me-redirect unauthenticated access")
            self.assertIn("/login", res.headers.get("Location", ""))

    def test_02_admin_superuser_access(self):
        """Memverifikasi Admin memiliki akses penuh ke seluruh workspace."""
        client = self.app.test_client()
        res_login = client.post("/login", data={"email": self.users["admin"].email, "password": "Secret123!"})
        self.assertEqual(res_login.status_code, 302)

        routes = [
            "/admin/",
            "/admin/users",
            "/admin/cron-jobs",
            "/market-analysis/",
            "/market-analysis/explorer",
            "/events/",
            "/events/calendar",
            "/marketing/dashboard",
            "/marketing/targets",
            "/marketing/segments",
        ]
        for route in routes:
            res = client.get(route)
            self.assertEqual(res.status_code, 200, f"Admin harus dapat mengakses {route}")

    def test_03_business_analyst_access_and_restrictions(self):
        """Memverifikasi Business Analyst dapat mengakses analitik, tetapi 403 ke Admin panel."""
        client = self.app.test_client()
        res_login = client.post("/login", data={"email": self.users["business_analyst"].email, "password": "Secret123!"})
        self.assertEqual(res_login.status_code, 302)

        # Akses yang diizinkan (200)
        allowed = [
            "/market-analysis/",
            "/market-analysis/explorer",
            f"/market-analysis/organization/{self.org.id}",
            "/events/",
            "/events/calendar",
            "/marketing/dashboard",
            "/marketing/targets",
            "/marketing/segments",
        ]
        for route in allowed:
            res = client.get(route)
            self.assertEqual(res.status_code, 200, f"BA harus dapat mengakses {route}")

        # Akses terlarang ke panel admin (403 Forbidden)
        forbidden = [
            "/admin/",
            "/admin/users",
            "/admin/cron-jobs",
            "/admin/monitoring",
            "/admin/logs",
            "/admin/ai-config",
        ]
        for route in forbidden:
            res = client.get(route)
            self.assertEqual(res.status_code, 403, f"BA tidak boleh mengakses {route} (harus 403)")

    def test_04_marketing_access_and_restrictions(self):
        """Memverifikasi Marketing dapat mengakses workspace marketing, event, dan org detail; 403 ke Admin."""
        client = self.app.test_client()
        res_login = client.post("/login", data={"email": self.users["marketing"].email, "password": "Secret123!"})
        self.assertEqual(res_login.status_code, 302)

        # Akses yang diizinkan (200)
        allowed = [
            "/marketing/dashboard",
            "/marketing/targets",
            "/marketing/segments",
            "/events/",
            "/events/calendar",
            "/market-analysis/explorer",
            f"/market-analysis/organization/{self.org.id}",
        ]
        for route in allowed:
            res = client.get(route)
            self.assertEqual(res.status_code, 200, f"Marketing harus dapat mengakses {route}")

        # Akses terlarang ke admin panel (403 Forbidden)
        forbidden = [
            "/admin/",
            "/admin/users",
            "/admin/cron-jobs",
            "/admin/logs",
        ]
        for route in forbidden:
            res = client.get(route)
            self.assertEqual(res.status_code, 403, f"Marketing tidak boleh mengakses {route} (harus 403)")

    def test_05_management_access_and_restrictions(self):
        """Memverifikasi Management dapat mengakses reporting dan overview, tetapi 403 ke Admin panel."""
        client = self.app.test_client()
        res_login = client.post("/login", data={"email": self.users["management"].email, "password": "Secret123!"})
        self.assertEqual(res_login.status_code, 302)

        allowed = [
            "/reporting/",
            "/market-analysis/",
            "/events/",
            "/marketing/dashboard",
        ]
        for route in allowed:
            res = client.get(route)
            self.assertEqual(res.status_code, 200, f"Management harus dapat mengakses {route}")

        forbidden = [
            "/admin/",
            "/admin/users",
        ]
        for route in forbidden:
            res = client.get(route)
            self.assertEqual(res.status_code, 403, f"Management tidak boleh mengakses {route} (harus 403)")

    def test_06_inactive_user_cannot_login(self):
        """Memverifikasi pengguna dengan is_active_flag=False tidak dapat masuk."""
        client = self.app.test_client()
        res = client.post("/login", data={"email": self.users["inactive"].email, "password": "Secret123!"})
        # Login form returns flash and remains on login or redirects to login
        self.assertIn(res.status_code, [200, 302])
        # Coba akses route terproteksi
        res_check = client.get("/marketing/dashboard")
        self.assertEqual(res_check.status_code, 302)
        self.assertIn("/login", res_check.headers.get("Location", ""))


if __name__ == "__main__":
    unittest.main()
