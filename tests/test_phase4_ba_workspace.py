"""Test Suite untuk Fase 4: BA / Business Analyst Workspace & Intelligence Analytics.

Memverifikasi:
1. Executive Overview Metrics (total orgs, avg score, high priority, contactability).
2. Industry & Regional Analytics (distribusi sektor & konsentrasi wilayah).
3. Company Segmentation (Priority Tiers A/B/C/D, organization types).
4. Product-Fit Analysis (demand breakdown produk apparel/merchandise).
5. Data Quality & Freshness Visibility (kelengkapan kontak & usia data).
6. White-Space Market Gap Analysis (kluster potensial tinggi berstatus discovered).
7. Company Intelligence Explorer (search, filter, pagination).
8. Detail Profil Master Organization & Provenance Audit Trail.
9. Route integration & RBAC protection (business_analyst & admin access).
10. Pengecekan Guardrail: Tidak ada CRM pipeline atau mutasi non-analitis pada master data.
"""

import os
import json
import unittest
from datetime import datetime, timezone, timedelta
from app import create_app
from app.extensions import db
from app.models import User, Organization, Prospect, DuplicateCandidate
from app.config import TestConfig
from app.services.intelligence_analytics import (
    get_executive_overview,
    get_industry_analytics,
    get_regional_analytics,
    get_segmentation_analysis,
    get_product_fit_matrix,
    get_data_quality_and_freshness,
    get_white_space_clusters,
    search_master_organizations,
    get_organization_detail,
)


