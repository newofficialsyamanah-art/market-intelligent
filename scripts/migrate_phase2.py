import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import create_app, db
from sqlalchemy import text, inspect

app = create_app()

def get_existing_columns(inspector, table_name):
    return [col['name'] for col in inspector.get_columns(table_name)]

def upgrade():
    print("=== STARTING PHASE 2 DATABASE MIGRATION (UPGRADE) ===")
    with app.app_context():
        conn = db.engine.connect()
        trans = conn.begin()
        inspector = inspect(db.engine)
        
        try:
            # 1. Add provenance_json to organizations
            print("\n1. Checking `provenance_json` column on `organizations`...")
            org_cols = get_existing_columns(inspector, 'organizations')
            if 'provenance_json' not in org_cols:
                print("  - Adding column `provenance_json` (TEXT NULL) to `organizations`...")
                conn.execute(text("ALTER TABLE `organizations` ADD COLUMN `provenance_json` TEXT NULL"))
            else:
                print("  - Column `provenance_json` already exists, skipping.")

            # 2. Create duplicate_candidates table
            print("\n2. Checking `duplicate_candidates` table...")
            tables = inspector.get_table_names()
            if 'duplicate_candidates' not in tables:
                print("  - Creating table `duplicate_candidates`...")
                conn.execute(text("""
                    CREATE TABLE `duplicate_candidates` (
                        `id` INT AUTO_INCREMENT PRIMARY KEY,
                        `organization_id` INT NOT NULL,
                        `candidate_name` VARCHAR(255) NOT NULL,
                        `candidate_source` VARCHAR(100) NULL,
                        `candidate_payload_json` TEXT NULL,
                        `match_tier` VARCHAR(50) NOT NULL,
                        `confidence_score` FLOAT NOT NULL,
                        `status` ENUM('pending', 'approved', 'rejected') NOT NULL DEFAULT 'pending',
                        `reviewed_by` INT NULL,
                        `reviewed_at` DATETIME NULL,
                        `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
                        CONSTRAINT `fk_dc_org` FOREIGN KEY (`organization_id`) REFERENCES `organizations` (`id`) ON DELETE CASCADE,
                        CONSTRAINT `fk_dc_user` FOREIGN KEY (`reviewed_by`) REFERENCES `users` (`id`) ON DELETE SET NULL,
                        KEY `idx_dc_status` (`status`),
                        KEY `idx_dc_org` (`organization_id`)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
                """))
            else:
                print("  - Table `duplicate_candidates` already exists, skipping.")

            trans.commit()
            print("\n[SUCCESS] Phase 2 Database Migration completed successfully!")
        except Exception as e:
            trans.rollback()
            print(f"\n[ERROR] Migration failed: {e}")
            raise e
        finally:
            conn.close()

def downgrade():
    print("=== STARTING PHASE 2 DATABASE MIGRATION (DOWNGRADE) ===")
    with app.app_context():
        conn = db.engine.connect()
        trans = conn.begin()
        inspector = inspect(db.engine)
        
        try:
            # 1. Drop duplicate_candidates
            if 'duplicate_candidates' in inspector.get_table_names():
                print("  - Dropping table `duplicate_candidates`...")
                conn.execute(text("DROP TABLE IF EXISTS `duplicate_candidates`"))

            # 2. Drop provenance_json from organizations
            org_cols = get_existing_columns(inspector, 'organizations')
            if 'provenance_json' in org_cols:
                print("  - Dropping column `provenance_json` from `organizations`...")
                conn.execute(text("ALTER TABLE `organizations` DROP COLUMN `provenance_json`"))

            trans.commit()
            print("\n[SUCCESS] Reverted Phase 2 migration successfully!")
        except Exception as e:
            trans.rollback()
            print(f"\n[ERROR] Downgrade failed: {e}")
            raise e
        finally:
            conn.close()

if __name__ == '__main__':
    action = sys.argv[1] if len(sys.argv) > 1 else 'upgrade'
    if action == 'downgrade':
        downgrade()
    else:
        upgrade()
