import unittest
from datetime import date
from app import create_app
from app.config import TestConfig
from app.extensions import db
from app.models import User, ProcurementSupplier, QuotationRequest


class TestRFQEdit(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app.config["TESTING"] = True
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Buat user procurement & supplier
        self.proc_user = User.query.filter_by(email="proc_test@example.com").first()
        if not self.proc_user:
            self.proc_user = User(name="Procurement User", email="proc_test@example.com", role="procurement", is_active_flag=True)
            self.proc_user.set_password("Secret123!")
            db.session.add(self.proc_user)

        self.supplier = ProcurementSupplier.query.filter_by(company_name="PT Supplier RFQ Test").first()
        if not self.supplier:
            self.supplier = ProcurementSupplier(
                company_name="PT Supplier RFQ Test",
                product="raw material",
                contact_email="supplier@example.com",
                region="Bandung",
                source_url="https://supplier-test.com"
            )
            db.session.add(self.supplier)
        db.session.commit()

        self.sup_user = User.query.filter_by(email="sup_test@example.com").first()
        if not self.sup_user:
            self.sup_user = User(name="Mitra Supplier Test", email="sup_test@example.com", role="supplier", is_active_flag=True)
            self.sup_user.set_password("Secret123!")
            db.session.add(self.sup_user)
            db.session.commit()
        self.supplier.created_by = self.sup_user.id
        db.session.commit()

        # Buat QuotationRequest (RFQ)
        self.rfq = QuotationRequest.query.filter_by(rfq_code="RFQ-TEST-0001").first()
        if not self.rfq:
            self.rfq = QuotationRequest(
                rfq_code="RFQ-TEST-0001",
                title="Pengadaan Kain Cotton 100 Roll",
                category="raw material",
                procurement_user_id=self.proc_user.id,
                supplier_id=self.supplier.id,
                target_quantity=100,
                unit="roll",
                target_budget_unit=500000.0,
                specifications="Gramasi 190-200 gsm",
                notes="Pengiriman ke gudang pusat",
                status="requested"
            )
            db.session.add(self.rfq)
            db.session.commit()

    def tearDown(self):
        db.session.rollback()
        db.session.remove()
        self.app_context.pop()

    def login_proc(self):
        self.client.get("/logout", follow_redirects=True)
        return self.client.post("/login", data={
            "email": "proc_test@example.com",
            "password": "Secret123!"
        }, follow_redirects=True)

    def login_sup(self):
        self.client.get("/logout", follow_redirects=True)
        return self.client.post("/login", data={
            "email": "sup_test@example.com",
            "password": "Secret123!"
        }, follow_redirects=True)

    def test_edit_rfq_success(self):
        self.login_proc()
        response = self.client.post(f"/procurement/rfq/{self.rfq.id}/edit", data={
            "title": "Pengadaan Kain Cotton Combed 30s Revisi",
            "category": "raw material",
            "target_quantity": 250,
            "unit": "roll",
            "target_budget_unit": "Rp 550.000",
            "target_delivery_date": "2026-11-15",
            "specifications": "Warna navy, toleransi lebar kain 2 cm",
            "notes": "Prioritas tinggi"
        }, follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        updated = QuotationRequest.query.get(self.rfq.id)
        self.assertEqual(updated.title, "Pengadaan Kain Cotton Combed 30s Revisi")
        self.assertEqual(updated.target_quantity, 250)
        self.assertEqual(updated.target_budget_unit, 550000.0)
        self.assertEqual(updated.target_delivery_date, date(2026, 11, 15))
        self.assertEqual(updated.specifications, "Warna navy, toleransi lebar kain 2 cm")
        self.assertEqual(updated.notes, "Prioritas tinggi")

    def test_rfq_detail_template_modal_structure(self):
        self.login_proc()
        response = self.client.get(f"/procurement/rfq/{self.rfq.id}")
        self.assertEqual(response.status_code, 200)
        html = response.data.decode("utf-8")

        # Pastikan tombol edit ada
        self.assertIn('data-bs-target="#modalEditRFQ"', html)
        self.assertIn('Edit Permintaan', html)

        # Pastikan modal Edit RFQ ada
        self.assertIn('id="modalEditRFQ"', html)
        self.assertIn('id="modalCancelRFQ"', html)

        # Pastikan modalEditRFQ TIDAK berada di dalam modalCancelRFQ
        cancel_modal_start = html.find('id="modalCancelRFQ"')
        cancel_modal_end = html.find('id="modalEditRFQ"')
        # Di antara pembukaan modalCancelRFQ dan modalEditRFQ harus ada penutup modal (</div>) dan penutup form
        between_modals = html[cancel_modal_start:cancel_modal_end]
        self.assertIn('Ya, Batalkan Permintaan', between_modals)
        self.assertIn('</form>', between_modals)

    def test_rfq_list_template_modal_structure(self):
        self.login_proc()
        response = self.client.get("/procurement/rfq")
        self.assertEqual(response.status_code, 200)
        html = response.data.decode("utf-8")

        # Pastikan tombol edit ada di list
        self.assertIn(f'data-bs-target="#modalEditRFQ{self.rfq.id}"', html)

        # Pastikan modal Edit RFQ ada
        self.assertIn(f'id="modalEditRFQ{self.rfq.id}"', html)

        # Pastikan modal TIDAK berada di dalam tbody
        tbody_start = html.find('<tbody')
        tbody_end = html.find('</tbody>')
        tbody_content = html[tbody_start:tbody_end]
        self.assertNotIn(f'id="modalEditRFQ{self.rfq.id}"', tbody_content)

    def test_supplier_notification_on_procurement_edit(self):
        # 1. Supplier submits initial quotation
        self.rfq.status = "submitted"
        self.rfq.quotation_price_unit = 500000.0
        self.rfq.quotation_total_price = 50000000.0
        self.rfq.supplier_user_id = self.sup_user.id
        self.rfq.revision_required = False
        db.session.commit()

        # 2. Procurement edits RFQ and provides revision note
        self.login_proc()
        res = self.client.post(f"/procurement/rfq/{self.rfq.id}/edit", data={
            "title": "Pengadaan Kain Cotton 200 Roll (Tambah Kuota)",
            "category": "raw material",
            "target_quantity": 200,
            "unit": "roll",
            "target_budget_unit": "480000",
            "revision_note": "Kuantitas bertambah menjadi 200 roll, mohon penawaran harga terbaik."
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        # Cek database
        rfq_refreshed = db.session.get(QuotationRequest, self.rfq.id)
        self.assertTrue(rfq_refreshed.revision_required)
        self.assertIn("Kuantitas bertambah", rfq_refreshed.revision_note)

        # 3. Supplier views detail page and sees notification banner & note
        self.login_sup()
        res_sup_detail = self.client.get(f"/supplier/rfq/{self.rfq.id}")
        self.assertEqual(res_sup_detail.status_code, 200)
        html_detail = res_sup_detail.data.decode("utf-8")
        self.assertIn("Perlu Revisi Penawaran", html_detail)
        self.assertIn("Kuantitas bertambah menjadi 200 roll", html_detail)
        self.assertIn("Revisi Sekarang", html_detail)

        # 4. Supplier views list page and sees warning badge
        res_sup_list = self.client.get("/supplier/rfq")
        self.assertEqual(res_sup_list.status_code, 200)
        html_list = res_sup_list.data.decode("utf-8")
        self.assertIn("Perlu Revisi Penawaran", html_list)

        # 5. Supplier submits revised quote, revision_required resets to False
        res_submit_rev = self.client.post(f"/supplier/rfq/{self.rfq.id}/submit", data={
            "quotation_price_unit": 475000.0,
            "quotation_total_price": 95000000.0,
            "quotation_lead_time_days": 10,
            "quotation_notes": "Harga khusus revisi volume 200 roll"
        }, follow_redirects=True)
        self.assertEqual(res_submit_rev.status_code, 200)

        rfq_final = db.session.get(QuotationRequest, self.rfq.id)
        self.assertFalse(rfq_final.revision_required)
        self.assertEqual(rfq_final.quotation_price_unit, 475000.0)


if __name__ == "__main__":
    unittest.main()
