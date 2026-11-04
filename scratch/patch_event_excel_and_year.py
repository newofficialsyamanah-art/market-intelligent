path = r"d:\market_intelligence\app\services\event_intelligence.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update signature of get_workspace_events to accept month and optional per_page
old_sig = """    @classmethod
    def get_workspace_events(
        cls,
        q: str = "",
        event_type: str = "",
        relevance: str = "",
        city: str = "",
        province: str = "",
        sport: str = "",
        status: str = "",
        organizer: str = "",
        start_date_from: Optional[datetime] = None,
        start_date_to: Optional[datetime] = None,
        source: str = "",
        verification_status: str = "",
        year: str = "",
        page: int = 1,
        per_page: int = 20
    ) -> Tuple[List[Event], int, int]:"""

new_sig = """    @classmethod
    def get_workspace_events(
        cls,
        q: str = "",
        event_type: str = "",
        relevance: str = "",
        city: str = "",
        province: str = "",
        sport: str = "",
        status: str = "",
        organizer: str = "",
        start_date_from: Optional[datetime] = None,
        start_date_to: Optional[datetime] = None,
        source: str = "",
        verification_status: str = "",
        year: str = "",
        month: str = "",
        page: int = 1,
        per_page: Optional[int] = 20
    ) -> Tuple[List[Event], int, int]:"""

content = content.replace(old_sig, new_sig)

# 2. Update year filter logic and add month filter
old_year_filter = """        if year:
            year_clean = year.strip()
            if year_clean.isdigit():
                y_int = int(year_clean)
                query = query.filter(
                    db.or_(
                        Event.name.like(f"%{year_clean}%"),
                        db.extract("year", Event.start_date) == y_int
                    )
                )
            else:
                query = query.filter(Event.name.like(f"%{year_clean}%"))"""

new_year_filter = """        if year:
            year_clean = year.strip()
            if year_clean.isdigit():
                y_int = int(year_clean)
                other_years = [str(y) for y in [2024, 2025, 2026, 2027, 2028, 2029] if y != y_int]
                query = query.filter(
                    db.or_(
                        Event.name.like(f"%{year_clean}%"),
                        db.and_(
                            db.extract("year", Event.start_date) == y_int,
                            *[~Event.name.like(f"%{oy}%") for oy in other_years]
                        )
                    )
                )
            else:
                query = query.filter(Event.name.like(f"%{year_clean}%"))

        if month:
            month_clean = month.strip()
            if month_clean.isdigit():
                m_int = int(month_clean)
                query = query.filter(db.extract("month", Event.start_date) == m_int)"""

content = content.replace(old_year_filter, new_year_filter)

# 3. Handle per_page is None or <= 0
old_pagination = """        total_count = query.count()
        total_pages = (total_count + per_page - 1) // per_page if total_count > 0 else 1"""

new_pagination = """        total_count = query.count()
        has_info = db.case(
            (db.or_(Event.website.isnot(None), Event.social_json.isnot(None), Event.source_url.like('http%')), 1),
            else_=0
        )
        if per_page is None or per_page <= 0:
            items = query.order_by(
                has_info.desc(),
                Event.relevance_score.desc(),
                Event.start_date.desc().nullslast()
            ).all()
            return items, total_count, 1

        total_pages = (total_count + per_page - 1) // per_page if total_count > 0 else 1"""

content = content.replace(old_pagination, new_pagination)

