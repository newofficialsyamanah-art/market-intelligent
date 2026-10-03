import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import create_app, db
from sqlalchemy import text

app = create_app()

with app.app_context():
    print("=" * 80)
    print("MENERAPKAN VALIDASI INTEGRITAS & UNIQUE CONSTRAINTS DI DATABASE")
    print("=" * 80)

    statements = [
        # 1. Prospects: 1 Organisasi hanya boleh punya 1 Record Prospek
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_prospects_organization_id 
        ON prospects (organization_id) 
        WHERE organization_id IS NOT NULL;
        """,
        # 2. Prospects: Nama perusahaan unik (case-insensitive)
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_prospects_company_name_lower 
        ON prospects (LOWER(company_name));
        """,
        # 3. Procurement Suppliers: Kombinasi produk dan source_url unik
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_procurement_suppliers_product_url 
        ON procurement_suppliers (product, source_url);
        """,
        # 4. Events: Nama event unik (case-insensitive)
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_events_name_lower 
        ON events (LOWER(name));
        """,
        # 5. Event Participants: Unik untuk perpaduan event_id + organization_id + role
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_event_participants_event_org_role 
        ON event_participants (event_id, organization_id, role);
        """,
        # 6. Users: Email unik (case-insensitive)
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_users_email_lower 
        ON users (LOWER(email));
        """
    ]

    for stmt in statements:
        try:
            db.session.execute(text(stmt))
            db.session.commit()
            idx_name = stmt.strip().split()[3]
            print(f"[OK] Berhasil membuat index/constraint: {idx_name}")
        except Exception as e:
            db.session.rollback()
            print(f"[ERR] Gagal: {e}")

    print("\nVerifikasi Index Selesai.")
