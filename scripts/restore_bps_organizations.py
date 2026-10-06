import os
import sys
import json
import time
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app
from app.extensions import db
from app.models import Organization, DataSource
from sqlalchemy import text

def restore_bps_organizations():
    app = create_app()
    with app.app_context():
        backup_file = os.path.join(r"D:\market_intelligence", "backups", "pre_migration_phase1_backup_20260924_125927.json")
        if not os.path.exists(backup_file):
            print(f"File backup tidak ditemukan: {backup_file}")
            return

        print(f"Memuat berkas backup {backup_file}...")
        t0 = time.time()
        with open(backup_file, "r", encoding="utf-8") as f:
            backup_data = json.load(f)

        org_table = backup_data.get("tables", {}).get("organizations", {})
        rows = org_table.get("rows", [])
        total_backup_rows = len(rows)
        print(f"Total baris organisasi di backup: {total_backup_rows:,} (dimuat dalam {time.time()-t0:.2f}s)")

        # Ambil set ID yang sudah ada di database saat ini
        existing_ids = set(r[0] for r in db.session.execute(text("SELECT id FROM organizations")).fetchall())
        print(f"Jumlah organisasi yang sudah ada di database saat ini: {len(existing_ids):,}")

        # Validasi ketersediaan data_sources agar foreign key tidak error
        valid_ds_ids = set(r[0] for r in db.session.execute(text("SELECT id FROM data_sources")).fetchall())

        to_insert = []
        for r in rows:
            rid = r.get("id")
            if rid in existing_ids:
                continue

            # Buat copy dict bersih untuk model Organization
            row_dict = {
                "id": rid,
                "name": r.get("name") or "Perusahaan Tanpa Nama",
                "normalized_name": r.get("normalized_name"),
                "domain": r.get("domain"),
                "organization_type": r.get("organization_type") or "Perusahaan",
                "industry": r.get("industry"),
                "address": r.get("address"),
                "city": r.get("city"),
                "province": r.get("province"),
                "phone": r.get("phone"),
                "email": r.get("email"),
                "website": r.get("website"),
                "social_json": r.get("social_json"),
                "source_url": r.get("source_url"),
                "description": r.get("description"),
                "product_fit": r.get("product_fit"),
                "opportunity_score": r.get("opportunity_score") or 0,
                "priority_tier": r.get("priority_tier"),
                "source_id": r.get("source_id") if r.get("source_id") in valid_ds_ids else None,
                "source_type": r.get("source_type") or "bps_upload",
                "employee_size": r.get("employee_size"),
                "relevance_score": r.get("relevance_score") or 0,
                "verification_status": r.get("verification_status") or "discovered",
                "provenance_json": r.get("provenance_json"),
            }

            for dt_col in ["created_at", "last_seen", "data_freshness"]:
                val = r.get(dt_col)
                if val and isinstance(val, str):
                    try:
                        row_dict[dt_col] = datetime.fromisoformat(val)
                    except Exception:
                        row_dict[dt_col] = None
                else:
                    row_dict[dt_col] = None

            to_insert.append(row_dict)

        print(f"Jumlah entitas baru yang akan di-insert: {len(to_insert):,}")
        if not to_insert:
            print("Semua data backup sudah ada di database.")
            return

        chunk_size = 500
        total_inserted = 0
        t_start = time.time()

        for i in range(0, len(to_insert), chunk_size):
            chunk = to_insert[i:i + chunk_size]
            try:
                db.session.bulk_insert_mappings(Organization, chunk)
                db.session.commit()
                total_inserted += len(chunk)
                print(f"  [+] Berhasil memasukkan {total_inserted:,} / {len(to_insert):,} organisasi...")
            except Exception as e:
                db.session.rollback()
                print(f"  [!] Error pada chunk {i}-{i+len(chunk)}: {e}")
                # Fallback per row jika ada baris yang bermasalah
                for row_item in chunk:
                    try:
                        db.session.bulk_insert_mappings(Organization, [row_item])
                        db.session.commit()
                        total_inserted += 1
                    except Exception as err_single:
                        db.session.rollback()
                        print(f"      Gagal skip ID {row_item['id']}: {err_single}")

        # Update postgres sequence untuk organizations_id_seq
        try:
            db.session.execute(text("SELECT setval('organizations_id_seq', COALESCE((SELECT MAX(id) FROM organizations), 1));"))
            db.session.commit()
            print("Sequence `organizations_id_seq` berhasil disinkronkan.")
        except Exception as e:
            print(f"Catatan sequence: {e}")

        total_now = db.session.execute(text("SELECT count(*) FROM organizations")).scalar()
        print(f"\n=== SELESAI ===")
        print(f"Waktu total: {time.time()-t_start:.2f} detik")
        print(f"Total organisasi di database sekarang: {total_now:,}")

if __name__ == "__main__":
    restore_bps_organizations()
