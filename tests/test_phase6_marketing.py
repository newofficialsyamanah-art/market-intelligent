"""Test Suite untuk Fase 6: Marketing Intelligence Workspace.

Memverifikasi:
1. Kalkulasi metrik Marketing Dashboard (pasar, skor prioritas, contactability, event-driven).
2. Target Intelligence & Account Explorer (pencarian, pemfilteran multi-dimensi).
3. B2B Segmentation Engine (6 preset segmentasi & drilldown).
4. Export Akun Target ke CSV (20+ kolom, UTF-8 BOM, kesiapan Excel).
5. Guardrail Bebas CRM: Tidak ada sales pipeline, deals, stages, atau lead tracking.
6. Akses Routes (/marketing/dashboard, /marketing/targets, /marketing/segments, /marketing/export).
"""

import json
import unittest
from datetime import datetime, timezone
from app import create_app
from app.extensions import db
from app.models import User, Organization, Event, EventParticipant, utc_now
from app.config import TestConfig
from app.services.marketing_intelligence import (
    MarketingIntelligenceService,
    SEGMENT_PRESETS,
)


class TestPhase6Marketing(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app.config["TESTING"] = True
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Dapatkan atau buat Marketing user
        self.mkt_user = User.query.filter_by(role="marketing").first()
        if not self.mkt_user:
            self.mkt_user = User(name="Marketing User Phase 6", email="mkt_phase6@example.com", role="marketing")
            db.session.add(self.mkt_user)
        self.mkt_user.set_password("Secret123!")

        # Dapatkan atau buat Business Analyst user
        self.ba_user = User.query.filter_by(role="business_analyst").first()
        if not self.ba_user:
            self.ba_user = User(name="BA User Phase 6", email="ba_phase6@example.com", role="business_analyst")
            db.session.add(self.ba_user)
        self.ba_user.set_password("Secret123!")

        db.session.commit()

        # Seed data uji khusus untuk marketing
        self.seed_orgs = []
        # Org 1: Hot target corporate
        org1 = Organization(
            name="[TEST] PT Finansial Prima Nusantara",
            normalized_name="finansial prima nusantara pt",
            domain="finansialprima-test.co.id",
            industry="Jasa Keuangan",
            product_fit="Seragam Kantor / Kemeja Formal",
            priority_tier="A - HOT",
            opportunity_score=95,
            phone="021-5551234",
            email="corporate@finansialprima-test.co.id",
            website="https://finansialprima-test.co.id",
            social_json=json.dumps({"linkedin": "https://linkedin.com/company/finansialprima"}),
            city="Jakarta Selatan",
            province="DKI Jakarta",
            created_at=utc_now(),
        )
        # Org 2: Industrial safety
        org2 = Organization(
            name="[TEST] PT Baja Konstruksi Mandiri",
            normalized_name="baja konstruksi mandiri pt",
            domain="bajamandiri-test.com",
            industry="Konstruksi & Manufaktur",
            product_fit="Wearpack Safety & Rompi Lapangan",
            priority_tier="B - WARM",
            opportunity_score=75,
            phone="031-8889999",
            email="procurement@bajamandiri-test.com",
            website="https://bajamandiri-test.com",
            city="Surabaya",
            province="Jawa Timur",
            created_at=utc_now(),
        )
        db.session.add_all([org1, org2])
        db.session.commit()
        self.seed_orgs = [org1, org2]

    def tearDown(self):
        db.session.rollback()
        Organization.query.filter(Organization.name.like("%[TEST]%")).delete()
        EventParticipant.query.filter(EventParticipant.notes.like("%[TEST]%")).delete()
        Event.query.filter(Event.name.like("%[TEST]%")).delete()
        db.session.commit()
        self.app_context.pop()

    def test_01_marketing_dashboard_metrics(self):
        metrics = MarketingIntelligenceService.get_marketing_dashboard_metrics()
        self.assertIn("total_organizations", metrics)
        self.assertIn("high_opportunity_count", metrics)
        self.assertIn("tier_distribution", metrics)
        self.assertIn("contactability", metrics)
        self.assertIn("event_driven", metrics)
        self.assertGreaterEqual(metrics["total_organizations"], 2)
        self.assertGreaterEqual(metrics["high_opportunity_count"], 1)

    def test_02_target_intelligence_search(self):
        # 1. Search by name
        items, count, pages = MarketingIntelligenceService.search_marketing_targets(
            q="Finansial Prima"
        )
        self.assertEqual(count, 1)
        self.assertEqual(items[0]["name"], "[TEST] PT Finansial Prima Nusantara")

        # 2. Filter by priority tier
        items_tier, count_tier, _ = MarketingIntelligenceService.search_marketing_targets(
            priority_tier="A - HOT"
        )
        self.assertGreaterEqual(count_tier, 1)
        self.assertTrue(all(it["priority_tier"] == "A - HOT" for it in items_tier))

        # 3. Filter by contactability
        items_contact, count_contact, _ = MarketingIntelligenceService.search_marketing_targets(
            has_email=True,
            has_phone=True
        )
        self.assertGreaterEqual(count_contact, 2)

    def test_03_segmentation_presets(self):
        presets = MarketingIntelligenceService.get_segment_presets_overview()
        self.assertGreaterEqual(len(presets), 11)
        keys = [p["key"] for p in presets]
        self.assertIn("corporate", keys)
        self.assertIn("manufacturing", keys)
        self.assertIn("textile", keys)
        self.assertIn("hot_targets", keys)
        self.assertIn("industrial", keys)
        self.assertIn("contactable_ready", keys)

        # Drilldown test
        drill_items, drill_count, _, info = MarketingIntelligenceService.get_segment_drilldown(
            preset_key="hot_targets"
        )
        self.assertGreaterEqual(drill_count, 1)
        self.assertEqual(info["key"], "hot_targets")

    def test_04_export_target_accounts(self):
        # Login Marketing
        res_login = self.client.post("/login", data={"email": self.mkt_user.email, "password": "Secret123!"})
        self.assertEqual(res_login.status_code, 302)

        res = self.client.get("/marketing/export?preset=hot_targets")
        self.assertEqual(res.status_code, 200)
        self.assertIn("text/csv", res.content_type)
        csv_text = res.data.decode("utf-8-sig")

        # Verifikasi 22 kolom F6.5
        expected_columns = [
            "organization", "organization_type", "industry", "product_fit",
            "opportunity_score", "priority_tier", "website", "domain",
            "instagram", "facebook", "linkedin", "phone", "email", "address",
            "city", "province", "employee_size", "event_count",
            "high_relevance_event_count", "latest_event", "source", "freshness"
        ]
        for col in expected_columns:
            self.assertIn(col, csv_text)

    def test_05_guardrail_no_crm(self):
        """Memastikan tidak ada sales pipeline, CRM deals, stages, atau lead tracking."""
        org_cols = [c.name for c in Organization.__table__.columns]
        self.assertNotIn("deal_stage", org_cols)
        self.assertNotIn("deal_amount", org_cols)
        self.assertNotIn("sales_pipeline", org_cols)
        self.assertNotIn("pipeline_stage", org_cols)
        self.assertNotIn("lead_status", org_cols)

    def test_06_marketing_routes(self):
        # Login BA (dapat melihat marketing workspace juga)
        res_login = self.client.post("/login", data={"email": self.ba_user.email, "password": "Secret123!"})
        self.assertEqual(res_login.status_code, 302)

        # 1. Dashboard
        res_dash = self.client.get("/marketing/dashboard")
        self.assertEqual(res_dash.status_code, 200)
        self.assertIn("Marketing Intelligence", res_dash.data.decode())

        # 2. Targets Explorer
        res_targets = self.client.get("/marketing/targets")
        self.assertEqual(res_targets.status_code, 200)
        self.assertIn("Target Intelligence", res_targets.data.decode())

        # 3. Segments
        res_seg = self.client.get("/marketing/segments")
        self.assertEqual(res_seg.status_code, 200)
        self.assertIn("Segmentation Engine", res_seg.data.decode())


if __name__ == "__main__":
    unittest.main()
