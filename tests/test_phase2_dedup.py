import os
import sys
import unittest
import time
import json
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import Organization, DuplicateCandidate, Prospect
from app.services.dedup_engine import (
    normalize_company_name,
    extract_domain,
    normalize_phone,
    normalize_location,
    calculate_fuzzy_ratio,
    IdentityResolutionEngine,
    safe_merge_organization,
    MatchResult
)

from app.config import TestConfig


class TestPhase2Deduplication(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app(TestConfig)
        cls.app.config['TESTING'] = True
        cls.app.config['WTF_CSRF_ENABLED'] = False

    def test_1_identity_normalization(self):
        """Uji 1: Verifikasi fungsi-fungsi normalisasi identitas."""
        # 1. Company Name Normalization
        self.assertEqual(normalize_company_name("PT. INDOFOOD SUKSES MAKMUR TBK"), "indofood sukses makmur")
        self.assertEqual(normalize_company_name("PAPANDAYAN COCOA INDUSTRIES, PT"), "papandayan cocoa industries")
        self.assertEqual(normalize_company_name("CV. ABADI TEXTILE (BANDUNG)"), "abadi textile bandung")
        self.assertEqual(normalize_company_name("UD. MEKAR JAYA ABADI"), "mekar jaya abadi")
        self.assertEqual(normalize_company_name("YAYASAN PENDIDIKAN BINA MULIA"), "pendidikan bina mulia")
        self.assertEqual(normalize_company_name("KOPERASI PEGAWAI TELKOM"), "pegawai telkom")
        self.assertEqual(normalize_company_name("PT GLOBAL LOGISTICS CORP."), "global logistics")

        # 2. Domain Extraction
        self.assertEqual(extract_domain("https://www.panbrothers.co.id/contact?q=1"), "panbrothers.co.id")
        self.assertEqual(extract_domain("http://indofood.com/about"), "indofood.com")
        self.assertEqual(extract_domain("sales@sritex.co.id"), "sritex.co.id")
        # Generic emails should return None
        self.assertIsNone(extract_domain("marketing@gmail.com"))
        self.assertIsNone(extract_domain("owner@yahoo.co.id"))
        self.assertIsNone(extract_domain("-"))

        # 3. Phone Normalization
        self.assertEqual(normalize_phone("+62 21-555 1234"), "0215551234")
        self.assertEqual(normalize_phone("628123456789"), "08123456789")
        self.assertEqual(normalize_phone("022-7654321"), "0227654321")
        self.assertIsNone(normalize_phone("0000"))
        self.assertIsNone(normalize_phone("-"))

        # 4. Location Normalization
        c1, p1 = normalize_location("KABUPATEN BANDUNG", "PROVINSI JAWA BARAT")
        self.assertEqual(c1, "bandung")
        self.assertEqual(p1, "jawa barat")
        c2, p2 = normalize_location("KOTA SURAKARTA", "JAWA TENGAH")
        self.assertEqual(c2, "surakarta")
        self.assertEqual(p2, "jawa tengah")

        # 5. Fuzzy Ratio
        ratio_exact = calculate_fuzzy_ratio("pan brothers garmen", "pan brothers garmen")
        self.assertEqual(ratio_exact, 1.0)
        ratio_similar = calculate_fuzzy_ratio("pan brothers garmen", "pan brothers garment")
        self.assertGreater(ratio_similar, 0.90)
        ratio_diff = calculate_fuzzy_ratio("pan brothers", "semen padang")
        self.assertLess(ratio_diff, 0.40)
        print("  [PASS] All Identity Normalization functions verified.")

    def test_2_matching_signals_tier1_to_4(self):
        """Uji 2: Verifikasi Matching Signals Tier 1 - 4."""
        with self.app.app_context():
            # Setup mock master orgs in engine
            org_master = Organization(
                id=9901,
                name="PT Pan Brothers Tbk",
                normalized_name="pan brothers",
                domain="panbrothers.co.id",
                city="Tangerang",
                province="Banten",
                phone="0215551234"
            )
            org_master2 = Organization(
                id=9902,
                name="PT Sinar Antjol",
                normalized_name="sinar antjol",
                domain="sinarantjol.com",
                city="Jakarta Utara",
                province="DKI Jakarta",
                phone="0216669999"
            )
            engine = IdentityResolutionEngine([org_master, org_master2])

            # Tier 1: Domain Match
            res_t1 = engine.evaluate_candidate(
                name="Pan Brothers Apparel Division",
                website="https://www.panbrothers.co.id/career"
            )
            self.assertEqual(res_t1.decision, "auto_match")
            self.assertEqual(res_t1.tier, "tier1_domain")
            self.assertEqual(res_t1.signal_strength, "STRONGEST")
            self.assertEqual(res_t1.matched_org.id, 9901)

            # Tier 2: Normalized Legal Name + Wilayah Match
            res_t2 = engine.evaluate_candidate(
                name="CV. Pan Brothers",
                city="KOTA TANGERANG",
                province="BANTEN"
            )
            self.assertEqual(res_t2.decision, "auto_match")
            self.assertEqual(res_t2.tier, "tier2_name_location")
            self.assertEqual(res_t2.signal_strength, "STRONG")
            self.assertEqual(res_t2.matched_org.id, 9901)

            # Tier 3: Corporate Contact Match (Phone)
            res_t3 = engine.evaluate_candidate(
                name="Pan Brothers Distribution",
                phone="+62 21-555 1234"
            )
            self.assertEqual(res_t3.decision, "auto_match")
            self.assertEqual(res_t3.tier, "tier3_contact")
            self.assertEqual(res_t3.signal_strength, "STRONG")

            # Tier 4: Fuzzy Match (Candidate Review when confidence is moderate)
            res_t4 = engine.evaluate_candidate(
                name="PT Sinar Antjol Perkasa",  # partial fuzzy similarity
                city="Surabaya",  # Different location
                province="Jawa Timur"
            )
            # Should be a candidate for review, NOT auto-merged!
            self.assertIn(res_t4.decision, ["review_candidate", "unmatched"])
            if res_t4.decision == "review_candidate":
                self.assertEqual(res_t4.signal_strength, "CANDIDATE")
                self.assertEqual(res_t4.matched_org.id, 9902)

            # Unmatched
            res_unmatched = engine.evaluate_candidate(
                name="PT Kalbe Farma Tbk",
                website="https://www.kalbe.co.id"
            )
            self.assertEqual(res_unmatched.decision, "unmatched")
            self.assertIsNone(res_unmatched.matched_org)
            print("  [PASS] Matching signals Tier 1-4 and Decision Matrix verified.")

    def test_3_safe_merge_strategy_and_provenance(self):
        """Uji 3: Safe Merge Non-Destructive, Field Preservation, dan Audit Provenance."""
        with self.app.app_context():
            master_org = Organization(
                name="PT Kahatex",
                normalized_name="kahatex",
                domain="kahatex.com",
                industry="Tekstil",
                city="Sumedang",
                province="Jawa Barat",
                phone="0227798888",
                email=None,  # Empty in master
                website="https://kahatex.com",
                opportunity_score=60,
                priority_tier="Tier C"
            )
            
            incoming_data = {
                "name": "PT. KAHATEX (CIMAHI PLANT)",
                "source_type": "bps",
                "source_id": 101,
                "email": "contact@kahatex.com",  # Should enrich master
                "phone": None,  # Should NOT overwrite master phone
                "opportunity_score": 85,  # Higher score should update master
                "priority_tier": "Tier A",  # Higher priority should update master
                "product_fit": "Seragam Pabrik & Wearpack"
            }
            
            match_res = MatchResult(
                decision="auto_match",
                tier="tier1_domain",
                confidence=0.98,
                signal_strength="STRONGEST",
                matched_org=master_org
            )
            
            # First merge
            modified, msg = safe_merge_organization(master_org, incoming_data, match_res)
            self.assertTrue(modified)
            self.assertEqual(master_org.phone, "0227798888", "Master phone must NOT be overwritten by None")
            self.assertEqual(master_org.email, "contact@kahatex.com", "Master email must be enriched")
            self.assertEqual(master_org.opportunity_score, 85, "Opportunity score must be updated to max")
            self.assertEqual(master_org.priority_tier, "Tier A", "Priority tier must be upgraded to Tier A")
            self.assertEqual(master_org.product_fit, "Seragam Pabrik & Wearpack")
            
            # Check provenance JSON
            self.assertIsNotNone(master_org.provenance_json)
            provenance = json.loads(master_org.provenance_json)
            self.assertEqual(len(provenance), 1)
            self.assertEqual(provenance[0]["source_id"], 101)
            self.assertEqual(provenance[0]["match_tier"], "tier1_domain")
            print("  [PASS] Safe non-destructive merge and provenance tracking verified.")

    def test_4_idempotency(self):
        """Uji 4: Idempotency - Menjalankan merge dua kali pada data yang sama tidak menimbulkan perubahan."""
        with self.app.app_context():
            master_org = Organization(
                name="PT Indorama Synthetics",
                normalized_name="indorama synthetics",
                domain="indorama.com",
                opportunity_score=70,
                priority_tier="Tier B"
            )
            incoming = {
                "name": "PT INDORAMA SYNTHETICS TBK",
                "source_type": "vendor_db",
                "source_id": 202,
                "email": "corp@indorama.com",
                "opportunity_score": 75,
                "priority_tier": "Tier B"
            }
            match_res = MatchResult(decision="auto_match", tier="tier1_domain", confidence=0.98, signal_strength="STRONGEST", matched_org=master_org)
            
            # Merge pertama -> harus modified
            mod1, msg1 = safe_merge_organization(master_org, incoming, match_res)
            self.assertTrue(mod1)
            prov_count_1 = len(json.loads(master_org.provenance_json))
            self.assertEqual(prov_count_1, 1)
            
            # Merge kedua dengan data identik -> HARUS FALSE (Idempotent!)
            mod2, msg2 = safe_merge_organization(master_org, incoming, match_res)
            self.assertFalse(mod2, "Merge kedua harus mengembalikan False (Idempotent)")
            prov_count_2 = len(json.loads(master_org.provenance_json))
            self.assertEqual(prov_count_2, 1, "Provenance log tidak boleh duplikat")
            print("  [PASS] Idempotency verified: duplicate runs produce 0 state changes.")

    def test_5_duplicate_candidate_persistence(self):
        """Uji 5: Penyimpanan entitas DuplicateCandidate untuk Review Manual."""
        with self.app.app_context():
            test_org = Organization(
                name="PT Sri Rejeki Isman Tbk",
                normalized_name="sri rejeki isman",
                domain="sritex.co.id",
                city="Sukoharjo",
                province="Jawa Tengah"
            )
            db.session.add(test_org)
            db.session.flush()

            # Buat candidate review
            cand = DuplicateCandidate(
                organization_id=test_org.id,
                candidate_name="PT SRI REJEKI MAKMUR",
                candidate_source="event_scraping",
                candidate_payload_json=json.dumps({"city": "Solo", "phone": "027112345"}),
                match_tier="tier4_fuzzy_candidate",
                confidence_score=0.88,
                status="pending"
            )
            db.session.add(cand)
            db.session.commit()

            # Query kembali
            saved = DuplicateCandidate.query.filter_by(organization_id=test_org.id).first()
            self.assertIsNotNone(saved)
            self.assertEqual(saved.match_tier, "tier4_fuzzy_candidate")
            self.assertEqual(saved.status, "pending")
            self.assertEqual(saved.organization.name, "PT Sri Rejeki Isman Tbk")

            # Cleanup
            db.session.delete(cand)
            db.session.delete(test_org)
            db.session.commit()
            print("  [PASS] DuplicateCandidate persistence for manual review verified.")

if __name__ == '__main__':
    unittest.main()
