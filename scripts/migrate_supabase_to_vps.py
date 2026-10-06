import os
import sys
import time
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker

SRC_URL = "postgresql+psycopg://postgres.mfalnomcgumgnooefigu:%40Singosari12345%21@aws-0-ap-northeast-1.pooler.supabase.com:5432/postgres?sslmode=require"
DST_URL = "postgresql+psycopg://syamanah:SyamanahDb2026!@139.190.99.209:5432/market_intelligence"

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app import create_app
from app.extensions import db

def migrate():
    print("=== MIGRASI DATABASE DARI SUPABASE KE VPS (139.190.99.209) ===")
    t_start = time.time()

    src_engine = create_engine(SRC_URL, pool_pre_ping=True)
    dst_engine = create_engine(DST_URL, pool_pre_ping=True)

    # 1. Pastikan seluruh tabel dibuat di VPS
    app = create_app()
    with app.app_context():
        print("1. Membuat schema tabel di target VPS...")
        db.metadata.create_all(bind=dst_engine)

    inspector = inspect(src_engine)
    all_tables = inspector.get_table_names()

    # Urutan tabel berdasarkan relasi foreign key
    table_order = [
        "users",
        "data_sources",
        "discovery_sources",
        "events",
        "procurement_suppliers",
        "organizations",
        "campaigns",
        "cron_jobs",
        "prospects",
        "supplier_products",
        "event_participants",
        "duplicate_candidates",
        "campaign_targets",
        "activity_logs",
        "raw_data",
        "reports",
        "market_analyses",
        "ai_agent_configs",
    ]

    # Tambahkan tabel yang belum masuk list jika ada
    for t in all_tables:
        if t not in table_order:
            table_order.append(t)

    print(f"2. Memulai transfer data untuk {len(table_order)} tabel...")

    with src_engine.connect() as src_conn, dst_engine.begin() as dst_conn:
        # Nonaktifkan sementara foreign key triggers untuk proses bulk copy yang aman
        dst_conn.execute(text("SET session_replication_role = 'replica';"))

        # 1. Bersihkan seluruh tabel target terlebih dahulu
        for table_name in reversed(table_order):
            if table_name in all_tables:
                dst_conn.execute(text(f'TRUNCATE TABLE "{table_name}" CASCADE;'))

        for table_name in table_order:
            if table_name not in all_tables:
                continue

            # Hitung baris di source
            count_src = src_conn.execute(text(f'SELECT count(*) FROM "{table_name}"')).scalar()
            if count_src == 0:
                print(f"  - {table_name}: 0 baris (dilewati)")
                continue

            print(f"  - {table_name}: mentransfer {count_src:,} baris...")
            t0 = time.time()

            # Ambil kolom
            cols = [col["name"] for col in inspector.get_columns(table_name)]
            cols_quoted = [f'"{c}"' for c in cols]
            col_list_str = ", ".join(cols_quoted)
            params_str = ", ".join([f":{c}" for c in cols])
            insert_stmt = text(f'INSERT INTO "{table_name}" ({col_list_str}) VALUES ({params_str})')

            # Fetch in chunks
            chunk_size = 1000
            offset = 0
            while offset < count_src:
                select_sql = text(f'SELECT {col_list_str} FROM "{table_name}" LIMIT {chunk_size} OFFSET {offset}')
                rows = src_conn.execute(select_sql).mappings().all()
                if not rows:
                    break
                dst_conn.execute(insert_stmt, rows)
                offset += len(rows)

            t_elapsed = time.time() - t0
            print(f"    [OK] Selesai {count_src:,} baris dalam {t_elapsed:.2f}s")

        # Kembalikan foreign key triggers
        dst_conn.execute(text("SET session_replication_role = 'origin';"))

        # Sinkronkan sequence ID untuk semua tabel di VPS
        print("3. Sinkronisasi PostgreSQL sequences di VPS...")
        seq_query = text("""
            SELECT sequence_name 
            FROM information_schema.sequences 
            WHERE sequence_schema = 'public';
        """)
        sequences = dst_conn.execute(seq_query).fetchall()
        for seq in sequences:
            seq_name = seq[0]
            # cari tabel terkait dari nama sequence (misal organizations_id_seq -> organizations)
            tbl = seq_name.replace("_id_seq", "")
            if tbl in all_tables:
                try:
                    dst_conn.execute(text(f"SELECT setval('{seq_name}', COALESCE((SELECT MAX(id) FROM \"{tbl}\"), 1));"))
                except Exception:
                    pass

    print("\n=== 4. VERIFIKASI PERBANDINGAN ROW COUNT ===")
    with src_engine.connect() as src_conn, dst_engine.connect() as dst_conn:
        for t in table_order:
            if t in all_tables:
                c_src = src_conn.execute(text(f'SELECT count(*) FROM "{t}"')).scalar()
                c_dst = dst_conn.execute(text(f'SELECT count(*) FROM "{t}"')).scalar()
                status = "OK" if c_src == c_dst else "MISMATCH"
                print(f"  [{status}] {t:22}: Supabase={c_src:6} | VPS={c_dst:6}")

    total_time = time.time() - t_start
    print(f"\nMigrasi data ke VPS selesai 100% dalam {total_time:.2f} detik!")

if __name__ == "__main__":
    migrate()
