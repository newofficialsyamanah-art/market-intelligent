import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import create_app, db
from sqlalchemy import text, inspect

app = create_app()

def get_existing_columns(inspector, table_name):
    return [col['name'] for col in inspector.get_columns(table_name)]

def get_existing_indexes(inspector, table_name):
    return [idx['name'] for idx in inspector.get_indexes(table_name)]

def upgrade():
    print("=== STARTING PHASE 1 DATABASE MIGRATION (UPGRADE) ===")
    with app.app_context():
        conn = db.engine.connect()
        trans = conn.begin()
        inspector = inspect(db.engine)
        
        try:
            # 1. Update organizations table
            print("\n1. Migrating `organizations` table...")
            org_cols = get_existing_columns(inspector, 'organizations')
            org_indexes = get_existing_indexes(inspector, 'organizations')
            
            # Make source_url nullable
            print("  - Altering `source_url` to be nullable...")
            conn.execute(text("ALTER TABLE `organizations` MODIFY COLUMN `source_url` VARCHAR(500) NULL"))
            
            # Drop unique constraint on source_url if exists
            for idx in org_indexes:
                if 'uq_organization_source' in idx or 'source_url' in idx:
                    print(f"  - Dropping constraint/index `{idx}` from `organizations`...")
                    conn.execute(text(f"ALTER TABLE `organizations` DROP INDEX `{idx}`"))
            
            new_org_cols = [
                ("normalized_name", "VARCHAR(255) NULL"),
                ("domain", "VARCHAR(150) NULL"),
                ("product_fit", "VARCHAR(255) NULL"),
                ("opportunity_score", "INT DEFAULT 0"),
                ("priority_tier", "VARCHAR(10) NULL"),
                ("source_id", "INT NULL"),
                ("source_type", "VARCHAR(50) DEFAULT 'bps'"),
                ("data_freshness", "DATETIME NULL"),
                ("employee_size", "VARCHAR(50) NULL"),
            ]
            for col_name, col_def in new_org_cols:
                if col_name not in org_cols:
                    print(f"  - Adding column `{col_name}`...")
                    conn.execute(text(f"ALTER TABLE `organizations` ADD COLUMN `{col_name}` {col_def}"))
                else:
                    print(f"  - Column `{col_name}` already exists, skipping.")
                    
            # Re-inspect indexes after potential adds
            inspector = inspect(db.engine)
            org_indexes = get_existing_indexes(inspector, 'organizations')
            if 'idx_org_normalized_name' not in org_indexes:
                print("  - Adding index `idx_org_normalized_name`...")
                conn.execute(text("ALTER TABLE `organizations` ADD INDEX `idx_org_normalized_name` (`normalized_name`)"))
            if 'idx_org_domain' not in org_indexes:
                print("  - Adding index `idx_org_domain`...")
                conn.execute(text("ALTER TABLE `organizations` ADD INDEX `idx_org_domain` (`domain`)"))
            if 'idx_org_opportunity_score' not in org_indexes:
                print("  - Adding index `idx_org_opportunity_score`...")
                conn.execute(text("ALTER TABLE `organizations` ADD INDEX `idx_org_opportunity_score` (`opportunity_score`)"))
            if 'idx_org_priority_tier' not in org_indexes:
                print("  - Adding index `idx_org_priority_tier`...")
                conn.execute(text("ALTER TABLE `organizations` ADD INDEX `idx_org_priority_tier` (`priority_tier`)"))
            
            # Foreign key for source_id -> data_sources(id)
            fks = [fk['name'] for fk in inspector.get_foreign_keys('organizations')]
            if 'fk_org_source_id' not in fks:
                print("  - Adding FK `fk_org_source_id` on `organizations.source_id`...")
                conn.execute(text("ALTER TABLE `organizations` ADD CONSTRAINT `fk_org_source_id` FOREIGN KEY (`source_id`) REFERENCES `data_sources` (`id`) ON DELETE SET NULL"))

            # 2. Update events table
            print("\n2. Migrating `events` table...")
            event_cols = get_existing_columns(inspector, 'events')
            event_indexes = get_existing_indexes(inspector, 'events')
            
            # Make source_url nullable
            print("  - Altering `source_url` to be nullable...")
            conn.execute(text("ALTER TABLE `events` MODIFY COLUMN `source_url` VARCHAR(500) NULL"))
            
            # Drop unique constraint on source_url if exists
            for idx in event_indexes:
                if 'uq_event_source' in idx or 'source_url' in idx:
                    print(f"  - Dropping constraint/index `{idx}` from `events`...")
                    conn.execute(text(f"ALTER TABLE `events` DROP INDEX `{idx}`"))
                    
            new_event_cols = [
                ("organizer_id", "INT NULL"),
                ("status", "VARCHAR(50) DEFAULT 'upcoming'"),
                ("relevance_notes", "TEXT NULL")
            ]
            for col_name, col_def in new_event_cols:
                if col_name not in event_cols:
                    print(f"  - Adding column `{col_name}`...")
                    conn.execute(text(f"ALTER TABLE `events` ADD COLUMN `{col_name}` {col_def}"))
                else:
                    print(f"  - Column `{col_name}` already exists, skipping.")
                    
            inspector = inspect(db.engine)
            event_indexes = get_existing_indexes(inspector, 'events')
            if 'idx_events_status' not in event_indexes:
                print("  - Adding index `idx_events_status`...")
                conn.execute(text("ALTER TABLE `events` ADD INDEX `idx_events_status` (`status`)"))
                
            fks = [fk['name'] for fk in inspector.get_foreign_keys('events')]
            if 'fk_events_organizer_id' not in fks:
                print("  - Adding FK `fk_events_organizer_id` on `events.organizer_id`...")
                conn.execute(text("ALTER TABLE `events` ADD CONSTRAINT `fk_events_organizer_id` FOREIGN KEY (`organizer_id`) REFERENCES `organizations` (`id`) ON DELETE SET NULL"))

            # 3. Update prospects table (Compatibility layer)
            print("\n3. Migrating `prospects` table (Compatibility layer)...")
            prospect_cols = get_existing_columns(inspector, 'prospects')
            if 'organization_id' not in prospect_cols:
                print("  - Adding column `organization_id`...")
                conn.execute(text("ALTER TABLE `prospects` ADD COLUMN `organization_id` INT NULL"))
                conn.execute(text("ALTER TABLE `prospects` ADD INDEX `idx_prospects_org_id` (`organization_id`)"))
                conn.execute(text("ALTER TABLE `prospects` ADD CONSTRAINT `fk_prospects_org_id` FOREIGN KEY (`organization_id`) REFERENCES `organizations` (`id`) ON DELETE SET NULL"))
            else:
                print("  - Column `organization_id` already exists, skipping.")

            # 4. Create event_participants table
            print("\n4. Checking/Creating `event_participants` table...")
            tables = inspector.get_table_names()
            if 'event_participants' not in tables:
                print("  - Creating table `event_participants`...")
                conn.execute(text("""
                    CREATE TABLE `event_participants` (
                        `id` INT AUTO_INCREMENT PRIMARY KEY,
                        `event_id` INT NOT NULL,
                        `organization_id` INT NOT NULL,
                        `role` ENUM('organizer', 'exhibitor', 'sponsor', 'partner', 'speaker') NOT NULL,
                        `booth_number` VARCHAR(50) NULL,
                        `notes` TEXT NULL,
                        `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
                        CONSTRAINT `fk_ep_event` FOREIGN KEY (`event_id`) REFERENCES `events` (`id`) ON DELETE CASCADE,
                        CONSTRAINT `fk_ep_org` FOREIGN KEY (`organization_id`) REFERENCES `organizations` (`id`) ON DELETE CASCADE,
                        UNIQUE KEY `uq_event_org_role` (`event_id`, `organization_id`, `role`),
                        KEY `idx_ep_event` (`event_id`),
                        KEY `idx_ep_org` (`organization_id`)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
                """))
            else:
                print("  - Table `event_participants` already exists, skipping.")

            trans.commit()
            print("\n[SUCCESS] Phase 1 Database Migration completed successfully!")
            
        except Exception as e:
            trans.rollback()
            print(f"\n[ERROR] Migration failed: {e}")
            raise e
        finally:
            conn.close()