# 4. Add export_events_to_excel method to EventIntelligenceService
excel_method = """    @classmethod
    def export_events_to_excel(cls, events: List[Event], filter_summary: str = ""):
        \"\"\"Mengekspor daftar event terfilter ke file Excel (.xlsx) dengan formatting profesional.\"\"\"
        import io
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils import get_column_letter

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Daftar Event"

        # Judul & Info Metadata
        ws.merge_cells("A1:N1")
        title_cell = ws["A1"]
        title_cell.value = "MARKET INTELLIGENCE - DAFTAR EVENT B2B & EXPO"
        title_cell.font = Font(name="Calibri", size=14, bold=True, color="FFFFFF")
        title_cell.fill = PatternFill(start_color="1B365D", end_color="1B365D", fill_type="solid")
        title_cell.alignment = Alignment(horizontal="center", vertical="center")
        ws.row_dimensions[1].height = 32

        ws.merge_cells("A2:N2")
        meta_cell = ws["A2"]
        meta_cell.value = f"Ringkasan Filter: {filter_summary or 'Semua Data'} | Diunduh pada: {datetime.now().strftime('%d %B %Y %H:%M WIB')} | Total: {len(events)} Event"
        meta_cell.font = Font(name="Calibri", size=9, italic=True, color="475569")
        meta_cell.fill = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")
        meta_cell.alignment = Alignment(horizontal="center", vertical="center")
        ws.row_dimensions[2].height = 20

        # Baris Header Kolom
        headers = [
            ("No", 6, "center"),
            ("Nama Event", 35, "left"),
            ("Jenis Event", 20, "left"),
            ("Tanggal Pelaksanaan", 25, "center"),
            ("Status Tanggal", 15, "center"),
            ("Tahun", 10, "center"),
            ("Venue / Gedung", 28, "left"),
            ("Kota", 16, "left"),
            ("Provinsi", 16, "left"),
            ("Penyelenggara", 28, "left"),
            ("Status", 14, "center"),
            ("Skor", 10, "right"),
            ("Peluang B2B / Apparel", 35, "left"),
            ("Website Resmi", 25, "left")
        ]

        header_font = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="203A43", end_color="203A43", fill_type="solid")
        thin_border = Border(
            left=Side(style="thin", color="CBD5E1"),
            right=Side(style="thin", color="CBD5E1"),
            top=Side(style="thin", color="CBD5E1"),
            bottom=Side(style="thin", color="CBD5E1")
        )

        ws.row_dimensions[4].height = 26
        for col_idx, (h_name, width, align) in enumerate(headers, 1):
            cell = ws.cell(row=4, column=col_idx, value=h_name)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.border = thin_border
            ws.column_dimensions[get_column_letter(col_idx)].width = width

        # Data Rows
        zebra_fill = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")
        white_fill = PatternFill(start_color="FFFFFF", end_color="FFFFFF", fill_type="solid")
        data_font = Font(name="Calibri", size=10)

        for row_idx, ev in enumerate(events, 5):
            is_even = (row_idx % 2 == 0)
            row_fill = zebra_fill if is_even else white_fill
            ws.row_dimensions[row_idx].height = 22

            status_tgl = "Pasti" if ev.is_date_confirmed else ("Bulan TBD" if ev.date_precision == "month" else "Tentatif")

            row_data = [
                (row_idx - 4, "center"),
                (ev.name or "", "left"),
                (ev.event_type or "-", "left"),
                (ev.date_display or "-", "center"),
                (status_tgl, "center"),
                (ev.event_year or "-", "center"),
                (ev.venue or "-", "left"),
                (ev.city or "-", "left"),
                (ev.province or "-", "left"),
                (ev.organizer or "-", "left"),
                ((ev.status or "upcoming").capitalize(), "center"),
                (ev.relevance_score or 0, "right"),
                (ev.relevance_notes or ev.description or "-", "left"),
                (ev.clean_website or "-", "left")
            ]

            for col_idx, (val, align) in enumerate(row_data, 1):
                cell = ws.cell(row=row_idx, column=col_idx, value=val)
                cell.font = data_font
                cell.fill = row_fill
                cell.border = thin_border
                cell.alignment = Alignment(horizontal=align, vertical="center")

                if col_idx == 14 and isinstance(val, str) and val.startswith("http"):
                    cell.hyperlink = val
                    cell.font = Font(name="Calibri", size=10, color="0044CC", underline="single")

        stream = io.BytesIO()
        wb.save(stream)
        stream.seek(0)
        return stream
"""

# Place export_events_to_excel at the end of EventIntelligenceService class
content = content + "\n\n" + excel_method

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Successfully updated app/services/event_intelligence.py with export_events_to_excel and refined year/month filtering!")

