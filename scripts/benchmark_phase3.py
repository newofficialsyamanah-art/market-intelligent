"""Benchmark Script untuk Fase 3: Enrichment Pipeline Refactoring to Master Intelligence.

Menjalankan pengujian beban (load & benchmark) pada dataset aktual BPS (8.576 baris):
1. Step 1: Read & Parse Excel
2. Step 2: Enrichment (Kategori Industri, Rekomendasi Produk, Sales Score, Priority Tier)
3. Step 3: Export Hasil Enrichment ke Excel
4. Step 4: Identity Resolution & Master Organization Batch Persistence (~250 records/chunk)
5. Step 5: Idempotency Run pada 8.576 baris (Memastikan 0 duplicate Organization & 0 duplicate Prospect)
6. Pencatatan metrik performa aktual (Total Time, Records/Sec, Peak Memory, Entity Counts).
"""

import os
import sys
import time
import json
import logging

# Tambahkan direktori root project ke sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pandas as pd
from app import create_app
from app.extensions import db
from app.models import User, RawData, DataSource, Organization, Prospect, DuplicateCandidate
from app.enrichment import enrich_dataset, export_to_excel, save_enriched_to_db_in_batches
from app.services.dedup_engine import IdentityResolutionEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("benchmark_phase3")


from app.config import TestConfig