class TestPhase4BAWorkspace(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app.config["TESTING"] = True
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Dapatkan atau buat Business Analyst user
        self.ba_user = User.query.filter_by(role="business_analyst").first()
        if not self.ba_user:
            self.ba_user = User(name="BA Analyst Phase 4", email="ba_phase4@example.com", role="business_analyst")
            db.session.add(self.ba_user)
        self.ba_user.set_password("Secret123!")

        # Dapatkan atau buat Marketing user untuk RBAC test
        self.mkt_user = User.query.filter_by(role="marketing").first()
        if not self.mkt_user:
            self.mkt_user = User(name="Marketing User Phase 4", email="mkt_phase4@example.com", role="marketing")
            db.session.add(self.mkt_user)
        self.mkt_user.set_password("Secret123!")
        db.session.commit()

        self.cleanup_org_ids = []

        # Buat seed data master Organization khusus pengujian analitik
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        self.test_org1 = Organization(
            name="PT Tekstil Mandiri Maju Phase4",
            normalized_name="tekstil mandiri maju phase4",
            domain="tekstilmandirip4.com",
            organization_type="Pabrik",
            industry="TEXTILE",
            city="Bandung",
            province="Jawa Barat",
            phone="022-777111",
            email="info@tekstilmandirip4.com",
            website="https://tekstilmandirip4.com",
            social_json=json.dumps({"instagram": "https://instagram.com/tekstilmandiri", "linkedin": "https://linkedin.com/company/tekstilmandiri"}),
            product_fit="Jaket, Kaos, Polo Shirt, Seragam, Wearpack",
            opportunity_score=85,
            priority_tier="A - HOT",
            verification_status="verified",
            provenance_json=json.dumps([{
                "source_type": "bps_upload",
                "source_id": 1,
                "raw_name": "PT Tekstil Mandiri Maju Phase4",
                "match_tier": "initial_creation",
                "confidence": 1.0,
                "merged_at": now.isoformat()
            }]),
            data_freshness=now,
            last_seen=now
        )

        self.test_org2 = Organization(
            name="CV Otomotif Perkasa Phase4",
            normalized_name="otomotif perkasa phase4",
            domain="otomotifp4.com",
            organization_type="Perusahaan",
            industry="AUTOMOTIVE",
            city="Surabaya",
            province="Jawa Timur",
            phone="031-555222",
            email="sales@otomotifp4.com",
            website="https://otomotifp4.com",
            product_fit="Jaket, Polo Shirt, Wearpack",
            opportunity_score=68,
            priority_tier="B - WARM",
            verification_status="discovered",
            provenance_json=json.dumps([{
                "source_type": "bps_upload",
                "source_id": 2,
                "raw_name": "CV Otomotif Perkasa Phase4",
                "match_tier": "initial_creation",
                "confidence": 1.0,
                "merged_at": now.isoformat()
            }]),
            data_freshness=now,
            last_seen=now
        )

        self.test_org3 = Organization(
            name="PT Mitra Pangan Sejahtera Phase4",
            normalized_name="mitra pangan sejahtera phase4",
            domain=None,
            organization_type="Perusahaan",
            industry="FOOD / F&B",
            city="Semarang",
            province="Jawa Tengah",
            phone=None,
            email=None,
            website=None,
            product_fit="Kaos, Polo Shirt, Seragam",
            opportunity_score=40,
            priority_tier="D - LOW",
            verification_status="discovered",
            data_freshness=now - timedelta(days=120),  # Stale data
            last_seen=now - timedelta(days=120)
        )

        db.session.add_all([self.test_org1, self.test_org2, self.test_org3])
        db.session.flush()
        self.cleanup_org_ids.extend([self.test_org1.id, self.test_org2.id, self.test_org3.id])

        # Buat test DuplicateCandidate yang terhubung ke test_org1
        self.test_candidate = DuplicateCandidate(
            organization_id=self.test_org1.id,
            candidate_name="PT Tekstil Mandiri Maju (Cabang Cimahi)",
            candidate_source="bps_upload:99",
            match_tier="tier4_fuzzy_candidate",
            confidence_score=0.91,
            status="pending"
        )
        db.session.add(self.test_candidate)
        db.session.commit()

    def tearDown(self):
        if self.cleanup_org_ids:
            DuplicateCandidate.query.filter(DuplicateCandidate.organization_id.in_(self.cleanup_org_ids)).delete(synchronize_session=False)
            Prospect.query.filter(Prospect.organization_id.in_(self.cleanup_org_ids)).delete(synchronize_session=False)
            Organization.query.filter(Organization.id.in_(self.cleanup_org_ids)).delete(synchronize_session=False)
            db.session.commit()
        self.app_context.pop()

    def test_1_executive_overview_metrics(self):
        """Uji 1: Executive Overview menghitung metrik master organizations dengan benar."""
        overview = get_executive_overview()
        self.assertGreaterEqual(overview["total_orgs"], 3)
        self.assertGreater(overview["avg_opportunity_score"], 0)
        self.assertGreaterEqual(overview["high_priority_count"], 2)  # test_org1 (85) and test_org2 (68)
        self.assertGreater(overview["contactability_rate"], 0.0)
        self.assertGreaterEqual(overview["pending_candidates_count"], 1)
        print("  [PASS] Test 1: Executive Overview Metrics verified.")

    def test_2_industry_and_regional_analytics(self):
        """Uji 2: Analisis Sektor Industri dan Persebaran Geografis."""
        ind_analytics = get_industry_analytics(limit=15)
        self.assertIsInstance(ind_analytics, list)
        self.assertGreater(len(ind_analytics), 0)
        industries_found = [item["industry"] for item in ind_analytics]
        self.assertIn("TEXTILE", industries_found)

        reg_analytics = get_regional_analytics(limit=10)
        self.assertIn("by_province", reg_analytics)
        self.assertIn("by_city", reg_analytics)
        provinces = [p["province"].upper() for p in reg_analytics["by_province"]]
        self.assertIn("JAWA BARAT", provinces)
        print("  [PASS] Test 2: Industry & Regional Analytics verified.")

    def test_3_company_segmentation(self):
        """Uji 3: Segmentasi Priority Tier dan Tipe Organisasi."""
        seg = get_segmentation_analysis()
        self.assertIn("tiers", seg)
        self.assertIn("types", seg)
        self.assertGreaterEqual(seg["tiers"]["A - HOT"], 1)
        self.assertGreaterEqual(seg["tiers"]["B - WARM"], 1)
        print("  [PASS] Test 3: Company Segmentation verified.")

    def test_4_product_fit_matrix(self):
        """Uji 4: Product-Fit Matrix breakdown produk apparel & merchandise."""
        matrix = get_product_fit_matrix()
        self.assertIsInstance(matrix, list)
        prod_keys = [m["product_key"] for m in matrix]
        self.assertIn("Wearpack", prod_keys)
        self.assertIn("Seragam", prod_keys)
        self.assertIn("Jaket", prod_keys)
        self.assertIn("Polo Shirt", prod_keys)
        self.assertIn("Kaos", prod_keys)
        for item in matrix:
            self.assertIn("count", item)
            self.assertIn("percentage", item)
            self.assertIn("avg_score", item)
        print("  [PASS] Test 4: Product-Fit Matrix verified.")

    def test_5_data_quality_and_freshness_visibility(self):
        """Uji 5: Metrik kelengkapan profil dan visibilitas kebaruan data master."""
        dq = get_data_quality_and_freshness()
        self.assertIn("phone_pct", dq)
        self.assertIn("email_pct", dq)
        self.assertIn("domain_pct", dq)
        self.assertIn("address_pct", dq)
        self.assertIn("fresh_30d", dq)
        self.assertIn("older_90d", dq)
        self.assertGreater(dq["fresh_30d"], 0)
        print("  [PASS] Test 5: Data Quality & Freshness Visibility verified.")

    def test_6_white_space_clusters(self):
        """Uji 6: White-Space Market Gap Analysis mengidentifikasi kluster belum tersentuh."""
        clusters = get_white_space_clusters(limit=10)
        self.assertIsInstance(clusters, list)
        for c in clusters:
            self.assertIn("province", c)
            self.assertIn("industry", c)
            self.assertIn("count", c)
            self.assertIn("avg_score", c)
            self.assertIn("potential_tag", c)
        print("  [PASS] Test 6: White-Space Market Gap Analysis verified.")

    def test_7_company_explorer_search_and_filters(self):
        """Uji 7: Pencarian, filter, dan pagination Master Organization di Explorer."""
        # 1. Search by name query
        items_q, total_q, _ = search_master_organizations(q="Tekstil Mandiri Maju")
        self.assertGreaterEqual(total_q, 1)
        self.assertEqual(items_q[0].name, self.test_org1.name)

        # 2. Filter by industry
        items_ind, total_ind, _ = search_master_organizations(industry="AUTOMOTIVE")
        self.assertGreaterEqual(total_ind, 1)
        self.assertTrue(any(o.industry == "AUTOMOTIVE" for o in items_ind))

        # 3. Filter by priority tier
        items_tier, total_tier, _ = search_master_organizations(priority_tier="A - HOT")
        self.assertGreaterEqual(total_tier, 1)
        self.assertTrue(any("A" in (o.priority_tier or "") for o in items_tier))

        # 4. Filter by min score
        items_score, total_score, _ = search_master_organizations(min_score=80)
        self.assertGreaterEqual(total_score, 1)
        for o in items_score:
            self.assertGreaterEqual(o.opportunity_score, 80)

        # 5. Filter has_contact
        items_contact, total_contact, _ = search_master_organizations(has_contact=True)
        self.assertGreater(total_contact, 0)
        for o in items_contact:
            has_c = bool(o.phone or o.email or o.domain)
            self.assertTrue(has_c)

        print("  [PASS] Test 7: Company Intelligence Explorer Search & Filters verified.")

    def test_8_organization_detail_and_provenance(self):
        """Uji 8: Detail Profil Master Organization dan Audit Trail Provenance."""
        detail = get_organization_detail(self.test_org1.id)
        self.assertIsNotNone(detail)
        self.assertEqual(detail["organization"].id, self.test_org1.id)
        self.assertEqual(len(detail["provenance"]), 1)
        self.assertEqual(detail["provenance"][0]["match_tier"], "initial_creation")
        self.assertEqual(len(detail["candidates"]), 1)
        self.assertEqual(detail["candidates"][0]["candidate_name"], "PT Tekstil Mandiri Maju (Cabang Cimahi)")
        # Verifikasi parsing social media terstruktur
        self.assertIn("social", detail)
        self.assertEqual(detail["social"]["instagram"], "https://instagram.com/tekstilmandiri")
        self.assertEqual(detail["social"]["linkedin"], "https://linkedin.com/company/tekstilmandiri")
        self.assertIsNone(detail["social"]["facebook"])
        print("  [PASS] Test 8: Organization Detail, Provenance Audit Trail & Social Media verified.")

    def test_9_routes_and_rbac_protection(self):
        """Uji 9: Rute HTTP BA Workspace berfungsi dan dilindungi RBAC."""
        # Unauthenticated request -> Redirect to login
        res_unauth = self.client.get("/market-analysis/")
        self.assertEqual(res_unauth.status_code, 302)

        # Login sebagai Business Analyst
        client_ba = self.app.test_client()
        res_login_ba = client_ba.post("/login", data={"email": self.ba_user.email, "password": "Secret123!"})
        self.assertEqual(res_login_ba.status_code, 302)

        # Dashboard BA Workspace
        res_dash = client_ba.get("/market-analysis/")
        self.assertEqual(res_dash.status_code, 200)
        self.assertIn(b"Business Analyst Workspace", res_dash.data)
        self.assertIn(b"Master Organizations", res_dash.data)

        # Explorer View
        res_exp = client_ba.get("/market-analysis/explorer")
        self.assertEqual(res_exp.status_code, 200)
        self.assertIn(b"Company Intelligence Explorer", res_exp.data)

        # Organization Detail View (Termasuk tampilan link social media nyata)
        res_det = client_ba.get(f"/market-analysis/organization/{self.test_org1.id}")
        self.assertEqual(res_det.status_code, 200)
        self.assertIn(self.test_org1.name.encode(), res_det.data)
        self.assertIn(b"Provenance Audit Trail", res_det.data)
        self.assertIn(b"https://instagram.com/tekstilmandiri", res_det.data)
        self.assertIn(b"https://linkedin.com/company/tekstilmandiri", res_det.data)

        # Non-existent organization detail -> Redirects to explorer
        res_404 = client_ba.get("/market-analysis/organization/99999999")
        self.assertEqual(res_404.status_code, 302)

        # Logout BA
        client_ba.get("/logout")

        # Login sebagai Marketing (roles_required business_analyst only -> 403 Forbidden)
        client_mkt = self.app.test_client()
        res_login_mkt = client_mkt.post("/login", data={"email": self.mkt_user.email, "password": "Secret123!"})
        self.assertEqual(res_login_mkt.status_code, 302)
        res_mkt = client_mkt.get("/market-analysis/")
        self.assertEqual(res_mkt.status_code, 403)

        print("  [PASS] Test 9: Routes & RBAC Protection verified.")

    def test_10_guardrail_check_not_a_crm(self):
        """Uji 10: Memastikan fitur Phase 4 tidak memperkenalkan sales pipeline, CRM deal stages, atau mengubah master entity."""
        # 1. Master Organization tidak memiliki kolom deal stage atau CRM pipeline
        org_cols = [c.name for c in Organization.__table__.columns]
        self.assertNotIn("deal_stage", org_cols)
        self.assertNotIn("sales_pipeline", org_cols)
        self.assertNotIn("deal_value", org_cols)

        # 2. organizations tetap single source of truth untuk company intelligence
        org = db.session.get(Organization, self.test_org1.id)
        self.assertEqual(org.organization_type, "Pabrik")
        self.assertEqual(org.opportunity_score, 85)

        # 3. Isolasi Database Testing: Pastikan test suite berjalan pada market_intelligence_test
        self.assertIn("market_intelligence_test", self.app.config["SQLALCHEMY_DATABASE_URI"])

        print("  [PASS] Test 10: Guardrail Check (Pure Intelligence Workspace, No CRM, Test DB Isolated) verified.")


if __name__ == "__main__":
    unittest.main()
