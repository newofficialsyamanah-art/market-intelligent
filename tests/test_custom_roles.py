import unittest

from app import create_app
from app.config import TestConfig
from app.extensions import db
from app.models import CustomRole, User


class TestCustomRoles(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app.config["TESTING"] = True
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.client = self.app.test_client()
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()

        self.admin = User.query.filter_by(email="custom_role_admin@example.com").first()
        if not self.admin:
            self.admin = User(name="Role Admin", email="custom_role_admin@example.com", role="admin")
            self.admin.set_password("Secret123!")
            db.session.add(self.admin)
        db.session.commit()

    def tearDown(self):
        db.session.rollback()
        self.context.pop()

    def login_admin(self):
        return self.client.post("/login", data={
            "email": self.admin.email,
            "password": "Secret123!",
        })

    def test_create_role_requires_program_access(self):
        self.login_admin()
        response = self.client.post("/admin/roles/new", data={
            "name": "Role Kosong",
            "key": "role_kosong",
        })
        self.assertEqual(response.status_code, 302)
        self.assertIsNone(CustomRole.query.filter_by(key="role_kosong").first())

    def test_create_and_assign_custom_role(self):
        self.login_admin()
        response = self.client.post("/admin/roles/new", data={
            "name": "Auditor Marketing",
            "key": "auditor_marketing",
            "permissions": ["marketing"],
        })
        self.assertEqual(response.status_code, 302)

        role = CustomRole.query.filter_by(key="auditor_marketing").first()
        self.assertIsNotNone(role)
        self.assertIn("marketing", role.permissions)

        page = self.client.get("/admin/users")
        self.assertEqual(page.status_code, 200)
        html = page.get_data(as_text=True)
        self.assertIn('data-bs-target="#createRoleModal"', html)
        self.assertIn('id="createRoleModal"', html)
        for builtin_role in (
            "admin", "business_analyst", "marketing", "management", "procurement", "supplier",
        ):
            self.assertGreaterEqual(html.count(f'value="{builtin_role}"'), 2)
        self.assertGreaterEqual(html.count('value="auditor_marketing"'), 2)

        self.client.post("/admin/users/new", data={
            "name": "Auditor",
            "email": "auditor@example.com",
            "password": "Secret123!",
            "role": "auditor_marketing",
        })
        user = User.query.filter_by(email="auditor@example.com").first()
        self.assertIsNotNone(user)
        self.assertEqual(user.role, "auditor_marketing")

        response = self.client.get("/logout")
        self.assertIn(response.status_code, (302, 200))
        login = self.client.post("/login", data={
            "email": "auditor@example.com",
            "password": "Secret123!",
        })
        self.assertEqual(login.status_code, 302)

        self.assertEqual(self.client.get("/marketing/dashboard").status_code, 200)
        self.assertEqual(self.client.get("/admin/users").status_code, 403)


if __name__ == "__main__":
    unittest.main()
