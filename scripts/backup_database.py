import os
import sys
import json
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import create_app, db
from sqlalchemy import text

app = create_app()

def backup_database():
    backup_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backups'))
    os.makedirs(backup_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = os.path.join(backup_dir, f'pre_migration_phase1_backup_{timestamp}.json')
    
    with app.app_context():
        inspector = db.inspect(db.engine)
        tables = inspector.get_table_names()
        
        backup_payload = {
            'timestamp': timestamp,
            'tables': {}
        }
        
        for table in tables:
            # We backup structure and data
            columns = [c['name'] for c in inspector.get_columns(table)]
            # For prospects, if large, backup count and sample or all?
            # 17152 rows in prospects is ~10-15MB JSON, which is very fast and safe to backup.
            rows = db.session.execute(text(f"SELECT * FROM `{table}`")).fetchall()
            
            serialized_rows = []
            for r in rows:
                row_dict = {}
                for k, v in r._mapping.items():
                    if isinstance(v, datetime):
                        row_dict[k] = v.isoformat()
                    else:
                        row_dict[k] = v
                serialized_rows.append(row_dict)
                
            backup_payload['tables'][table] = {
                'columns': columns,
                'row_count': len(serialized_rows),
                'rows': serialized_rows
            }
            print(f"Backed up `{table}`: {len(serialized_rows)} rows")
            
        with open(backup_file, 'w', encoding='utf-8') as f:
            json.dump(backup_payload, f, ensure_ascii=False, indent=2)
            
        file_size_mb = os.path.getsize(backup_file) / (1024 * 1024)
        print(f"\n[SUCCESS] Full database backup saved to: {backup_file} ({file_size_mb:.2f} MB)")
        return backup_file

if __name__ == '__main__':
    backup_database()
