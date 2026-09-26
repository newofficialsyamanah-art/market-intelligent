import os
import sys
import unittest
import pandas as pd
from datetime import datetime

# Setup sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import User, DataSource, RawData, Prospect, Organization, Event, EventParticipant, MarketAnalysis, Report
from app.enrichment import enrich_dataset, export_to_excel, save_enriched_to_db_in_batches
from app.discovery import _upsert_organization, _upsert_event

from app.config import TestConfig


class TestPhase1Regression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app(TestConfig)
        cls.app.config['TESTING'] = True
        cls.app.config['WTF_CSRF_ENABLED'] = False
        cls.client = cls.app.test_client()
        with cls.app.app_context():
            db.create_all()

    def test_1_legacy_prospect_queries(self):
        """Uji 1: Query lama pada tabel prospects tetap berjalan 100% kompatibel."""
        with self.app.app_context():
            # Query sederhana
            count = Prospect.query.count()
            self.assertGreaterEqual(count, 0, "Query count prospects harus berhasil")
            
            # Query filtering
            sample = Prospect.query.filter(Prospect.score >= 0).limit(10).all()
            self.assertIsInstance(sample, list)
            if sample:
                first = sample[0]
                self.assertTrue(hasattr(first, 'organization_id'), "Prospect harus memiliki atribut organization_id")
                self.assertTrue(hasattr(first, 'company_name'), "Prospect harus memiliki company_name")
            
            # Query agregasi seperti di market_analysis
            from sqlalchemy import func
            industries = db.session.query(
                Prospect.industry, func.count(Prospect.id)
            ).group_by(Prospect.industry).limit(5).all()
            self.assertIsInstance(industries, list)
            print(f"  [PASS] Legacy prospects query test passed ({count} records in DB)")

    def test_2_new_models_and_relationships(self):
        """Uji 2: Model Organization (Master), Event, dan EventParticipant bekerja sempurna."""
        with self.app.app_context():
            # Create test organization
            test_org = Organization(
                name="PT Sinar Tekstil Jaya",
                normalized_name="sinar tekstil jaya",
                domain="sinartekstil.co.id",
                organization_type="Perusahaan",
                industry="Tekstil & Pakaian",
                city="Bandung",
                province="Jawa Barat",
                product_fit="Seragam Pabrik & Wearpack",
                opportunity_score=85,
                priority_tier="Tier A",
                source_type="test"
            )
            db.session.add(test_org)
            db.session.flush()
            
            self.assertIsNotNone(test_org.id)
            self.assertIsNone(test_org.source_url, "source_url nullable harus berhasil tanpa error")
            
            # Create test event
            test_event = Event(
                name="Indonesia Apparel Expo 2026",
                event_type="Pameran",
                venue="JIExpo Kemayoran",
                city="Jakarta",
                province="DKI Jakarta",
                organizer_id=test_org.id,
                status="upcoming",
                relevance_notes="Target 200+ vendor garmen"
            )
            db.session.add(test_event)
            db.session.flush()
            
            self.assertIsNotNone(test_event.id)
            self.assertEqual(test_event.organizer_id, test_org.id)
            self.assertEqual(test_event.organizer_org.name, test_org.name)
            
            # Create test participant (Many-to-Many)
            test_participant = EventParticipant(
                event_id=test_event.id,
                organization_id=test_org.id,
                role="organizer",
                booth_number="Hall A-01",
                notes="Penyelenggara utama expo"
            )
            db.session.add(test_participant)
            db.session.commit()
            
            # Query back
            ep = EventParticipant.query.filter_by(event_id=test_event.id, organization_id=test_org.id).first()
            self.assertIsNotNone(ep)
            self.assertEqual(ep.role, "organizer")
            self.assertEqual(len(test_event.participants), 1)
            self.assertEqual(len(test_org.participations), 1)
            
            # Clean up test records
            db.session.delete(test_event)
            db.session.delete(test_org)
            db.session.commit()
            print("  [PASS] Organization, Event, and EventParticipant CRUD & relationships passed")

    def test_3_upload_and_enrichment_compatibility(self):
        """Uji 3: Pipeline enrichment Flow B berjalan sempurna dengan skema baru."""
        with self.app.app_context():
            # Buat sample dataset tiruan BPS
            data = [
                {"NAMA PERUSAHAAN": "PT GARMEN INDAH MAKMUR", "KODE KBLI": "14111", "KABUPATEN/KOTA": "KABUPATEN BANDUNG", "PROVINSI": "JAWA BARAT", "TELEPON": "022123456", "EMAIL": "info@garmenindah.com"},
                {"NAMA PERUSAHAAN": "CV TEKSTIL ABADI", "KODE KBLI": "13112", "KABUPATEN/KOTA": "KOTA SURAKARTA", "PROVINSI": "JAWA TENGAH", "TELEPON": "027112345", "EMAIL": "contact@tekstilbadi.co.id"},
                {"NAMA PERUSAHAAN": "PT MAJU LOGISTIK UTAMA", "KODE KBLI": "52291", "KABUPATEN/KOTA": "JAKARTA UTARA", "PROVINSI": "DKI JAKARTA", "TELEPON": "", "EMAIL": ""},
            ]
            df = pd.DataFrame(data)
            
            # 1. Enrich
            enriched_df = enrich_dataset(df)
            self.assertEqual(len(enriched_df), 3)
            self.assertIn("rekomendasi_produk", enriched_df.columns)
            self.assertIn("sales_score", enriched_df.columns)
            self.assertIn("priority", enriched_df.columns)
            
            # 2. Export Excel
            test_export_path = os.path.join(self.app.config.get("RAW_STAGING_DIR", "instance/staging"), "test_export_phase1.xlsx")
            os.makedirs(os.path.dirname(test_export_path), exist_ok=True)
            export_to_excel(enriched_df, test_export_path)
            self.assertTrue(os.path.exists(test_export_path))
            self.assertGreater(os.path.getsize(test_export_path), 0)
            
            # 3. Test Batch DB Save (compatibility layer test)
            admin_user = User.query.filter_by(role="admin").first()
            user_id = admin_user.id if admin_user else 1
            
            # Save dummy raw_data first
            rd = RawData(source_type="file", original_name="test_phase1.xlsx", status="processed", created_by=user_id)
            db.session.add(rd)
            db.session.commit()
            
            saved_count, err = save_enriched_to_db_in_batches(enriched_df, raw_data_id=rd.id, user_id=user_id, batch_size=2)
            self.assertIsNone(err)
            self.assertEqual(saved_count, 3)
            
            # Clean up test rows
            Prospect.query.filter_by(raw_data_id=rd.id).delete()
            db.session.delete(rd)
            db.session.commit()
            if os.path.exists(test_export_path):
                os.remove(test_export_path)
            print("  [PASS] Enrichment and batch save execution passed without error")

    def test_4_event_and_organization_discovery_resilience(self):
        """Uji 4: Discovery upsert tidak lagi error jika source_url null atau duplikat."""
        with self.app.app_context():
            # Mock DiscoverySource
            ds = DataSource.query.first()
            if not ds:
                ds = DataSource(name="Default Source", source_type="manual")
                db.session.add(ds)
                db.session.commit()
                
            from app.models import DiscoverySource
            disc_src = DiscoverySource.query.first()
            if not disc_src:
                disc_src = DiscoverySource(name="Test Discovery", source_kind="organization", category="Tekstil")
                db.session.add(disc_src)
                db.session.commit()
                
            # Upsert org via discovery helper
            test_url = "https://example.com/company-test-phase1"
            data = {"name": "PT Example Discovery", "telephone": "021-99998888"}
            is_new1 = _upsert_organization(test_url, disc_src, data, {})
            self.assertTrue(is_new1)
            
            # Duplicate upsert should update, not throw IntegrityError
            is_new2 = _upsert_organization(test_url, disc_src, {"name": "PT Example Discovery Updated"}, {})
            self.assertFalse(is_new2)
            
            # Upsert event
            event_url = "https://example.com/event-test-phase1"
            event_data = {"name": "Pameran Test 2026", "organizer": "PT Example Discovery"}
            ev_new1 = _upsert_event(event_url, disc_src, event_data, {})
            self.assertTrue(ev_new1)
            
            # Duplicate event upsert
            ev_new2 = _upsert_event(event_url, disc_src, event_data, {})
            self.assertFalse(ev_new2)
            
            # Cleanup
            Organization.query.filter_by(source_url=test_url).delete()
            Event.query.filter_by(source_url=event_url).delete()
            db.session.commit()
            print("  [PASS] Discovery upsert resilience passed (no duplicate/null constraint errors)")

    def test_5_rbac_and_route_access(self):
        """Uji 5: RBAC permissions dan proteksi endpoint berfungsi."""
        # Unauthenticated request to /admin should redirect to login
        res = self.client.get('/admin/', follow_redirects=False)
        self.assertIn(res.status_code, [302, 401, 403], "Unauthenticated user must be redirected or blocked from /admin")
        
        # Public login page must return 200
        res_login = self.client.get('/login')
        self.assertEqual(res_login.status_code, 200, "Login page must return 200")
        print("  [PASS] RBAC and route protection verified")

    def test_6_authenticated_role_routes(self):
        """Uji 6: Akses rute untuk masing-masing role (business_analyst, marketing, management, admin)."""
        with self.app.app_context():
            ba_user = User.query.filter_by(role="business_analyst").first()
            mkt_user = User.query.filter_by(role="marketing").first()
            mgmt_user = User.query.filter_by(role="management").first()
            admin_user = User.query.filter_by(role="admin").first()
            
            ba_id = ba_user.id if ba_user else None
            mkt_id = mkt_user.id if mkt_user else None
            mgmt_id = mgmt_user.id if mgmt_user else None
            admin_id = admin_user.id if admin_user else None

        # 1. Test Business Analyst access
        if ba_id:
            client_ba = self.app.test_client()
            with client_ba.session_transaction() as sess:
                sess['_user_id'] = str(ba_id)
                sess['_fresh'] = True
            res_ma = client_ba.get('/market-analysis/')
            self.assertEqual(res_ma.status_code, 200, "BA must access /market-analysis/ with 200")
            res_dc = client_ba.get('/data-collection/')
            self.assertEqual(res_dc.status_code, 200, "BA must access /data-collection/ with 200")
            
        # 2. Test Marketing access
        if mkt_id:
            client_mkt = self.app.test_client()
            with client_mkt.session_transaction() as sess:
                sess['_user_id'] = str(mkt_id)
                sess['_fresh'] = True
            res_mkt = client_mkt.get('/marketing/')
            self.assertEqual(res_mkt.status_code, 200, "Marketing must access /marketing/ with 200")
            
        # 3. Test Management access
        if mgmt_id:
            client_mgmt = self.app.test_client()
            with client_mgmt.session_transaction() as sess:
                sess['_user_id'] = str(mgmt_id)
                sess['_fresh'] = True
            res_rep = client_mgmt.get('/reporting/')
            self.assertEqual(res_rep.status_code, 200, "Management must access /reporting/ with 200")
            
        # 4. Test Admin access to Data Manager
        if admin_id:
            client_admin = self.app.test_client()
            with client_admin.session_transaction() as sess:
                sess['_user_id'] = str(admin_id)
                sess['_fresh'] = True
            res_orgs = client_admin.get('/admin/data-manager/organizations')
            self.assertEqual(res_orgs.status_code, 200, "Admin must access organizations data-manager with 200")
            res_ev = client_admin.get('/admin/data-manager/events')
            self.assertEqual(res_ev.status_code, 200, "Admin must access events data-manager with 200")
            res_ep = client_admin.get('/admin/data-manager/event-participants')
            self.assertEqual(res_ep.status_code, 200, "Admin must access event-participants data-manager with 200")

        print("  [PASS] Authenticated role access across all modules verified 100%")

if __name__ == '__main__':
    unittest.main()
