path = r"d:\market_intelligence\app\blueprints\events\routes.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Add send_file to flask import
content = content.replace(
    "from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, Response",
    "from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, Response, send_file"
)

# 2. Add month parameter in index()
old_index_args = """    verification_status = request.args.get("verification_status", "").strip()
    year = request.args.get("year", "").strip()
    start_date_from_raw = request.args.get("start_date_from", "").strip()"""

new_index_args = """    verification_status = request.args.get("verification_status", "").strip()
    year = request.args.get("year", "").strip()
    month = request.args.get("month", "").strip()
    start_date_from_raw = request.args.get("start_date_from", "").strip()"""

content = content.replace(old_index_args, new_index_args)

# 3. Pass month to get_workspace_events
old_call = """        source=source,
        verification_status=verification_status,
        year=year,
        page=page,
        per_page=15,
    )"""

new_call = """        source=source,
        verification_status=verification_status,
        year=year,
        month=month,
        page=page,
        per_page=15,
    )"""

content = content.replace(old_call, new_call)

# 4. Pass month and available_years to template
old_filters = """            "year": year,
            "start_date_from": start_date_from_raw,
            "start_date_to": start_date_to_raw,
        },
        event_types=event_types,"""

new_filters = """            "year": year,
            "month": month,
            "start_date_from": start_date_from_raw,
            "start_date_to": start_date_to_raw,
        },
        available_years=[2027, 2026, 2025, 2024],
        event_types=event_types,"""

content = content.replace(old_filters, new_filters)

# 5. Add export_excel route
export_route_code = """
@events_bp.route("/export/excel")
@login_required
@roles_required("business_analyst", "marketing", "management")
def export_excel():
    \"\"\"Export data event ke file Excel (.xlsx) berdasarkan filter waktu (tahun, bulan, tanggal spesifik) dan kriteria lainnya.\"\"\"
    q = (request.args.get("q") or "").strip()
    event_type = (request.args.get("event_type") or "").strip()
    relevance = (request.args.get("relevance") or "").strip()
    sport = (request.args.get("sport") or "").strip()
    city = (request.args.get("city") or "").strip()
    province = (request.args.get("province") or "").strip()
    status = (request.args.get("status") or "").strip()
    organizer = (request.args.get("organizer") or "").strip()
    source = (request.args.get("source") or "").strip()
    verification_status = (request.args.get("verification_status") or "").strip()
    year = (request.args.get("year") or "").strip()
    month = (request.args.get("month") or "").strip()
    start_date_from_raw = (request.args.get("start_date_from") or "").strip()
    start_date_to_raw = (request.args.get("start_date_to") or "").strip()

    start_date_from = None
    if start_date_from_raw:
        try:
            start_date_from = datetime.strptime(start_date_from_raw, "%Y-%m-%d")
        except ValueError:
            pass

    start_date_to = None
    if start_date_to_raw:
        try:
            start_date_to = datetime.strptime(start_date_to_raw, "%Y-%m-%d")
        except ValueError:
            pass

    # Ambil SEMUA event yang cocok (per_page=None)
    events, total, _ = EventIntelligenceService.get_workspace_events(
        q=q,
        event_type=event_type,
        relevance=relevance,
        city=city,
        province=province,
        sport=sport,
        status=status,
        organizer=organizer,
        start_date_from=start_date_from,
        start_date_to=start_date_to,
        source=source,
        verification_status=verification_status,
        year=year,
        month=month,
        per_page=None
    )

    # Buat label filter untuk nama file & header
    filter_parts = []
    if year:
        filter_parts.append(f"Tahun_{year}")
    if month:
        months_id = ["", "Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober", "November", "Desember"]
        m_idx = int(month) if month.isdigit() and 1 <= int(month) <= 12 else None
        if m_idx:
            filter_parts.append(f"Bulan_{months_id[m_idx]}")
    if start_date_from_raw or start_date_to_raw:
        filter_parts.append(f"Tgl_{start_date_from_raw or 'Awal'}_sd_{start_date_to_raw or 'Akhir'}")
    if city:
        filter_parts.append(f"Kota_{city}")
    if not filter_parts:
        filter_parts.append("Semua_Waktu")

    filter_label = "_".join(filter_parts)
    now_str = datetime.now().strftime("%Y%m%d_%H%M")
    filename = f"Event_Intelligence_{filter_label}_{now_str}.xlsx"

    excel_stream = EventIntelligenceService.export_events_to_excel(
        events=events,
        filter_summary=f"Waktu: {filter_label.replace('_', ' ')} | Ditemukan: {total} Event"
    )

    log_activity("export_events_excel", f"Export {len(events)} event ke Excel ({filter_label})")

    return send_file(
        excel_stream,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename
    )
"""

content = content + "\n" + export_route_code

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Successfully updated app/blueprints/events/routes.py with export_excel and month/year filters!")

