"""Test Suite untuk Fase 3: Refactor Enrichment Pipeline to Master Intelligence.

Memverifikasi:
1. End-to-End Enrichment Pipeline (Parse -> Enrich -> Export Excel -> Identity Resolution -> Master Organization -> Prospect Sync).
2. Identity Resolution & Master Deduplication (Tier 1-3 Strong Signals) saat batch save.
3. Ambiguous Candidate Handling (Tier 4 / Location Conflict): tidak auto-merge, masuk DuplicateCandidate pending review, buat entity mandiri.
4. Idempotency 100%: penjalanan berulang dengan dataset yang sama menghasilkan 0 duplikasi Organization dan 0 duplikasi Prospect.
5. Ketahanan Sistem: kegagalan database tidak menghilangkan file Excel hasil enrichment.
6. Backward Compatibility: query modul lama (market_analysis, marketing, reporting, prospect) tetap berjalan lancar.
"""

import os
import json
import unittest
import pandas as pd
from app import create_app
from app.extensions import db
from app.models import User, RawData, DataSource, Organization, Prospect, DuplicateCandidate, Campaign, MarketAnalysis, Report
from app.enrichment import enrich_dataset, export_to_excel, save_enriched_to_db_in_batches, BatchSaveResult
from app.config import TestConfig
from app.services.dedup_engine import IdentityResolutionEngine


