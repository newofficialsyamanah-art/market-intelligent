import os
import sys
from datetime import datetime
from sqlalchemy import text, inspect

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import create_app, db

def get_existing_columns(inspector, table_name):
    try:
        return [col['name'] for col in inspector.get_columns(table_name)]
    except Exception:
        return []

def run_migration_for_app(app_instance, db_label="Main DB"):
    print(f"\n=== MIGRATING {db_label} ===")
    with app_instance.app_context():
        conn = db.engine.connect()
        trans = conn.begin()
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()

        try:
            # 1. Update `campaigns` table
            print("\n1. Checking `campaigns` columns...")
            if 'campaigns' in tables:
                camp_cols = get_existing_columns(inspector, 'campaigns')
                new_camp_cols = [
                    ('description', 'TEXT NULL'),
                    ('product', 'VARCHAR(150) NULL DEFAULT "Jersey / Custom Teamwear"'),
                    ('target_segment', 'VARCHAR(150) NULL'),
                    ('organization_type', 'VARCHAR(100) NULL'),
                    ('province', 'VARCHAR(100) NULL'),
                    ('city', 'VARCHAR(100) NULL'),
                    ('start_date', 'DATETIME NULL'),
                    ('end_date', 'DATETIME NULL'),
                    ('channel', 'VARCHAR(100) NULL'),
                    ('notes', 'TEXT NULL'),
                    ('updated_at', 'DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'),
                ]
                for col_name, col_type in new_camp_cols:
                    if col_name not in camp_cols:
                        print(f"  - Adding column `{col_name}` ({col_type}) to `campaigns`...")
                        conn.execute(text(f"ALTER TABLE `campaigns` ADD COLUMN `{col_name}` {col_type}"))
                    else:
                        print(f"  - Column `{col_name}` already exists on `campaigns`.")
            else:
                print("  - Table `campaigns` not found.")

            # 2. Create `campaign_targets` table
            print("\n2. Checking `campaign_targets` table...")
            tables = inspect(db.engine).get_table_names()
            if 'campaign_targets' not in tables:
                print("  - Creating table `campaign_targets`...")
                conn.execute(text("""
                    CREATE TABLE `campaign_targets` (
                        `id` INT AUTO_INCREMENT PRIMARY KEY,
                        `campaign_id` INT NOT NULL,
                        `organization_id` INT NOT NULL,
                        `product_fit_snapshot` VARCHAR(255) NULL,
                        `opportunity_score_snapshot` INT DEFAULT 0,
                        `status` VARCHAR(50) DEFAULT 'targeted',
                        `notes` TEXT NULL,
                        `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
                        CONSTRAINT `fk_ct_campaign` FOREIGN KEY (`campaign_id`) REFERENCES `campaigns` (`id`) ON DELETE CASCADE,
                        CONSTRAINT `fk_ct_org` FOREIGN KEY (`organization_id`) REFERENCES `organizations` (`id`) ON DELETE CASCADE,
                        UNIQUE KEY `uq_campaign_target_org` (`campaign_id`, `organization_id`),
                        KEY `idx_ct_campaign` (`campaign_id`),
                        KEY `idx_ct_org` (`organization_id`)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
                """))
            else:
                print("  - Table `campaign_targets` already exists.")

            # 3. Update `organizations` table
            print("\n3. Checking `organizations` columns...")
            if 'organizations' in tables:
                org_cols = get_existing_columns(inspector, 'organizations')
                new_org_cols = [
                    ('ai_scoring_json', 'TEXT NULL'),
                    ('sport', 'VARCHAR(100) NULL'),
                    ('organization_subtype', 'VARCHAR(100) NULL'),
                ]
                for col_name, col_type in new_org_cols:
                    if col_name not in org_cols:
                        print(f"  - Adding column `{col_name}` ({col_type}) to `organizations`...")
                        conn.execute(text(f"ALTER TABLE `organizations` ADD COLUMN `{col_name}` {col_type}"))
                    else:
                        print(f"  - Column `{col_name}` already exists on `organizations`.")
            else:
                print("  - Table `organizations` not found.")

            # 4. Update `cron_jobs` table
            print("\n4. Checking `cron_jobs` columns...")
            if 'cron_jobs' in tables:
                cron_cols = get_existing_columns(inspector, 'cron_jobs')
                new_cron_cols = [
                    ('duration_seconds', 'FLOAT NULL'),
                    ('records_processed', 'INT DEFAULT 0'),
                    ('success_count', 'INT DEFAULT 0'),
                    ('failed_count', 'INT DEFAULT 0'),
                    ('error_summary', 'TEXT NULL'),
                    ('next_run', 'DATETIME NULL'),
                ]
                for col_name, col_type in new_cron_cols:
                    if col_name not in cron_cols:
                        print(f"  - Adding column `{col_name}` ({col_type}) to `cron_jobs`...")
                        conn.execute(text(f"ALTER TABLE `cron_jobs` ADD COLUMN `{col_name}` {col_type}"))
                    else:
                        print(f"  - Column `{col_name}` already exists on `cron_jobs`.")
            else:
                print("  - Table `cron_jobs` not found.")

            trans.commit()
            print(f"[SUCCESS] Migration completed for {db_label}!")
        except Exception as e:
            trans.rollback()
            print(f"[ERROR] Migration failed for {db_label}: {e}")
            raise e
        finally:
            conn.close()

def upgrade():
    # 1. Migrate Main DB
    app_main = create_app()
    run_migration_for_app(app_main, "Main Database (market_intelligence)")

    # 2. Migrate Test DB
    os.environ["FLASK_ENV"] = "testing"
    os.environ["TESTING"] = "1"
    app_test = create_app()
    run_migration_for_app(app_test, "Test Database (market_intelligence_test)")

if __name__ == '__main__':
    upgrade()
