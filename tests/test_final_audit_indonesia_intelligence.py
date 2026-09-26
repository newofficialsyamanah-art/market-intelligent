"""Comprehensive Verification Suite for Indonesia Market & Organization Intelligence.

Tests covering:
1. Education Discovery Universe (PAUD to Universitas, Kemdikbud sources, provenance, idempotency)
2. Community & Student Organization Discovery (Sports clubs, futsal, running, BEM/HIMA/UKM)
3. Social Discovery & Enrichment (Instagram, TikTok, Facebook, LinkedIn signals: product, sport, activity)
4. Explainable AI Product Fit Scoring (Jersey / Custom Teamwear, evidence, reasoning, fallback)
5. Marketing Campaign Management (Creation, Target assignment, snapshots, status, export, duplicate protection)
6. Cron Automation & Execution Tracking (10 task types, metrics, manual run, retry)
7. Role-Based Dashboard Integrity (admin, business_analyst, marketing, management)
8. End-to-End Pipeline Integration (Discovery -> Master Org -> Social -> Event -> AI Fit -> Campaign)
"""

import json
import unittest
from datetime import datetime, timezone

from app import create_app
from app.config import TestConfig
from app.extensions import db
from app.models import (
    ActivityLog,
    Campaign,
    CampaignTarget,
    CronJob,
    DiscoverySource,
    DuplicateCandidate,
    Event,
    EventParticipant,
    Organization,
    Prospect,
    User,
    utc_now,
)
from app.scheduler import TASK_TYPES, execute_job, is_scheduler_running
from app.services.discovery_service import DiscoveryPipelineService
from app.services.marketing_intelligence import MarketingIntelligenceService
from app.services.product_fit_service import ProductFitService
from app.services.social_connector import SocialConnectorService


