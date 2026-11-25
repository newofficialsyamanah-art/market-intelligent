"""Product-category sales trend loaded from the supplied 2026 workbook."""

import io
from pathlib import Path
from typing import Any, Dict, List

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill


_SOURCE_FILENAME = "omset_by_product_category_2026.xlsx"
_CATEGORY_COLORS = (
    "#2563eb", "#dc2626", "#059669", "#ea580c", "#7c3aed",
    "#0891b2", "#65a30d", "#d97706", "#db2777", "#475569",
    "#0f766e", "#9333ea", "#c026d3",
)


def get_product_sales_trend_2026() -> Dict[str, Any]:
    """Read monthly category revenue and validate it against workbook row totals."""
    workbook_path = Path(__file__).resolve().parents[1] / "data" / _SOURCE_FILENAME
    workbook = load_workbook(workbook_path, data_only=True, read_only=True)
    try:
        rows = workbook.active.iter_rows(values_only=True)
        headers = next(rows, None)
        if not headers or headers[0] != "Product Category" or "Total" not in headers:
            raise ValueError(f"Unexpected columns in product sales workbook: {workbook_path}")

        total_index = headers.index("Total")
        month_indexes = [
            (index, str(header).replace(" 2026", ""))
            for index, header in enumerate(headers)
            if index != 0 and index != total_index and str(header).endswith(" 2026")
        ]
        if len(month_indexes) != 12:
            raise ValueError(f"Expected 12 monthly columns in product sales workbook: {workbook_path}")

        categories: List[Dict[str, Any]] = []
        monthly_totals = [0.0] * len(month_indexes)
        for row in rows:
            if not row or not row[0]:
                continue
            monthly_values = [float(row[index] or 0) for index, _ in month_indexes]
            row_total = float(row[total_index] or 0)
            calculated_total = sum(monthly_values)
            if abs(calculated_total - row_total) > 0.01:
                raise ValueError(
                    f"Monthly values do not match the stated total for product category {row[0]!r}"
                )
            for index, value in enumerate(monthly_values):
                monthly_totals[index] += value

            categories.append({
                "name": str(row[0]).strip(),
                "monthly_values": monthly_values,
                "total": row_total,
            })

        datasets = [
            {
                "label": category["name"],
                "data": [round(value / 1_000_000, 2) for value in category["monthly_values"]],
                "backgroundColor": _CATEGORY_COLORS[index % len(_CATEGORY_COLORS)],
                "borderWidth": 0,
            }
            for index, category in enumerate(categories)
        ]
        datasets.append({
            "type": "line",
            "label": "Total omzet",
            "data": [round(value / 1_000_000, 2) for value in monthly_totals],
            "yAxisID": "yTotal",
            "borderColor": "#111827",
            "backgroundColor": "#111827",
            "borderWidth": 2,
            "pointRadius": 3,
            "fill": False,
            "tension": 0.2,
        })

        return {
            "source_filename": "OMSET BY PRODUCT CATEGORY 2026 - INSIGHTS DASHBOARD.xlsx",
            "months": [month for _, month in month_indexes],
            "categories": categories,
            "monthly_totals": monthly_totals,
            "grand_total": sum(monthly_totals),
            "datasets": datasets,
            "selected_category": "",
        }
    finally:
        workbook.close()


def filter_product_sales_trend_2026(
    sales: Dict[str, Any],
    selected_category: str,
) -> Dict[str, Any]:
    """Return a recalculated view of the sales data for one exact product category."""
    if not selected_category:
        return sales

    categories = [
        category for category in sales["categories"]
        if category["name"] == selected_category
    ]
    if len(categories) != 1:
        raise ValueError(f"Unknown product category: {selected_category}")

    category = categories[0]
    monthly_totals = list(category["monthly_values"])
    monthly_total_dataset = {
        "type": "line",
        "label": f"Total omzet - {category['name']}",
        "data": [round(value / 1_000_000, 2) for value in monthly_totals],
        "yAxisID": "yTotal",
        "borderColor": "#111827",
        "backgroundColor": "#111827",
        "borderWidth": 2,
        "pointRadius": 3,
        "fill": False,
        "tension": 0.2,
    }

    return {
        **sales,
        "categories": categories,
        "monthly_totals": monthly_totals,
        "grand_total": sum(monthly_totals),
        "datasets": [
            dataset for dataset in sales["datasets"]
            if dataset.get("label") == selected_category
        ] + [monthly_total_dataset],
        "selected_category": selected_category,
    }


def create_product_sales_workbook(sales: Dict[str, Any]) -> io.BytesIO:
    """Create an .xlsx export of the selected product or all product categories."""
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Omzet 2026"
    sheet.append(["Tren Omzet Syamanah 2026 per Kategori Produk"])
    sheet.append(["Sumber", _safe_excel_text(sales["source_filename"])])
    sheet.append([
        "Filter produk",
        _safe_excel_text(sales.get("selected_category") or "Semua kategori"),
    ])
    sheet.append([])
    sheet.append(["Kategori Produk"] + [f"{month} (Rp)" for month in sales["months"]] + ["Total (Rp)"])

    header_fill = PatternFill("solid", fgColor="17365D")
    for cell in sheet[5]:
        cell.fill = header_fill
        cell.font = Font(bold=True, color="FFFFFF")
        cell.alignment = Alignment(horizontal="center", wrap_text=True)

    for category in sales["categories"]:
        sheet.append(
            [_safe_excel_text(category["name"])]
            + list(category["monthly_values"])
            + [category["total"]]
        )

    data_end_row = sheet.max_row
    totals_row = sheet.max_row + 1
    sheet.append(["Total Bulanan"] + list(sales["monthly_totals"]) + [sales["grand_total"]])
    for cell in sheet[totals_row]:
        cell.font = Font(bold=True)
        cell.fill = PatternFill("solid", fgColor="E2F0D9")

    for row in sheet.iter_rows(min_row=6, min_col=2, max_col=len(sales["months"]) + 2):
        for cell in row:
            cell.number_format = '"Rp" #,##0.00'
    sheet.freeze_panes = "B6"
    sheet.auto_filter.ref = (
        f"A5:{sheet.cell(row=max(data_end_row, 5), column=len(sales['months']) + 2).coordinate}"
    )
    sheet.column_dimensions["A"].width = 28
    for column in range(2, len(sales["months"]) + 3):
        sheet.column_dimensions[sheet.cell(row=5, column=column).column_letter].width = 18

    output = io.BytesIO()
    workbook.save(output)
    output.seek(0)
    return output


def _safe_excel_text(value: str) -> str:
    if value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + value
    return value
