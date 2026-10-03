import unittest
from app import create_app
from app.config import TestConfig
from app.extensions import db
from app.models import ProcurementSupplier
from app.services.procurement_service import (
    clean_company_name,
    is_relevant_fabric_supplier,
    search_suppliers,
)


class ProcurementTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

    def tearDown(self):
        db.session.rollback()
        db.session.remove()
        self.app_context.pop()

    def test_clean_company_name(self):
        tests = [
            ("PelitaTex | Jual Bahan Jaket Bandung Terlengkap & Terpercaya", "https://pelitatex.com/", "PelitaTex"),
            ("Toko Bahan Kaos | Karunia Textile Bandung | CVC Piqe Soft", "https://karuniatex.com/cvc-piqe-soft/", "Karunia Textile Bandung"),
            ("Jual Kain Oxford Roll Berkualitas Murah | Moiztex", "https://moiztex.com/oxford", "Moiztex"),
            ("KARYA MANDIRI TEXTILE - Supplier Bahan Kain Jersey Bandung", "https://karyamandiritextile.com/", "KARYA MANDIRI TEXTILE"),
            ("Beranda - CV. Diamond Textile Indonesia", "https://diamondtextileindonesia.com/", "CV. Diamond Textile Indonesia"),
        ]
        for raw_title, url, expected in tests:
            result = clean_company_name(raw_title, url)
            self.assertEqual(result, expected)

    def test_is_relevant_fabric_supplier(self):
        # Valid fabric page
        valid_title = "PelitaTex - Jual Bahan Kain Jaket Taslan Bandung"
        valid_text = "Kami menyediakan kain taslan, fleece, parasut, micro ns untuk kebutuhan produksi jaket konveksi."
        self.assertTrue(is_relevant_fabric_supplier(valid_title, valid_text, "jaket", "taslan"))

        # Irrelevant news article (e.g. NIK or car or phone)
        bad_title = "Warga Jakarta Perlu Tahu, Begini Cara Cek NIK Aktif Secara Online"
        bad_text = "Dukcapil DKI Jakarta mengimbau warga mengecek status nomor induk kependudukan di portal resmi kependudukan."
        self.assertFalse(is_relevant_fabric_supplier(bad_title, bad_text, "jersey", "dry fit"))

    def test_search_suppliers_seeds_verified(self):
        query, suppliers = search_suppliers("jersey", limit=3)
        self.assertTrue(len(suppliers) >= 3)
        names = [s.company_name for s in suppliers]
        self.assertIn("Knitto Textiles", names)
        self.assertIn("Karya Mandiri Textile", names)
        for s in suppliers:
            self.assertGreaterEqual(s.fit_score, 50)
            self.assertNotIn("uzone.id", s.source_url)
    def test_is_relevant_multi_category_suppliers(self):
        from app.services.procurement_service import is_relevant_supplier
        # Elektrikal
        self.assertTrue(is_relevant_supplier("PT Supreme Cable - Distributor Kabel Listrik", "Kabel tegangan rendah dan panel listrik industri SNI", "elektrikal", "kabel"))
        # Software
        self.assertTrue(is_relevant_supplier("Mekari - Software ERP & Cloud SaaS HRIS", "Solusi software payroll akuntansi dan sistem informasi perusahaan", "software", "erp"))
        # Pharmaceutical
        self.assertTrue(is_relevant_supplier("Kalbe Farma - Industri Farmasi & Obat", "Pabrik obat generik, alat kesehatan, dan distribusi PBF", "pharmaceutical", "obat"))
        # Hardware
        self.assertTrue(is_relevant_supplier("Kawan Lama - Distributor Perkakas Mesin", "Peralatan teknik industri, baut, valve, dan alat ukur presisi", "hardware", "perkakas"))
        # Irrelevant text should fail
        self.assertFalse(is_relevant_supplier("Resep Masakan Enak", "Cara memasak ayam goreng kremes renyah dan gurih", "software", "erp"))

    def test_all_8_categories_verified_suppliers(self):
        categories = ["raw material", "distributor", "elektrikal", "services", "pharmaceutical", "local", "hardware", "software"]
        for cat in categories:
            query, suppliers = search_suppliers(cat, limit=2)
            self.assertTrue(len(suppliers) >= 2, f"Failed for category {cat}")
            for s in suppliers:
                self.assertEqual(s.product, cat)
                self.assertGreaterEqual(s.fit_score, 45)
                self.assertTrue(s.company_name)


if __name__ == "__main__":
    unittest.main()