class TestFinalAuditIndonesiaIntelligence(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app.config["TESTING"] = True
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Seed users for RBAC testing
        self.admin = self._get_or_create_user("Admin Audit", "admin_audit@example.com", "admin")
        self.ba = self._get_or_create_user("BA Audit", "ba_audit@example.com", "business_analyst")
        self.mkt = self._get_or_create_user("Marketing Audit", "mkt_audit@example.com", "marketing")
        self.mgmt = self._get_or_create_user("Management Audit", "mgmt_audit@example.com", "management")

    def tearDown(self):
        db.session.remove()
        self.app_context.pop()

    def _get_or_create_user(self, name, email, role):
        u = User.query.filter_by(email=email).first()
        if not u:
            u = User(name=name, email=email, role=role)
            u.set_password("Secret123!")
            db.session.add(u)
            db.session.commit()
        return u

    def _login(self, user):
        self.client.get("/logout", follow_redirects=True)
        return self.client.post("/login", data={"email": user.email, "password": "Secret123!"}, follow_redirects=True)

    # =========================================================================
    # 1. Education Discovery Universe
    # =========================================================================
    def test_01_education_discovery_universe(self):
        """Memverifikasi discovery institusi pendidikan Indonesia (PAUD - Universitas)
        dengan provenance yang valid dan idempotensi tinggi.
        """
        res = DiscoveryPipelineService.discover_education_institutions(
            province="Jawa Barat", city="Bandung", limit_per_level=2
        )
        self.assertGreater(res["total_ingested"], 0, "Harus menemukan dan menyerap institusi pendidikan")
        self.assertGreaterEqual(res["new_organizations"] + res["matched_organizations"], res["total_ingested"])

        # Verifikasi record Master Organization yang tercipta
        edu_org = Organization.query.filter(
            Organization.organization_type == "education",
            Organization.city == "Bandung"
        ).first()
        self.assertIsNotNone(edu_org, "Master Organization pendidikan harus tersimpan")
        self.assertIn(edu_org.organization_subtype, ["university", "high_school", "vocational_school", "junior_high", "primary_school"])

        # Verifikasi Provenance
        prov_data = json.loads(edu_org.provenance_json) if edu_org.provenance_json else []
        provenance = prov_data[0] if isinstance(prov_data, list) and prov_data else (prov_data if isinstance(prov_data, dict) else {})
        self.assertEqual(provenance.get("source_type"), "education_directory")
        self.assertIsNotNone(provenance.get("confidence"))

        # Verifikasi Idempotensi (rerun tidak menduplikasi)
        count_before = Organization.query.count()
        rerun_res = DiscoveryPipelineService.discover_education_institutions(
            province="Jawa Barat", city="Bandung", limit_per_level=2
        )
        count_after = Organization.query.count()
        self.assertEqual(count_before, count_after, "Rerun tidak boleh menambah record duplikat")
        self.assertEqual(rerun_res["new_organizations"], 0, "Semua data harus ter-match secara idempotent")

    # =========================================================================
    # 2. Community & Student Organization Discovery
    # =========================================================================
    def test_02_community_and_student_discovery(self):
        """Memverifikasi discovery komunitas olahraga dan organisasi mahasiswa."""
        # 1. Komunitas Olahraga (Futsal)
        res_sports = DiscoveryPipelineService.discover_communities(category="futsal", city="Bandung", limit=3)
        self.assertGreater(res_sports["total_ingested"], 0)

        futsal_org = Organization.query.filter(
            Organization.sport == "futsal",
            Organization.city == "Bandung"
        ).first()
        self.assertIsNotNone(futsal_org, "Klub futsal harus tercatat")
        self.assertEqual(futsal_org.organization_type, "community")
        self.assertEqual(futsal_org.organization_subtype, "futsal_club")

        # 2. Organisasi Mahasiswa (BEM / UKM)
        res_student = DiscoveryPipelineService.discover_communities(category="student_org", city="Bandung", limit=2)
        self.assertGreater(res_student["total_ingested"], 0)

        student_org = Organization.query.filter(
            Organization.organization_type == "student_org"
        ).first()
        self.assertIsNotNone(student_org, "Organisasi mahasiswa harus tercatat")
        self.assertEqual(student_org.organization_subtype, "student_organization")

    # =========================================================================
    # 3. Social Discovery, Enrichment & Signal Extraction
    # =========================================================================
    def test_03_social_discovery_and_signal_extraction(self):
        """Memverifikasi ekstraksi sinyal produk, olahraga, aktivitas serta social discovery."""
        # 1. Ekstraksi Sinyal dari Bio / Post
        sample_bio = (
            "Official UKM Futsal Universitas Nusantara. Juara 1 Turnamen Futsal Cup 2026. "
            "Pemesanan custom jersey apparel & seragam tim hubungi DM."
        )
        signals = SocialConnectorService.extract_social_signals(sample_bio)
        self.assertIn("jersey", signals["product_signals"])
        self.assertIn("seragam", signals["product_signals"])
        self.assertIn("apparel", signals["product_signals"])
        self.assertIn("futsal", signals["sport_signals"])
        self.assertIn("turnamen", signals["activity_signals"])
        self.assertTrue(signals["jersey_relevance"])

        # 2. URL Parsing Legitimate
        ig_parsed = SocialConnectorService.parse_social_profile_url("https://www.instagram.com/futsal_garuda_fc/")
        self.assertEqual(ig_parsed["platform"], "instagram")
        self.assertEqual(ig_parsed["username"], "futsal_garuda_fc")

        tiktok_parsed = SocialConnectorService.parse_social_profile_url("https://www.tiktok.com/@runner_bandung")
        self.assertEqual(tiktok_parsed["platform"], "tiktok")
        self.assertEqual(tiktok_parsed["username"], "runner_bandung")

        # 3. Social Discovery Candidate
        connector = SocialConnectorService()
        social_candidates = connector.discover_social_candidates(
            platform="instagram", query="jersey futsal bandung", limit=2
        )
        self.assertGreater(len(social_candidates), 0)
        self.assertEqual(social_candidates[0]["source_platform"], "instagram")
        self.assertIn("instagram.com", social_candidates[0]["source_url"])

    # =========================================================================
    # 4. Explainable AI Product Fit Scoring
    # =========================================================================
    def test_04_explainable_ai_product_fit_scoring(self):
        """Memverifikasi scoring AI Product Fit yang explainable, berlandaskan evidence tanpa mengarang."""
        org = Organization(
            name="Bandung Tigers Futsal Club",
            organization_type="community",
            organization_subtype="futsal_club",
            sport="futsal",
            city="Bandung",
            province="Jawa Barat",
            description="Klub futsal aktif turnamen regional membutuhkan jersey kompetisi",
            website="https://instagram.com/bandungtigersfutsal",
        )
        db.session.add(org)
        db.session.commit()

        # Jalankan evaluasi
        eval_result = ProductFitService.evaluate_organization(org, target_product="Jersey / Custom Teamwear")

        self.assertIn("product_fit_score", eval_result)
        self.assertIn("product_fit_label", eval_result)
        self.assertIn("reasoning", eval_result)
        self.assertIn("evidence_used", eval_result)
        self.assertIn("confidence", eval_result)
        self.assertIn("scored_at", eval_result)

        # Harus menghasilkan High Fit untuk klub futsal aktif
        self.assertGreaterEqual(eval_result["product_fit_score"], 70)
        self.assertIn(eval_result["product_fit_label"], ["High Fit", "High", "Medium Fit", "Medium"])
        self.assertGreater(len(eval_result["evidence_used"]), 0, "Evidence harus tersedia")

        # Verifikasi persistence dan property helper model
        db.session.refresh(org)
        self.assertIsNotNone(org.ai_scoring_json)
        self.assertEqual(org.ai_product_fit_label, eval_result["product_fit_label"])
        self.assertIsNotNone(org.ai_product_fit_score)
        self.assertTrue(len(org.ai_evidence) > 0)
        self.assertIn("futsal", org.ai_reasoning.lower())

    # =========================================================================
    # 5. Marketing Campaign Management (Intelligence Integration)
    # =========================================================================
    def test_05_campaign_management_lifecycle(self):
        """Memverifikasi siklus Campaign Management: pembuatan, penugasan target snapshot,
        deduplikasi target, pembaruan status, dan ekspor CSV.
        """
        self._login(self.mkt)

        # 1. Buat Campaign Baru
        create_resp = self.client.post("/marketing/campaigns/new", data={
            "name": "Q4 Jersey Futsal Championship Campaign",
            "product": "Jersey / Custom Teamwear",
            "target_segment": "Sports Clubs & Communities",
            "organization_type": "community",
            "province": "Jawa Barat",
            "city": "Bandung",
            "channel": "WhatsApp / Social DM",
            "description": "Kampanye penawaran jersey custom untuk klub futsal regional.",
            "status": "active",
        }, follow_redirects=True)
        self.assertEqual(create_resp.status_code, 200)

        camp = Campaign.query.filter_by(name="Q4 Jersey Futsal Championship Campaign").first()
        self.assertIsNotNone(camp)
        self.assertEqual(camp.product, "Jersey / Custom Teamwear")

        # Buat org target
        org1 = Organization(
            name="Target Futsal Nusantara",
            organization_type="community",
            sport="futsal",
            opportunity_score=88,
            product_fit="high",
            city="Bandung",
        )
        db.session.add(org1)
        db.session.commit()

        # 2. Tambah Target ke Campaign
        add_resp = self.client.post(f"/marketing/campaigns/{camp.id}/add-targets", data={
            "organization_ids": str(org1.id),
            "notes": "Target prioritas tinggi turnamen",
        }, follow_redirects=True)
        self.assertEqual(add_resp.status_code, 200)

        target = CampaignTarget.query.filter_by(campaign_id=camp.id, organization_id=org1.id).first()
        self.assertIsNotNone(target)
        self.assertEqual(target.opportunity_score_snapshot, 88)
        self.assertEqual(target.product_fit_snapshot, "high")
        self.assertEqual(target.status, "selected")

        # 3. Pencegahan Duplikasi Target (Idempotensi)
        self.client.post(f"/marketing/campaigns/{camp.id}/add-targets", data={
            "organization_ids": str(org1.id),
        }, follow_redirects=True)
        targets_count = CampaignTarget.query.filter_by(campaign_id=camp.id, organization_id=org1.id).count()
        self.assertEqual(targets_count, 1, "Target yang sama tidak boleh diduplikasi dalam campaign")

        # 4. Update Status Target
        status_resp = self.client.post(f"/marketing/campaigns/{camp.id}/targets/{org1.id}/status", data={
            "status": "contacted",
            "notes": "Sudah dikirimkan katalog via DM",
        }, follow_redirects=True)
        self.assertEqual(status_resp.status_code, 200)
        db.session.refresh(target)
        self.assertEqual(target.status, "contacted")

        # 5. Export Targets ke CSV
        export_resp = self.client.get(f"/marketing/campaigns/{camp.id}/export-targets")
        self.assertEqual(export_resp.status_code, 200)
        self.assertIn("text/csv", export_resp.content_type)
        csv_text = export_resp.data.decode("utf-8-sig")
        self.assertIn("Target Futsal Nusantara", csv_text)
        self.assertIn("Q4 Jersey Futsal Championship Campaign", csv_text)

        # 6. Hapus Target
        del_resp = self.client.post(f"/marketing/campaigns/{camp.id}/targets/{org1.id}/remove", follow_redirects=True)
        self.assertEqual(del_resp.status_code, 200)
        self.assertIsNone(CampaignTarget.query.filter_by(campaign_id=camp.id, organization_id=org1.id).first())

    # =========================================================================
    # 6. Cron Automation & Execution Tracking
    # =========================================================================
    def test_06_cron_automation_and_manual_execution(self):
        """Memverifikasi 10 task types cron, eksekusi nyata, tracking metrik performa,
        dan fungsi manual run / retry.
        """
        self._login(self.admin)

        # 1. Verifikasi kelengkapan TASK_TYPES
        required_tasks = {
            "education_discovery", "community_discovery", "social_discovery",
            "social_enrichment", "event_refresh", "ai_product_scoring",
            "data_quality_check", "duplicate_detection", "retry_failed_jobs",
            "cache_maintenance"
        }
        for task in required_tasks:
            self.assertIn(task, TASK_TYPES)

        # 2. Buat CronJob untuk AI Product Fit Scoring
        job = CronJob(
            name="Audit Test AI Scoring Job",
            task_type="ai_product_scoring",
            schedule_cron="0 3 * * *",
            is_active=True,
        )
        db.session.add(job)
        db.session.commit()

        # 3. Jalankan Manual Execution via execute_job
        execute_job(self.app, job.id, force=True)

        # 4. Verifikasi metrik tercatat nyata
        db.session.commit()
        db.session.refresh(job)
        self.assertEqual(job.last_status, "success")
        self.assertIsNotNone(job.duration_seconds)
        self.assertGreaterEqual(job.duration_seconds, 0)
        self.assertIsNotNone(job.records_processed)
        self.assertIsNotNone(job.next_run)

        # 5. Uji Route POST /admin/cron-jobs/<jid>/run
        run_resp = self.client.post(f"/admin/cron-jobs/{job.id}/run", follow_redirects=True)
        self.assertEqual(run_resp.status_code, 200)

        # 6. Uji Helper is_scheduler_running
        scheduler_status = is_scheduler_running()
        self.assertIsInstance(scheduler_status, bool)

    # =========================================================================
    # 7. Role-Based Dashboard Views
    # =========================================================================
    def test_07_role_based_dashboards(self):
        """Memverifikasi main dashboard (/) menampilkan view spesifik per role
        tanpa menghilangkan fitur atau menyebabkan error template.
        """
        # 1. Admin Dashboard
        self._login(self.admin)
        resp_admin = self.client.get("/")
        self.assertEqual(resp_admin.status_code, 200)
        html_admin = resp_admin.data.decode("utf-8")
        self.assertIn("Administrator", html_admin)
        self.assertIn("Scheduler Status", html_admin)
        self.assertIn("Status Scheduled Cron Jobs", html_admin)

        # 2. Business Analyst Dashboard
        self._login(self.ba)
        resp_ba = self.client.get("/")
        self.assertEqual(resp_ba.status_code, 200)
        html_ba = resp_ba.data.decode("utf-8")
        self.assertIn("Business Analyst", html_ba)
        self.assertIn("Master Organizations (SSoT)", html_ba)
        self.assertIn("Cakupan Taksonomi", html_ba)

        # 3. Marketing Dashboard
        self._login(self.mkt)
        resp_mkt = self.client.get("/")
        self.assertEqual(resp_mkt.status_code, 200)
        html_mkt = resp_mkt.data.decode("utf-8")
        self.assertIn("Marketing", html_mkt)
        self.assertIn("High Product Fit", html_mkt)
        self.assertIn("Active Campaigns", html_mkt)

        # 4. Management Dashboard
        self._login(self.mgmt)
        resp_mgmt = self.client.get("/")
        self.assertEqual(resp_mgmt.status_code, 200)
        html_mgmt = resp_mgmt.data.decode("utf-8")
        self.assertIn("Management / Executive", html_mgmt)
        self.assertIn("Total Addressable Market", html_mgmt)
        self.assertIn("Komposisi Pasar Indonesia", html_mgmt)

    # =========================================================================
    # 8. Full End-to-End Pipeline Integration Test
    # =========================================================================
    def test_08_end_to_end_indonesia_pipeline(self):
        """Memverifikasi alur penuh end-to-end:
        Discovery -> Prospect -> Identity Resolution -> Master Organization
        -> Social Enrichment -> Event Signal -> AI Product Fit -> Marketing Target -> Campaign
        """
        # Step 1 & 2: Ingest candidate via unified pipeline
        test_candidate = {
            "name": "Klub Sepak Bola & Futsal Siliwangi",
            "organization_type": "community",
            "organization_subtype": "futsal_club",
            "sport": "futsal",
            "city": "Bandung",
            "province": "Jawa Barat",
            "phone": "081234567890",
            "email": "siliwangi.fc@example.com",
            "website": "https://www.instagram.com/siliwangifc_official/",
            "source_type": "social_discovery",
            "source_platform": "instagram",
            "source_url": "https://www.instagram.com/siliwangifc_official/",
            "description": "Klub sepak bola dan futsal kejuaraan regional. Butuh custom teamwear apparel.",
        }
        org_created, is_new, note = DiscoveryPipelineService.ingest_candidate_to_master(test_candidate)
        org_id = org_created.id
        self.assertIsNotNone(org_id)

        # Step 3: Verifikasi Master Organization (SSoT)
        org = db.session.get(Organization, org_id)
        self.assertIsNotNone(org)
        self.assertEqual(org.name, "Klub Sepak Bola & Futsal Siliwangi")
        self.assertEqual(org.sport, "futsal")

        # Step 4: Social Enrichment & Signal Extraction
        enrich_res = SocialConnectorService.enrich_organization_socials(org)
        self.assertGreater(enrich_res["signals_extracted"]["total_signals"], 0)
        self.assertTrue(enrich_res["signals_extracted"]["jersey_relevance"])

        # Step 5: Event Intelligence Signal
        event = Event(
            name="Turnamen Futsal Piala Walikota Bandung 2026",
            event_type="tournament",
            city="Bandung",
            province="Jawa Barat",
            relevance_score=95,
        )
        db.session.add(event)
        db.session.commit()

        participant = EventParticipant(
            event_id=event.id,
            organization_id=org.id,
            role="participant",
            notes="Peserta tim divisi utama",
        )
        db.session.add(participant)
        db.session.commit()

        # Step 6: AI Product Fit Evaluation
        fit_res = ProductFitService.evaluate_organization(org, target_product="Jersey / Custom Teamwear")
        self.assertGreaterEqual(fit_res["product_fit_score"], 65)
        self.assertIn(fit_res["product_fit_label"], ["High Fit", "High", "Medium Fit", "Medium"])
        self.assertIn("futsal", fit_res["reasoning"].lower())

        # Step 7: Marketing Target Explorer Discovery
        results, total_count, total_pages = MarketingIntelligenceService.search_marketing_targets(
            sport="futsal",
            city="Bandung",
            per_page=10
        )
        matched_target_ids = [item["id"] for item in results]
        self.assertIn(org.id, matched_target_ids, "Organisasi harus ditemukan di Marketing Explorer")

        # Step 8 & 9: Campaign Target Assignment & Tracking
        campaign = Campaign(
            name="Bandung Futsal Tournament Campaign",
            product="Jersey / Custom Teamwear",
            target_segment="Futsal Clubs",
            status="active",
        )
        db.session.add(campaign)
        db.session.commit()

        c_target = CampaignTarget(
            campaign_id=campaign.id,
            organization_id=org.id,
            product_fit_snapshot=org.product_fit,
            opportunity_score_snapshot=org.opportunity_score,
            status="selected",
            notes="Target utama hasil intelligence turnamen",
        )
        db.session.add(c_target)
        db.session.commit()

        # Final Verification: Pipeline complete, audit trail intact
        saved_target = CampaignTarget.query.filter_by(campaign_id=campaign.id, organization_id=org.id).first()
        self.assertIsNotNone(saved_target)
        self.assertEqual(saved_target.organization.name, "Klub Sepak Bola & Futsal Siliwangi")
        self.assertIn("Jersey", saved_target.product_fit_snapshot)


if __name__ == "__main__":
    unittest.main()
