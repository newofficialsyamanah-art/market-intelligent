import os
import sys
import json
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import create_app, db
from sqlalchemy import text

app = create_app()

with app.app_context():
    print("=== Current Database Inspection ===")
    inspector = db.inspect(db.engine)
    tables = inspector.get_table_names()
    print(f"Tables in DB: {tables}")
    
    backup_data = {}
    for table in tables:
        count = db.session.execute(text(f"SELECT COUNT(*) FROM `{table}`")).scalar()
        print(f"Table `{table}`: {count} rows")
        # Fetch existing columns
        columns = [col['name'] for col in inspector.get_columns(table)]
        print(f"  Columns: {columns}")
        
    print("\nBackup inspection completed.")