class TestPhase3Pipeline(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app.config["TESTING"] = True
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Dapatkan atau buat test user
        self.user = User.query.filter_by(role="business_analyst").first()
        if not self.user:
            self.user = User(name="BA Phase3 Tester", email="ba_phase3@example.com", role="business_analyst")
            self.user.set_password("Secret123!")
            db.session.add(self.user)
            db.session.commit()

        # Buat DataSource untuk testing
        self.data_source = DataSource(name="Phase 3 Test Source", source_type="file", created_by=self.user.id)
        db.session.add(self.data_source)
        db.session.commit()

        self.cleanup_raw_ids = []
        self.cleanup_org_ids = []
        self.cleanup_files = []

        # Bersihkan entitas uji dari run sebelumnya jika ada
        test_domains = ["nusantaratekstil.co.id", "panganmandiri.com", "megabaja.co.id", "semenandalas.com", "solusimaju.com"]
        for d in test_domains:
            for org in Organization.query.filter_by(domain=d).all():
                DuplicateCandidate.query.filter_by(organization_id=org.id).delete()
                Prospect.query.filter_by(organization_id=org.id).delete()
                db.session.delete(org)
        for name in ["PT Makmur Sentosa", "PT Resilien Export", "PT Kompatibel Modul Lama"]:
            for org in Organization.query.filter_by(name=name).all():
                DuplicateCandidate.query.filter_by(organization_id=org.id).delete()
                Prospect.query.filter_by(organization_id=org.id).delete()
                db.session.delete(org)
        db.session.commit()

    def tearDown(self):
        # Bersihkan data uji yang dibuat selama test
        if self.cleanup_raw_ids:
            Prospect.query.filter(Prospect.raw_data_id.in_(self.cleanup_raw_ids)).delete(synchronize_session=False)
            RawData.query.filter(RawData.id.in_(self.cleanup_raw_ids)).delete(synchronize_session=False)

        if self.cleanup_org_ids:
            DuplicateCandidate.query.filter(DuplicateCandidate.organization_id.in_(self.cleanup_org_ids)).delete(synchronize_session=False)
            Prospect.query.filter(Prospect.organization_id.in_(self.cleanup_org_ids)).delete(synchronize_session=False)
            Organization.query.filter(Organization.id.in_(self.cleanup_org_ids)).delete(synchronize_session=False)

        if self.data_source and self.data_source.id:
            ds = db.session.get(DataSource, self.data_source.id)
            if ds:
                db.session.delete(ds)

        db.session.commit()

        for f in self.cleanup_files:
            if os.path.exists(f):
                try:
                    os.remove(f)
                except Exception:
                    pass

        self.app_context.pop()

    def test_1_end_to_end_enrichment_pipeline(self):
        """Uji 1: Pipeline lengkap dari enrichment, export Excel, resolusi ke Organization, hingga sync Prospect."""
        # 1. Dataset Uji
        raw_rows = [
            {
                "nama_perusahaan": "PT Nusantara Tekstil Prima TestP3",
                "industri": "Industri Tekstil dan Pakaian Jadi",
                "kota": "Bandung",
                "provinsi": "Jawa Barat",
                "telepon": "022-7890123",
                "email": "contact@nusantaratekstilp3.co.id",
                "website": "https://www.nusantaratekstilp3.co.id",
                "alamat": "Jl. Soekarno Hatta No. 45"
            },
            {
                "nama_perusahaan": "CV Boga Sejahtera Mandiri TestP3",
                "industri": "Industri Makanan Olahan",
                "kota": "Surabaya",
                "provinsi": "Jawa Timur",
                "telepon": "031-8889999",
                "email": "info@bogamandirip3.com",
                "website": "http://bogamandirip3.com",
                "alamat": "Rungkut Industri III"
            }
        ]
        df = pd.DataFrame(raw_rows)

        # 2. Enrichment
        df_enriched = enrich_dataset(df)
        self.assertEqual(len(df_enriched), 2)
        self.assertIn("kategori_industri", df_enriched.columns)
        self.assertIn("rekomendasi_produk", df_enriched.columns)
        self.assertIn("sales_score", df_enriched.columns)
        self.assertIn("priority", df_enriched.columns)

        # 3. Export Excel
        export_path = os.path.join(self.app.config.get("RAW_STAGING_DIR", "instance/staging"), "test_p3_e2e.xlsx")
        self.cleanup_files.append(export_path)
        export_to_excel(df_enriched, export_path)
        self.assertTrue(os.path.exists(export_path))
        self.assertGreater(os.path.getsize(export_path), 0)

        # 4. Save RawData metadata
        rd = RawData(
            source_id=self.data_source.id,
            source_type="file",
            original_name="test_p3_e2e.xlsx",
            status="processed",
            created_by=self.user.id
        )
        db.session.add(rd)
        db.session.commit()
        self.cleanup_raw_ids.append(rd.id)

        # 5. Batch Save ke Database
        res, err = save_enriched_to_db_in_batches(df_enriched, raw_data_id=rd.id, user_id=self.user.id, batch_size=2)
        self.assertIsNone(err)
        self.assertTrue(isinstance(res, int))
        self.assertEqual(res, 2)
        self.assertEqual(res.orgs_created, 2)
        self.assertEqual(res.orgs_updated, 0)
        self.assertEqual(res.candidates_flagged, 0)
        self.assertEqual(res.prospects_synced, 2)

        # Verifikasi Organization (MASTER)
        org1 = Organization.query.filter_by(domain="nusantaratekstilp3.co.id").first()
        self.assertIsNotNone(org1, "Master Organization untuk nusantaratekstilp3.co.id wajib dibuat")
        self.cleanup_org_ids.append(org1.id)
        self.assertEqual(org1.city, "Bandung")
        self.assertEqual(org1.province, "Jawa Barat")
        self.assertIsNotNone(org1.opportunity_score)
        self.assertIsNotNone(org1.priority_tier)

        org2 = Organization.query.filter_by(domain="bogamandirip3.com").first()
        self.assertIsNotNone(org2, "Master Organization untuk bogamandirip3.com wajib dibuat")
        self.cleanup_org_ids.append(org2.id)

        # Verifikasi Provenance
        self.assertIsNotNone(org1.provenance_json)
        prov1 = json.loads(org1.provenance_json)
        self.assertEqual(len(prov1), 1)
        self.assertEqual(prov1[0]["match_tier"], "initial_creation")
        self.assertEqual(prov1[0]["raw_data_id"], rd.id)

        # Verifikasi Compatibility Sync ke Prospect
        prospects = Prospect.query.filter_by(raw_data_id=rd.id).all()
        self.assertEqual(len(prospects), 2)
        p1 = next((p for p in prospects if p.organization_id == org1.id), None)
        self.assertIsNotNone(p1, "Prospect harus terhubung ke master organization_id")
        self.assertEqual(p1.company_name, org1.name)
        self.assertEqual(p1.score, org1.opportunity_score)

        print("  [PASS] Test 1: End-to-End Enrichment Pipeline to Master Intelligence verified.")

    def test_2_master_deduplication_strong_signals(self):
        """Uji 2: Deduplikasi saat save batch menggunakan strong matching signals (Tier 1 & Tier 2)."""
        # Buat master Organization terlebih dahulu
        master_org = Organization(
            name="PT Mega Baja Indonesia",
            normalized_name="mega baja indonesia",
            domain="megabaja.co.id",
            industry="Konstruksi",
            city="Bekasi",
            province="Jawa Barat",
            phone="0218881234",
            email="sales@megabaja.co.id",
            website="https://megabaja.co.id",
            opportunity_score=50,
            priority_tier="Tier C",
            source_id=self.data_source.id,
            provenance_json=json.dumps([{
                "source_type": "bps",
                "source_id": 999,
                "raw_name": "PT Mega Baja Indonesia",
                "match_tier": "initial_creation",
                "confidence": 1.0,
                "merged_at": "2026-09-01T00:00:00"
            }])
        )
        db.session.add(master_org)
        db.session.commit()
        self.cleanup_org_ids.append(master_org.id)

        # Buat batch input baru:
        # Row 1: Cocok dengan master_org via domain (Tier 1) dan membawa kontak baru serta skor lebih tinggi
        # Row 2: Entitas baru yang belum ada
        new_rows = [
            {
                "nama_perusahaan": "Mega Baja Indonesia Cabang Cikarang",
                "industri": "Manufacturing",
                "kota": "Bekasi",
                "provinsi": "Jawa Barat",
                "telepon": "0218881234",
                "email": "cikarang@megabaja.co.id",  # Domain sama: megabaja.co.id
                "website": "https://www.megabaja.co.id/cikarang",
                "alamat": "Kawasan Industri Jababeka"
            },
            {
                "nama_perusahaan": "PT Semen Perkasa Andalas",
                "industri": "Konstruksi",
                "kota": "Padang",
                "provinsi": "Sumatera Barat",
                "telepon": "075199988",
                "email": "info@semenandalas.com",
                "website": "https://semenandalas.com",
                "alamat": "Jl. Raya Padang"
            }
        ]
        df = pd.DataFrame(new_rows)
        df_enriched = enrich_dataset(df)

        rd = RawData(source_id=self.data_source.id, source_type="file", original_name="test_p3_dedup.xlsx", status="processed", created_by=self.user.id)
        db.session.add(rd)
        db.session.commit()
        self.cleanup_raw_ids.append(rd.id)

        # Jalankan batch save
        res, err = save_enriched_to_db_in_batches(df_enriched, raw_data_id=rd.id, user_id=self.user.id)
        self.assertIsNone(err)
        self.assertEqual(res.orgs_created, 1, "Hanya 1 entitas baru (Semen Perkasa) yang dibuat")
        self.assertEqual(res.orgs_updated, 1, "1 entitas (Mega Baja) berhasil di-auto-merge")

        # Verifikasi master_org diperbarui
        db.session.refresh(master_org)
        self.assertIsNotNone(master_org.provenance_json)
        prov = json.loads(master_org.provenance_json)
        self.assertEqual(len(prov), 2, "Riwayat provenance harus bertambah menjadi 2 entri")
        self.assertEqual(prov[1]["match_tier"], "tier1_domain")

        # Verifikasi Semen Perkasa dibuat
        new_org = Organization.query.filter_by(domain="semenandalas.com").first()
        self.assertIsNotNone(new_org)
        self.cleanup_org_ids.append(new_org.id)

        print("  [PASS] Test 2: Master Deduplication & Strong Signals verified.")

    def test_3_ambiguous_candidate_handling(self):
        """Uji 3: Sinyal ambigu (Tier 4 / Location Conflict) tidak auto-merge, dicatat ke DuplicateCandidate pending review."""
        # Master Org: "PT Makmur Sentosa" di Jakarta
        master_org = Organization(
            name="PT Makmur Sentosa",
            normalized_name="makmur sentosa",
            domain=None,
            city="Jakarta Selatan",
            province="DKI Jakarta",
            opportunity_score=50,
            priority_tier="Tier C",
            source_id=self.data_source.id,
            provenance_json=json.dumps([{"source_type": "seed", "match_tier": "initial_creation"}])
        )
        db.session.add(master_org)
        db.session.commit()
        self.cleanup_org_ids.append(master_org.id)

        # Incoming Row: Nama identik "PT Makmur Sentosa" tapi di Medan, Sumatera Utara (Konflik Wilayah Eksplisit!)
        conflict_rows = [
            {
                "nama_perusahaan": "PT Makmur Sentosa",
                "kota": "Medan",
                "provinsi": "Sumatera Utara",
                "industri": "Manufacturing",
                "alamat": "Kawasan Industri Medan"
            }
        ]
        df = pd.DataFrame(conflict_rows)
        df_enriched = enrich_dataset(df)

        rd = RawData(source_id=self.data_source.id, source_type="file", original_name="test_p3_conflict.xlsx", status="processed", created_by=self.user.id)
        db.session.add(rd)
        db.session.commit()
        self.cleanup_raw_ids.append(rd.id)

        res, err = save_enriched_to_db_in_batches(df_enriched, raw_data_id=rd.id, user_id=self.user.id)
        self.assertIsNone(err)
        self.assertEqual(res.candidates_flagged, 1, "Harus mencatat 1 kandidat review karena konflik lokasi")
        self.assertEqual(res.orgs_created, 1, "Entitas master tersendiri harus dibuat agar data tidak hilang")
        self.assertEqual(res.orgs_updated, 0, "TIDAK boleh meng-update/menggabungkan entitas Jakarta secara otomatis")

        # Verifikasi tabel duplicate_candidates
        candidate = DuplicateCandidate.query.filter_by(organization_id=master_org.id).first()
        self.assertIsNotNone(candidate, "DuplicateCandidate harus tercatat di DB")
        self.assertEqual(candidate.status, "pending")
        self.assertIn("tier2_name_location_conflict", candidate.match_tier)
        self.assertEqual(candidate.candidate_name, "PT Makmur Sentosa")

        # Bersihkan entitas baru yang dibuat
        medan_org = Organization.query.filter_by(city="Medan").first()
        if medan_org:
            self.cleanup_org_ids.append(medan_org.id)

        print("  [PASS] Test 3: Ambiguous Candidate Handling (No Auto-Merge, Review Pending) verified.")

    def test_4_pipeline_idempotency(self):
        """Uji 4: Penjalanan berulang kali dengan dataset yang sama tidak menghasilkan duplikasi."""
        rows = [
            {
                "nama_perusahaan": "PT Solusi Idempotent Maju",
                "industri": "Tekstil",
                "kota": "Semarang",
                "provinsi": "Jawa Tengah",
                "telepon": "024-7654321",
                "email": "halo@solusimaju.com",
                "website": "https://solusimaju.com"
            }
        ]
        df = pd.DataFrame(rows)
        df_enriched = enrich_dataset(df)

        rd = RawData(source_id=self.data_source.id, source_type="file", original_name="test_idempotent.xlsx", status="processed", created_by=self.user.id)
        db.session.add(rd)
        db.session.commit()
        self.cleanup_raw_ids.append(rd.id)

        # Run 1: Pembuatan awal
        res1, err1 = save_enriched_to_db_in_batches(df_enriched, raw_data_id=rd.id, user_id=self.user.id)
        self.assertIsNone(err1)
        self.assertEqual(res1.orgs_created, 1)
        self.assertEqual(res1.prospects_synced, 1)

        org = Organization.query.filter_by(domain="solusimaju.com").first()
        self.assertIsNotNone(org)
        self.cleanup_org_ids.append(org.id)

        org_count_before = Organization.query.count()
        prospect_count_before = Prospect.query.filter_by(raw_data_id=rd.id).count()
        self.assertEqual(prospect_count_before, 1)

        # Run 2: Re-ingest dataset yang sama persis dengan raw_data_id yang sama
        res2, err2 = save_enriched_to_db_in_batches(df_enriched, raw_data_id=rd.id, user_id=self.user.id)
        self.assertIsNone(err2)
        self.assertEqual(res2.orgs_created, 0, "Tidak boleh membuat organization baru pada penjalanan ulang")
        self.assertEqual(res2.candidates_flagged, 0)

        org_count_after = Organization.query.count()
        prospect_count_after = Prospect.query.filter_by(raw_data_id=rd.id).count()

        self.assertEqual(org_count_before, org_count_after, "Total Organization di DB tidak boleh bertambah")
        self.assertEqual(prospect_count_before, prospect_count_after, "Total Prospect di DB tidak boleh bertambah duplikat")

        print("  [PASS] Test 4: Pipeline Idempotency (0 Duplicates on Rerun) verified.")

    def test_5_resilience_and_excel_preservation(self):
        """Uji 5: Kegagalan database tidak menghilangkan file Excel hasil export."""
        rows = [{"nama_perusahaan": "PT Resilien Export", "industri": "Garmen", "kota": "Solo", "provinsi": "Jawa Tengah"}]
        df = pd.DataFrame(rows)
        df_enriched = enrich_dataset(df)

        export_path = os.path.join(self.app.config.get("RAW_STAGING_DIR", "instance/staging"), "test_resilience.xlsx")
        self.cleanup_files.append(export_path)
        export_to_excel(df_enriched, export_path)

        # Pastikan file Excel fisik tercipta
        self.assertTrue(os.path.exists(export_path))
        initial_file_size = os.path.getsize(export_path)
        self.assertGreater(initial_file_size, 0)

        # Simulasikan database error saat batch save (misal dengan memicu exception pada session)
        class FaultyDataFrame(pd.DataFrame):
            @property
            def iloc(self):
                raise RuntimeError("Simulated Database / IO Exception during batch")

        faulty_df = FaultyDataFrame(rows)
        res, err = save_enriched_to_db_in_batches(faulty_df, raw_data_id=99999, user_id=self.user.id)
        self.assertIsNotNone(err)
        self.assertIn("Simulated Database", err)

        # File Excel fisik HARUS TETAP ADA dan TIDAK RUSAK
        self.assertTrue(os.path.exists(export_path), "File Excel hasil enrichment tidak boleh hilang saat DB error")
        self.assertEqual(os.path.getsize(export_path), initial_file_size)

        print("  [PASS] Test 5: Resilience & Excel Output Preservation verified.")

    def test_6_backward_compatibility_with_legacy_modules(self):
        """Uji 6: Modul lama (market_analysis, marketing, reporting, prospect) tetap berfungsi 100%."""
        # Buat master Organization & synced Prospect
        org = Organization(
            name="PT Kompatibel Modul Lama",
            industry="TEXTILE",
            city="Bandung",
            province="Jawa Barat",
            opportunity_score=80,
            priority_tier="Tier A",
            product_fit="Jaket, Kaos, Polo Shirt, Seragam"
        )
        db.session.add(org)
        db.session.flush()
        self.cleanup_org_ids.append(org.id)

        p = Prospect(
            company_name=org.name,
            industry=org.industry,
            region="Bandung, Jawa Barat",
            score=org.opportunity_score,
            segment=org.priority_tier,
            description=org.product_fit,
            organization_id=org.id,
            status="new",
            created_by=self.user.id
        )
        db.session.add(p)
        db.session.commit()

        # 1. Query market_analysis: _distribution('industry') & _distribution('region')
        from sqlalchemy import func
        ind_dist = dict(db.session.query(Prospect.industry, func.count(Prospect.id)).filter(Prospect.industry.isnot(None)).group_by(Prospect.industry).all())
        self.assertIn("TEXTILE", ind_dist)
        self.assertGreaterEqual(ind_dist["TEXTILE"], 1)

        # 2. Query marketing: filter score & segment
        high_score_prospects = Prospect.query.filter(Prospect.score >= 70).all()
        self.assertGreaterEqual(len(high_score_prospects), 1)

        # 3. Query reporting: avg_score & total_prospects
        total_p = Prospect.query.count()
        avg_score = db.session.query(func.avg(Prospect.score)).scalar()
        self.assertGreaterEqual(total_p, 1)
        self.assertGreater(avg_score, 0)

        # 4. Relasi master Organization -> prospects_legacy
        linked_prospects = org.prospects_legacy.all()
        self.assertEqual(len(linked_prospects), 1)
        self.assertEqual(linked_prospects[0].company_name, "PT Kompatibel Modul Lama")

        print("  [PASS] Test 6: Backward Compatibility with Legacy Modules verified.")


if __name__ == "__main__":
    unittest.main()
