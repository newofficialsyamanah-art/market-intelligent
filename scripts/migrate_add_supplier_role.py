import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app, db
from sqlalchemy import text

app = create_app()

with app.app_context():
    dialect = db.engine.dialect.name
    print(f"Adding 'supplier' role to database (dialect: {dialect})...")
    with db.engine.begin() as connection:
        if dialect == "postgresql":
            connection.execute(text("ALTER TYPE role_enum ADD VALUE IF NOT EXISTS 'supplier'"))
        elif dialect == "mysql":
            connection.execute(text(
                "ALTER TABLE users MODIFY COLUMN role "
                "ENUM('admin','business_analyst','marketing','management','procurement','supplier') "
                "NOT NULL DEFAULT 'business_analyst'"
            ))
        elif dialect == "sqlite":
            pass
        else:
            raise RuntimeError(f"Unsupported database dialect: {dialect}")
    print("[OK] Supplier role successfully added to database enum.")
