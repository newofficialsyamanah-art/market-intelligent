"""Add the procurement role to existing MySQL or PostgreSQL databases."""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app, db
from sqlalchemy import text

app = create_app()

with app.app_context():
    dialect = db.engine.dialect.name
    with db.engine.begin() as connection:
        if dialect == "postgresql":
            connection.execute(text("ALTER TYPE role_enum ADD VALUE IF NOT EXISTS 'procurement'"))
        elif dialect == "mysql":
            connection.execute(text(
                "ALTER TABLE users MODIFY COLUMN role "
                "ENUM('admin','business_analyst','marketing','management','procurement') "
                "NOT NULL DEFAULT 'business_analyst'"
            ))
        else:
            raise RuntimeError(f"Unsupported database dialect: {dialect}")
    print(f"Procurement role added for {dialect}.")
