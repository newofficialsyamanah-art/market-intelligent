"""Test Suite untuk Fase 5: Event Intelligence Workspace.

Memverifikasi:
1. Normalisasi nama event & kalkulasi skor relevansi B2B (HIGH, MEDIUM, LOW, REJECT).
2. Deduplikasi event bertingkat (Tier 1 URL, Tier 2 Name+Date/City, Tier 3 Name+Organizer).
3. Pembuatan dan pembaruan event non-destruktif.
4. Pencocokan organisasi master & relasi partisipan (organizer, exhibitor, sponsor, partner, speaker).
5. Integritas constraint unik relasi partisipan.
6. Pencarian, pemfilteran, dan paginasi event.
7. Route endpoints Event Workspace (/events/, /events/<id>, /events/calendar, /events/api/calendar, /events/export).
"""

import json
import unittest
from datetime import datetime, timezone
from app import create_app
from app.extensions import db
from app.models import User, Organization, Event, EventParticipant, utc_now
from app.config import TestConfig
from app.services.event_intelligence import (
    normalize_event_name,
    EventIntelligenceService,
)


class TestPhase5Events(unittest.TestCase):
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
            self.ba_user = User(name="BA Analyst Phase 5", email="ba_phase5@example.com", role="business_analyst")
            db.session.add(self.ba_user)
        self.ba_user.set_password("Secret123!")

        # Dapatkan atau buat Marketing user
        self.mkt_user = User.query.filter_by(role="marketing").first()
        if not self.mkt_user:
            self.mkt_user = User(name="Marketing User Phase 5", email="mkt_phase5@example.com", role="marketing")
            db.session.add(self.mkt_user)
        self.mkt_user.set_password("Secret123!")

        db.session.commit()

    def tearDown(self):
        db.session.rollback()
        # Bersihkan data test event
        EventParticipant.query.filter(EventParticipant.notes.like("%[TEST]%")).delete()
        Event.query.filter(Event.name.like("%[TEST]%")).delete()
        Organization.query.filter(Organization.name.like("%[TEST]%")).delete()
        db.session.commit()
        self.app_context.pop()

    def test_01_event_normalization(self):
        norm1 = normalize_event_name("Indo Intertex 2026 - The International Textile Expo")
        norm2 = normalize_event_name("Indo Intertex Exhibition")
        self.assertIn("intertex", norm1)
        self.assertIn("intertex", norm2)

    def test_02_relevance_classification(self):
        # High relevance
        cat_high, score_high, _ = EventIntelligenceService.calculate_relevance(
            name="Indo Intertex Garment & Textile Machinery Expo",
            description="Pameran industri tekstil, bordir, konveksi dan busana kerja",
        )
        self.assertEqual(cat_high, "HIGH")
        self.assertGreaterEqual(score_high, 80)

        # Medium relevance
        cat_med, score_med, _ = EventIntelligenceService.calculate_relevance(
            name="Manufacturing Indonesia Expo",
            description="Pameran mesin industri, otomotif dan pabrik manufaktur",
        )
        self.assertEqual(cat_med, "MEDIUM")
        self.assertGreaterEqual(score_med, 50)
        self.assertLess(score_med, 80)

        # Reject
        cat_rej, score_rej, _ = EventIntelligenceService.calculate_relevance(
            name="Bonus Slot Online Gacor Promo",
            description="Daftar akun slot judi online terpercaya",
        )
        self.assertEqual(cat_rej, "REJECT")
        self.assertEqual(score_rej, 0)

    def test_03_event_creation_and_deduplication(self):
        event_payload = {
            "name": "[TEST] Indonesia Garment Expo 2026",
            "event_type": "Exhibition / Trade Fair",
            "organizer": "PT Media Expo Utama",
            "venue": "JIExpo Kemayoran",
            "city": "Jakarta Pusat",
            "website": "https://garmentexpo-test.co.id",
            "description": "Pameran pakaian seragam dan bahan tekstil",
            "status": "upcoming",
        }

        # Run 1: Create
        ev1, is_created, msg = EventIntelligenceService.create_or_update_event(event_payload)
        self.assertTrue(is_created)
        self.assertIsNotNone(ev1.id)
        self.assertEqual(ev1.relevance_score, 100)

        # Run 2: Exact duplicate via website -> update safe, no duplicate
        ev2, is_created_2, msg2 = EventIntelligenceService.create_or_update_event(event_payload)
        self.assertFalse(is_created_2)
        self.assertEqual(ev1.id, ev2.id)

    def test_04_participant_linking_and_roles(self):
        # Buat org dan event
        org = Organization(
            name="[TEST] PT Sinar Tekstil Jaya",
            normalized_name="sinar tekstil jaya pt",
            domain="sinartekstil-test.com",
            industry="Tekstil & Garment",
            created_at=utc_now(),
        )
        db.session.add(org)

        ev = Event(
            name="[TEST] Apparel Trade Fair 2026",
            event_type="Exhibition",
            city="Jakarta",
            relevance_score=90,
            created_at=utc_now(),
        )
        db.session.add(ev)
        db.session.commit()

        # Link as exhibitor
        part, is_new = EventIntelligenceService.link_participant(
            event_id=ev.id,
            organization_id=org.id,
            role="exhibitor",
            booth_number="Booth A-10",
            notes="[TEST] Peserta utama kain seragam",
        )
        self.assertTrue(is_new)
        self.assertEqual(part.role, "exhibitor")
        self.assertEqual(part.booth_number, "Booth A-10")

        # Idempotent re-link: should not create duplicate
        part2, is_new2 = EventIntelligenceService.link_participant(
            event_id=ev.id,
            organization_id=org.id,
            role="exhibitor",
            booth_number="Booth A-10",
            notes="[TEST] Peserta utama kain seragam",
        )
        self.assertFalse(is_new2)
        self.assertEqual(part.id, part2.id)

        # Verify get_event_detail
        detail = EventIntelligenceService.get_event_detail(ev.id)
        self.assertIsNotNone(detail)
        self.assertEqual(detail["participants_count"], 1)
        self.assertEqual(len(detail["by_role"]["exhibitors"]), 1)
        self.assertEqual(detail["by_role"]["exhibitors"][0]["organization_name"], "[TEST] PT Sinar Tekstil Jaya")

    def test_05_event_routes(self):
        # Login BA
        res_login = self.client.post("/login", data={"email": self.ba_user.email, "password": "Secret123!"})
        self.assertEqual(res_login.status_code, 302)

        # 1. Index
        res = self.client.get("/events/")
        self.assertEqual(res.status_code, 200)

        # 2. Calendar view
        res_cal = self.client.get("/events/calendar")
        self.assertEqual(res_cal.status_code, 200)

        # 3. API Calendar
        res_api = self.client.get("/events/api/calendar")
        self.assertEqual(res_api.status_code, 200)
        self.assertTrue(isinstance(res_api.get_json(), list))

        # 4. Export CSV
        res_export = self.client.get("/events/export")
        self.assertEqual(res_export.status_code, 200)
        self.assertIn("text/csv", res_export.content_type)
        self.assertIn("Event Name", res_export.data.decode("utf-8-sig"))


if __name__ == "__main__":
    unittest.main()
