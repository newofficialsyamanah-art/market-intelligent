import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import create_app, db
from app.models import Organization, Prospect, RawData, DataSource
from sqlalchemy import text

app = create_app()

with app.app_context():
    print("=" * 80)
    print("EKSEKUSI PEMBERSIHAN DATA DUPLIKAT (CLEANUP)")
    print("=" * 80)

    # 1. CLEANUP PROSPECTS DUPLICATES (raw_data_id = 12)
    # 8,576 records duplicate dari file re-upload hasil_enrichment_47e24deb.xlsx
    count_p12 = Prospect.query.filter_by(raw_data_id=12).count()
    print(f"\n[1] Menghapus {count_p12} prospek duplikat dari raw_data_id=12...")
    deleted_prospects = Prospect.query.filter_by(raw_data_id=12).delete(synchronize_session=False)
    db.session.commit()
    print(f"    -> Berhasil menghapus {deleted_prospects} prospek duplikat.")

    # 2. CLEANUP 4 ORGANIZATIONS DUPLICATES
    # IDs: 9936 (Medan Futsal Club), 9937 (USU Futsal Team), 9939 (Unimed Futsal Squad), 9943 (Politeknik Negeri Medan Futsal)
    print("\n[2] Menghapus 4 entitas organisasi duplikat hasil concurrent discovery...")
    # Update score tertinggi untuk Politeknik Negeri Medan Futsal (ID 9946) dari ID 9943 (score 82)
    poly = Organization.query.get(9946)
    if poly:
        poly.opportunity_score = max(poly.opportunity_score or 0, 82)
        db.session.commit()

    deleted_orgs = Organization.query.filter(Organization.id.in_([9936, 9937, 9939, 9943])).delete(synchronize_session=False)
    db.session.commit()
    print(f"    -> Berhasil menghapus {deleted_orgs} organisasi duplikat (IDs: 9936, 9937, 9939, 9943).")

    # 3. CLEANUP REDUNDANT RAW_DATA & DATA_SOURCES
    print("\n[3] Menghapus data scrape mentah berulang (raw_data 14, 15) dan sumber data redundant...")
    deleted_raw = RawData.query.filter(RawData.id.in_([14, 15])).delete(synchronize_session=False)
    # Hapus juga raw_data 12 karena prospeknya sudah dibersihkan (bisa dipertahankan atau dihapus)
    # Pertahankan metadata raw_data 12 atau biarkan
    deleted_ds = DataSource.query.filter(DataSource.id.in_([64, 65, 62])).delete(synchronize_session=False)
    db.session.commit()
    print(f"    -> Berhasil menghapus {deleted_raw} raw_data mentah dan {deleted_ds} data_sources redundant.")

    print("\n" + "=" * 80)
    print("VERIFIKASI SETELAH PEMBERSIHAN:")
    print("=" * 80)
    print("Total Organizations:", Organization.query.count())
    print("Total Prospects    :", Prospect.query.count())
    print("Total RawData      :", RawData.query.count())
    print("Total DataSources  :", DataSource.query.count())