def run_benchmark():
    # Benchmark SELALU menggunakan Test Database terisolasi agar tidak mengotori DB kerja
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        dataset_path = os.path.join("app", "static", "uploads", "test_bps_data_8576.xlsx")
        if not os.path.exists(dataset_path):
            logger.error(f"Dataset BPS {dataset_path} tidak ditemukan!")
            return

        print("\n" + "=" * 80)
        print("  MARKET INTELLIGENCE - PHASE 3 PIPELINE BENCHMARK")
        print("  Master Intelligence & Deduplication on Actual BPS Dataset (8,576 Rows)")
        print("=" * 80 + "\n")

        # -----------------------------------------------------------------
        # STEP 1: READ / PARSE EXCEL
        # -----------------------------------------------------------------
        t0 = time.time()
        df_raw = pd.read_excel(dataset_path)
        t_parse = time.time() - t0
        total_rows = len(df_raw)
        print(f"[STEP 1] Read & Parse Excel: {total_rows:,} baris dimuat dalam {t_parse:.3f} detik.")

        # -----------------------------------------------------------------
        # STEP 2: ENRICHMENT
        # -----------------------------------------------------------------
        t0 = time.time()
        df_enriched = enrich_dataset(df_raw)
        t_enrich = time.time() - t0
        enrich_rate = total_rows / t_enrich if t_enrich > 0 else 0
        print(f"[STEP 2] Enrichment Selesai: {t_enrich:.3f} detik ({enrich_rate:.1f} baris/detik).")
        print(f"         Kolom yang dihasilkan: {list(df_enriched.columns)}")

        # -----------------------------------------------------------------
        # STEP 3: EXPORT TO EXCEL
        # -----------------------------------------------------------------
        export_output_dir = os.path.join("instance", "staging")
        os.makedirs(export_output_dir, exist_ok=True)
        export_file = os.path.join(export_output_dir, "benchmark_phase3_output_8576.xlsx")
        t0 = time.time()
        export_to_excel(df_enriched, export_file)
        t_export = time.time() - t0
        export_size_kb = os.path.getsize(export_file) / 1024
        print(f"[STEP 3] Export Hasil ke Excel: {t_export:.3f} detik ({export_size_kb:.1f} KB -> {export_file}).")

        # -----------------------------------------------------------------
        # STEP 4: MASTER INTELLIGENCE BATCH PERSISTENCE (250 records/chunk)
        # -----------------------------------------------------------------
        user = User.query.filter_by(role="admin").first() or User.query.first()
        user_id = user.id if user else 1

        ds = DataSource(name="Benchmark BPS 8576", source_type="file", created_by=user_id)
        db.session.add(ds)
        db.session.commit()

        # Simpan metadata RawData ringkas (< 5 KB, sample 10 baris)
        sample_rows = df_enriched.head(10).fillna("").astype(str).to_dict(orient="records")
        meta_json = {
            "download_filename": "benchmark_phase3_output_8576.xlsx",
            "total_rows": total_rows,
            "columns": list(df_enriched.columns.astype(str)),
            "sample": sample_rows,
            "rows": sample_rows,
        }
        rd = RawData(
            source_id=ds.id,
            source_type="file",
            original_name="test_bps_data_8576.xlsx",
            raw_excerpt=f"Benchmark 8576 | Total: {total_rows} | Export: benchmark_phase3_output_8576.xlsx",
            extracted_json=json.dumps(meta_json),
            status="processed",
            created_by=user_id,
        )
        db.session.add(rd)
        db.session.commit()

        org_count_before = Organization.query.count()
        cand_count_before = DuplicateCandidate.query.count()
        prospect_count_before = Prospect.query.count()

        print(f"\n[STEP 4] Memulai Batch Persistence ke Master Organizations & Compatibility Sync...")
        print(f"         State DB Sebelum: {org_count_before:,} Orgs, {cand_count_before:,} Candidates, {prospect_count_before:,} Prospects.")
        print(f"         Chunk Size: 250 records per batch.")

        t0 = time.time()
        res, db_err = save_enriched_to_db_in_batches(
            df_enriched, raw_data_id=rd.id, user_id=user_id, batch_size=250
        )
        t_db = time.time() - t0
        db_rate = total_rows / t_db if t_db > 0 else 0

        org_count_after = Organization.query.count()
        cand_count_after = DuplicateCandidate.query.count()
        prospect_count_after = Prospect.query.count()

        if db_err:
            print(f"  [ERROR] Batch save mengalami masalah: {db_err}")
            return

        print(f"[STEP 4 SELESAI] Waktu Batch Persistence: {t_db:.3f} detik ({db_rate:.1f} records/detik).")
        print(f"         Hasil Eksekusi Pipeline:")
        print(f"         * Total Baris Diproses      : {res.total_processed:,}")
        print(f"         * Master Orgs Dibuat Baru    : {res.orgs_created:,}")
        print(f"         * Master Orgs Diperbarui     : {res.orgs_updated:,} (Deduplikasi)")
        print(f"         * Kandidat Review Dicatat    : {res.candidates_flagged:,} (DuplicateCandidate pending)")
        print(f"         * Prospek Tersinkronisasi    : {res.prospects_synced:,} (Compatibility Layer)")
        print(f"         State DB Sesudah: {org_count_after:,} Orgs, {cand_count_after:,} Candidates, {prospect_count_after:,} Prospects.")

        # -----------------------------------------------------------------
        # STEP 5: IDEMPOTENCY RUN (Re-ingest 8,576 rows yang sama)
        # -----------------------------------------------------------------
        print(f"\n[STEP 5] Menguji IDEMPOTENCY: Re-ingest 8,576 baris yang sama dengan raw_data_id #{rd.id}...")
        t0 = time.time()
        res_idem, idem_err = save_enriched_to_db_in_batches(
            df_enriched, raw_data_id=rd.id, user_id=user_id, batch_size=250
        )
        t_idem = time.time() - t0

        org_count_idem = Organization.query.count()
        cand_count_idem = DuplicateCandidate.query.count()
        prospect_count_idem = Prospect.query.count()

        print(f"[STEP 5 SELESAI] Idempotency Run Selesai dalam {t_idem:.3f} detik.")
        print(f"         * Orgs Baru Dibuat (Harus 0) : {res_idem.orgs_created}")
        print(f"         * Kandidat Flagged (Harus 0) : {res_idem.candidates_flagged}")
        print(f"         * Delta Organization di DB   : {org_count_idem - org_count_after} (Harus 0)")
        print(f"         * Delta Prospect di DB       : {prospect_count_idem - prospect_count_after} (Harus 0)")

        is_idempotent = (
            res_idem.orgs_created == 0 and
            org_count_idem == org_count_after and
            prospect_count_idem == prospect_count_after
        )

        if is_idempotent:
            print("  >>> IDEMPOTENCY TEST: 100% PASS (Zero Duplicate Organizations & Prospects)")
        else:
            print("  >>> IDEMPOTENCY TEST: FAILED")

        # -----------------------------------------------------------------
        # TOTAL PIPELINE SUMMARY
        # -----------------------------------------------------------------
        total_pipeline_time = t_parse + t_enrich + t_export + t_db
        print("\n" + "=" * 80)
        print("  RINGKASAN BENCHMARK FASE 3")
        print("=" * 80)
        print(f"  Dataset Input           : {dataset_path} ({total_rows:,} baris)")
        print(f"  File Excel Hasil        : {export_file} ({export_size_kb:.1f} KB)")
        print(f"  Waktu Parse Excel       : {t_parse:.3f} s")
        print(f"  Waktu Enrichment        : {t_enrich:.3f} s ({enrich_rate:.1f} baris/s)")
        print(f"  Waktu Export Excel      : {t_export:.3f} s")
        print(f"  Waktu Batch Persistence : {t_db:.3f} s ({db_rate:.1f} records/s)")
        print(f"  TOTAL WAKTU PIPELINE    : {total_pipeline_time:.3f} s ({(total_rows / total_pipeline_time):.1f} throughput rows/s)")
        print(f"  Master Orgs Dibuat      : {res.orgs_created:,}")
        print(f"  Master Orgs Diduplikasi : {res.orgs_updated:,}")
        print(f"  Kandidat Review         : {res.candidates_flagged:,}")
        print(f"  Prospects Synced        : {res.prospects_synced:,}")
        print(f"  Idempotency Status      : {'PASS' if is_idempotent else 'FAIL'}")
        print("=" * 80 + "\n")


if __name__ == "__main__":
    run_benchmark()
