path = r"d:\market_intelligence\app\services\event_intelligence.py"
with open(path, "r", encoding="utf-8") as f:
    code = f.read()

# Replace A1:N1 with A1:O1
code = code.replace('ws.merge_cells("A1:N1")', 'ws.merge_cells("A1:O1")')
code = code.replace('ws.merge_cells("A2:N2")', 'ws.merge_cells("A2:O2")')

# Replace headers definition
old_headers = """        headers = [
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
        ]"""

new_headers = """        headers = [
            ("No", 6, "center"),
            ("Nama Event", 35, "left"),
            ("Jenis Event", 20, "left"),
            ("Tanggal Pelaksanaan", 28, "center"),
            ("Status Tanggal", 20, "center"),
            ("Tahun", 10, "center"),
            ("Venue / Gedung", 28, "left"),
            ("Kota", 16, "left"),
            ("Provinsi", 16, "left"),
            ("Penyelenggara", 28, "left"),
            ("Status", 14, "center"),
            ("Skor", 10, "right"),
            ("Keterangan & Catatan Tanggal", 35, "left"),
            ("Website Resmi", 25, "left"),
            ("URL Sumber Bukti", 30, "left")
        ]"""

code = code.replace(old_headers, new_headers)

# Replace status_tgl and row_data
old_row = """            status_tgl = "Pasti" if ev.is_date_confirmed else ("Bulan TBD" if ev.date_precision == "month" else "Tentatif")

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
            ]"""

new_row = """            if ev.is_date_confirmed:
                status_tgl = "Pasti / Terkonfirmasi"
            elif ev.date_precision == "month":
                status_tgl = "Bulan (Estimasi)"
            else:
                status_tgl = "Tentatif (Estimasi)"

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
                (ev.clean_website or "-", "left"),
                (ev.clean_source_url or ev.source_url or "-", "left")
            ]"""

code = code.replace(old_row, new_row)

old_hyperlink = """                if col_idx == 14 and isinstance(val, str) and val.startswith("http"):
                    cell.hyperlink = val
                    cell.font = Font(name="Calibri", size=10, color="0044CC", underline="single")"""

new_hyperlink = """                if col_idx in [14, 15] and isinstance(val, str) and val.startswith("http"):
                    cell.hyperlink = val
                    cell.font = Font(name="Calibri", size=10, color="0044CC", underline="single")"""

code = code.replace(old_hyperlink, new_hyperlink)

with open(path, "w", encoding="utf-8") as f:
    f.write(code)

print("Successfully updated export_events_to_excel with URL Sumber column and Estimasi labels!")