def downgrade():
    print("=== STARTING PHASE 1 DATABASE MIGRATION (DOWNGRADE / REVERT) ===")
    with app.app_context():
        conn = db.engine.connect()
        trans = conn.begin()
        inspector = inspect(db.engine)
        
        try:
            # 1. Drop event_participants
            if 'event_participants' in inspector.get_table_names():
                print("  - Dropping table `event_participants`...")
                conn.execute(text("DROP TABLE IF EXISTS `event_participants`"))
                
            # 2. Revert prospects
            prospect_cols = get_existing_columns(inspector, 'prospects')
            if 'organization_id' in prospect_cols:
                print("  - Dropping FK and column `organization_id` from `prospects`...")
                # Drop FK if exists
                try:
                    conn.execute(text("ALTER TABLE `prospects` DROP FOREIGN KEY `fk_prospects_org_id`"))
                except Exception:
                    pass
                conn.execute(text("ALTER TABLE `prospects` DROP COLUMN `organization_id`"))
                
            # 3. Revert events
            event_cols = get_existing_columns(inspector, 'events')
            if 'organizer_id' in event_cols:
                try:
                    conn.execute(text("ALTER TABLE `events` DROP FOREIGN KEY `fk_events_organizer_id`"))
                except Exception:
                    pass
                conn.execute(text("ALTER TABLE `events` DROP COLUMN `organizer_id`"))
            if 'status' in event_cols:
                conn.execute(text("ALTER TABLE `events` DROP COLUMN `status`"))
            if 'relevance_notes' in event_cols:
                conn.execute(text("ALTER TABLE `events` DROP COLUMN `relevance_notes`"))
                
            # 4. Revert organizations
            org_cols = get_existing_columns(inspector, 'organizations')
            if 'source_id' in org_cols:
                try:
                    conn.execute(text("ALTER TABLE `organizations` DROP FOREIGN KEY `fk_org_source_id`"))
                except Exception:
                    pass
            for col in ['normalized_name', 'domain', 'product_fit', 'opportunity_score', 'priority_tier', 'source_id', 'source_type', 'data_freshness', 'employee_size']:
                if col in org_cols:
                    conn.execute(text(f"ALTER TABLE `organizations` DROP COLUMN `{col}`"))
                    
            trans.commit()
            print("\n[SUCCESS] Reverted Phase 1 migration successfully!")
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
