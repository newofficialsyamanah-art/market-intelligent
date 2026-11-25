import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import text
from app import create_app
from app.extensions import db


app = create_app()

with app.app_context():
    db.create_all()
    dialect = db.engine.dialect.name
    with db.engine.begin() as connection:
        if dialect == "mysql":
            connection.execute(text(
                "ALTER TABLE users MODIFY COLUMN role "
                "VARCHAR(100) NOT NULL DEFAULT 'business_analyst'"
            ))
        elif dialect == "postgresql":
            connection.execute(text(
                "ALTER TABLE users ALTER COLUMN role TYPE VARCHAR(100) "
                "USING role::text"
            ))
        elif dialect not in {"sqlite"}:
            raise RuntimeError(f"Unsupported database dialect: {dialect}")
    print("[OK] Custom role schema is ready.")
