"""Excel export for filtered Company Intelligence Explorer results."""

import io
from datetime import datetime
from typing import Any, Dict, Iterable, Optional

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter


_COLUMNS = (
    ("ID", "id"),
    ("Nama Organisasi", "name"),
    ("Nama Normalisasi", "normalized_name"),
    ("Jenis Organisasi", "organization_type"),
    ("Subjenis", "organization_subtype"),
    ("Industri", "industry"),
    ("Olahraga", "sport"),
    ("Product Fit", "product_fit"),
    ("Opportunity Score", "opportunity_score"),
    ("Priority Tier", "priority_tier"),
    ("Anggota Estimasi", "estimated_members"),
    ("Ukuran Karyawan", "employee_size"),
    ("Status Ukuran", "size_status"),
    ("Sumber Ukuran", "size_source"),
    ("Telepon", "phone"),
    ("Email", "email"),
    ("Website", "clean_website_url"),
    ("Domain", "domain"),
    ("Instagram", "instagram_url"),
    ("Facebook", "facebook_url"),
    ("LinkedIn", "linkedin_url"),
    ("TikTok", "tiktok_url"),
    ("Alamat", "address"),
    ("Kota", "city"),
    ("Provinsi", "province"),
    ("Tipe Sumber", "source_type"),
    ("ID Sumber", "source_id"),
    ("URL Sumber", "source_url"),
    ("Status Verifikasi", "verification_status"),
    ("Relevance Score", "relevance_score"),
    ("Deskripsi", "description"),
    ("Data Freshness", "data_freshness"),
    ("Terakhir Dilihat", "last_seen"),
    ("Dibuat Pada", "created_at"),
)


def create_company_intelligence_workbook(
    organizations: Iterable[Any],
    filters: Optional[Dict[str, Any]] = None,
) -> io.BytesIO:
    """Create an .xlsx workbook with the full filtered organization result set."""
    from openpyxl.styles import Border, Side

    organizations = list(organizations)
    filters = filters or {}
    wb = Workbook()
    guide = wb.active
    guide.title = "Petunjuk"
    guide.append(["Company Intelligence Explorer"])
    guide.append(["Diekspor pada", datetime.now()])
    guide.append(["Jumlah organisasi", len(organizations)])
    active_filters = [f"{key}={value}" for key, value in filters.items() if value not in ("", None, False)]
    guide.append(["Filter aktif", "; ".join(active_filters) if active_filters else "Semua data"])
    guide["A1"].font = Font(bold=True, size=14, color="FFFFFF")
    guide["A1"].fill = PatternFill("solid", fgColor="17365D")
    guide["A1"].alignment = Alignment(vertical="center")
    guide.column_dimensions["A"].width = 24
    guide.column_dimensions["B"].width = 100
    guide["B2"].number_format = "yyyy-mm-dd hh:mm"
    guide.freeze_panes = "A2"

    sheet = wb.create_sheet("Organisasi")
    headers = [label for label, _ in _COLUMNS]
    sheet.append(headers)
    header_fill = PatternFill("solid", fgColor="17365D")
    header_font = Font(bold=True, color="FFFFFF")
    thin_border = Border(
        left=Side(style="thin", color="D9E2F3"),
        right=Side(style="thin", color="D9E2F3"),
        top=Side(style="thin", color="D9E2F3"),
        bottom=Side(style="thin", color="D9E2F3"),
    )
    for cell in sheet[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = thin_border

    for organization in organizations:
        sheet.append([
            _safe_spreadsheet_value(getattr(organization, attribute, None))
            for _, attribute in _COLUMNS
        ])

    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    header_indexes = {label: index + 1 for index, (label, _) in enumerate(_COLUMNS)}
    for label in ("ID", "Opportunity Score", "Anggota Estimasi", "ID Sumber", "Relevance Score"):
        column = header_indexes[label]
        for row in range(2, sheet.max_row + 1):
            sheet.cell(row=row, column=column).number_format = "#,##0"
    for label in ("Data Freshness", "Terakhir Dilihat", "Dibuat Pada"):
        column = header_indexes[label]
        for row in range(2, sheet.max_row + 1):
            sheet.cell(row=row, column=column).number_format = "yyyy-mm-dd hh:mm"

    sample_rows = list(sheet.iter_rows(min_row=2, max_row=min(sheet.max_row, 101), values_only=True))
    for column_index, header in enumerate(headers, start=1):
        sample_values = [str(header)] + [
            str(row[column_index - 1] or "") for row in sample_rows
        ]
        width = min(max(max((len(value) for value in sample_values), default=12) + 2, 12), 48)
        sheet.column_dimensions[get_column_letter(column_index)].width = width

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output


def _safe_spreadsheet_value(value: Any) -> Any:
    if isinstance(value, datetime) and value.tzinfo is not None:
        return value.replace(tzinfo=None)
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + value
    return value if value is not None else ""
