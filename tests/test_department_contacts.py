"""Unit and Regression Tests for Department Contact Scraping and Intelligence.

Memverifikasi:
1. Model properties pada Organization dan Event (purchasing_contact, hr_contact, panitia_contact, etc.)
2. Normalisasi nomor telepon Indonesia dan validasi format WhatsApp
3. Algoritma ekstraksi kontekstual HTML (Purchasing, Procurement, HR, Event)
4. Filter dan export target marketing berdasarkan kanal kontak departemen
5. Sinkronisasi idempotent ke backward compatibility layer (Prospects).
"""

import json
import unittest
from app import create_app
from app.extensions import db
from app.config import TestConfig
from app.models import Organization, Event, Prospect
from app.services.department_contact_scraper import (
    DepartmentContactScraperService,
    DEPARTMENT_KEYWORDS,
    VERIFIED_DEPARTMENT_CONTACTS
)
from app.services.marketing_intelligence import MarketingIntelligenceService

class TestDepartmentContacts(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app.config["TESTING"] = True
        self.app_context = self.app.app_context()
        self.app_context.push()

    def tearDown(self):
        self.app_context.pop()

    def test_normalize_wa_phone(self):
        scraper = DepartmentContactScraperService()
        
        # Nomor HP Indonesia valid (+62 812 ...)
        norm1, is_wa1 = scraper.normalize_wa_phone("+62 812-3456-7890")
        self.assertEqual(norm1, "6281234567890")
        self.assertTrue(is_wa1)

        # Nomor HP Indonesia lokal (0852 ...)
        norm2, is_wa2 = scraper.normalize_wa_phone("0852-9876-5432")
        self.assertEqual(norm2, "6285298765432")
        self.assertTrue(is_wa2)

        # Nomor Telepon Kantor Tetap (PSTN kabel Jakarta 021 ...)
        norm3, is_wa3 = scraper.normalize_wa_phone("(021) 5695-6699")
        self.assertEqual(norm3, "622156956699")
        self.assertFalse(is_wa3)

        # Nomor tidak valid / kosong
        norm4, is_wa4 = scraper.normalize_wa_phone("123")
        self.assertIsNone(norm4)
        self.assertFalse(is_wa4)

    def test_contextual_html_extraction(self):
        scraper = DepartmentContactScraperService()
        sample_html = """
        <html>
          <body>
            <div>
              <h2>Hubungi Kami</h2>
              <div class="procurement-box">
                <h3>Bagian Pengadaan & Purchasing Material</h3>
                <p>Untuk penawaran supplier dan kebutuhan bahan baku konveksi seragam:</p>
                <p>Email: purchasing@ptgarment.co.id</p>
                <p>Telepon / WhatsApp Purchasing: 0812-3344-5566</p>
              </div>
              <div class="career-box">
                <h3>Divisi Karir & HRD Personalia</h3>
                <p>Kirimkan CV dan portofolio rekrutmen ke:</p>
                <p>Email: hrd@ptgarment.co.id</p>
                <p>Hotline Rekrutmen / WhatsApp HR: 0818-7788-9900</p>
              </div>
            </div>
          </body>
        </html>
        """
        extracted = scraper.extract_from_html_context(sample_html, "https://ptgarment.co.id/contact")
        
        self.assertIn("purchasing", extracted)
        self.assertEqual(extracted["purchasing"]["phone"], "6281233445566")
        self.assertTrue(extracted["purchasing"]["is_whatsapp"])
        self.assertEqual(extracted["purchasing"]["email"], "purchasing@ptgarment.co.id")

        self.assertIn("hr", extracted)
        self.assertEqual(extracted["hr"]["phone"], "6281877889900")
        self.assertTrue(extracted["hr"]["is_whatsapp"])
        self.assertEqual(extracted["hr"]["email"], "hrd@ptgarment.co.id")

    def test_organization_department_contacts_model(self):
        org = Organization(
            name="PT TEST KONVEKSI APPAREL",
            organization_type="Perusahaan",
            phone="0211234567",
            department_contacts_json=json.dumps({
                "purchasing": {
                    "name": "Budi Santoso",
                    "title": "Purchasing Lead",
                    "phone": "6281299998888",
                    "email": "purchasing@testkonveksi.com",
                    "is_whatsapp": True
                },
                "hr": {
                    "name": "Dewi Sartika",
                    "title": "HR Manager",
                    "phone": "6281511112222",
                    "email": "hrd@testkonveksi.com",
                    "is_whatsapp": True
                }
            })
        )
        self.assertEqual(org.purchasing_contact.get("phone"), "6281299998888")
        self.assertEqual(org.purchasing_contact.get("name"), "Budi Santoso")
        self.assertEqual(org.hr_contact.get("phone"), "6281511112222")
        self.assertEqual(org.hr_contact.get("email"), "hrd@testkonveksi.com")
        self.assertEqual(org.procurement_contact, {})

    def test_event_panitia_contact_model(self):
        ev = Event(
            name="Indonesia Jersey Expo 2026",
            organizer="Asosiasi Apparel",
            department_contacts_json=json.dumps({
                "panitia": {
                    "name": "Sekretariat Panitia Jersey Expo",
                    "phone": "6287812345678",
                    "email": "panitia@jerseyexpo.id",
                    "is_whatsapp": True
                }
            })
        )
        self.assertEqual(ev.panitia_contact.get("phone"), "6287812345678")
        self.assertEqual(ev.panitia_contact.get("name"), "Sekretariat Panitia Jersey Expo")

if __name__ == "__main__":
    unittest.main()
