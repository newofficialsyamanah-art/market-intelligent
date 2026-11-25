from io import BytesIO
import unittest

from openpyxl import load_workbook

from app import create_app
from app.blueprints.prospect.routes import _build_2027_product_trend
from app.config import TestConfig
from app.extensions import db
from app.models import User
from app.services.product_sales_trend import (
    create_product_sales_workbook,
    filter_product_sales_trend_2026,
    get_product_sales_trend_2026,
)


class TestProspect2027Trends(unittest.TestCase):
    def test_loads_product_sales_workbook_and_reconciles_totals(self):
        sales = get_product_sales_trend_2026()

        self.assertEqual(len(sales["months"]), 12)
        self.assertEqual(len(sales["categories"]), 13)
        self.assertIn("FOB Jersey", {category["name"] for category in sales["categories"]})
        self.assertAlmostEqual(
            sum(category["total"] for category in sales["categories"]),
            sales["grand_total"],
            places=2,
        )
        self.assertAlmostEqual(sum(sales["monthly_totals"]), sales["grand_total"], places=2)

    def test_filters_and_exports_selected_product_sales(self):
        sales = get_product_sales_trend_2026()
        selected_category = "FOB Jersey"
        filtered = filter_product_sales_trend_2026(sales, selected_category)

        self.assertEqual([item["name"] for item in filtered["categories"]], [selected_category])
        self.assertEqual(filtered["selected_category"], selected_category)
        self.assertEqual(filtered["monthly_totals"], filtered["categories"][0]["monthly_values"])
        self.assertAlmostEqual(
            filtered["grand_total"],
            filtered["categories"][0]["total"],
            places=2,
        )
        with self.assertRaises(ValueError):
            filter_product_sales_trend_2026(sales, "Produk tidak tersedia")

        workbook = load_workbook(
            BytesIO(create_product_sales_workbook(filtered).getvalue()),
            data_only=True,
        )
        sheet = workbook["Omzet 2026"]
        self.assertEqual(sheet["A6"].value, selected_category)
        self.assertEqual(sheet["A7"].value, "Total Bulanan")
        workbook.close()

    def test_builds_product_counts_by_2027_quarter_without_splitting_opportunities(self):
        trend = _build_2027_product_trend([
            {"products": ["Jersey", "Kaos"], "lead_time": "Q1 2027"},
            {"products": ["Jersey"], "lead_time": "Jan 2027"},
            {"products": ["Jaket", "Seragam"], "lead_time": "Q1-Q2 2027"},
            {"products": "Seragam", "lead_time": "2027"},
            {"products": ["Jersey"], "lead_time": "Q3 2026"},
            {"products": ["Jersey"], "lead_time": "Sep 2027"},
        ])

        rows = {row["name"]: row for row in trend["rows"]}
        self.assertEqual(rows["Jersey"]["quarter_counts"]["Q1"], 2)
        self.assertEqual(rows["Jersey"]["quarter_counts"]["Q3"], 1)
        self.assertEqual(rows["Jersey"]["quarter_counts"]["Belum terjadwal"], 0)
        self.assertEqual(rows["Jaket"]["quarter_counts"]["Belum terjadwal"], 1)
        self.assertEqual(rows["Seragam"]["quarter_counts"]["Belum terjadwal"], 2)
        self.assertEqual(rows["Kaos"]["quarter_counts"]["Q1"], 1)
        self.assertEqual(trend["prospect_count"], 5)
        self.assertEqual(trend["unscheduled_count"], 2)

    def test_market_share_and_pdf_pages_render_product_trend(self):
        app = create_app(TestConfig)
        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False
        client = app.test_client()
        app_context = app.app_context()
        app_context.push()
        db.create_all()

        user = User(name="Trend Test Marketing", email="trend_test_marketing@example.com", role="marketing")
        user.set_password("Secret123!")
        db.session.add(user)
        db.session.commit()

        try:
            login = client.post(
                "/login",
                data={"email": user.email, "password": "Secret123!"},
            )
            self.assertEqual(login.status_code, 302)

            page = client.get("/prospects/market-share-2027")
            self.assertEqual(page.status_code, 200)
            self.assertIn(b"Tren Omzet Syamanah 2026 per Kategori Produk", page.data)
            self.assertIn(b"FOB Jersey", page.data)
            self.assertIn(b"Filter per produk", page.data)
            self.assertIn(b"Export Excel", page.data)
            self.assertIn(b"Tren Jumlah Prospek 2027 per Produk", page.data)
            self.assertIn(b"prospectProductTrend2027", page.data)
            self.assertIn(b"Belum terjadwal", page.data)

            filtered_page = client.get(
                "/prospects/market-share-2027?sales_category=FOB+Jersey"
            )
            self.assertEqual(filtered_page.status_code, 200)
            self.assertIn(b"FOB Jersey", filtered_page.data)

            excel_export = client.get(
                "/prospects/market-share-2027/export-sales.xlsx?sales_category=FOB+Jersey"
            )
            self.assertEqual(excel_export.status_code, 200)
            self.assertEqual(
                excel_export.mimetype,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            exported_workbook = load_workbook(BytesIO(excel_export.data), data_only=True)
            self.assertEqual(exported_workbook["Omzet 2026"]["A6"].value, "FOB Jersey")
            exported_workbook.close()

            pdf_page = client.get("/prospects/market-share-2027/pdf")
            self.assertEqual(pdf_page.status_code, 200)
            self.assertIn(b"FOB Jersey", pdf_page.data)
        finally:
            db.session.remove()
            app_context.pop()


if __name__ == "__main__":
    unittest.main()
