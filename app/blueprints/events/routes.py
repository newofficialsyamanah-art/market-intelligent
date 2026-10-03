"""Routes for Event Intelligence Workspace (Phase 5)."""

import csv
import io
import json
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, Response
from flask_login import login_required, current_user

from app.extensions import db
from app.models import Event, EventParticipant, Organization, utc_now
from app.utils import roles_required, log_activity
from app.services.event_intelligence import EventIntelligenceService

events_bp = Blueprint("events", __name__)


@events_bp.route("/")
@login_required
@roles_required("business_analyst", "marketing", "management")
def index():
    """Event Intelligence Workspace - Daftar & Pencarian Event B2B."""
    q = request.args.get("q", "").strip()
    event_type = request.args.get("event_type", "").strip()
    relevance = request.args.get("relevance", "").strip()
    sport = request.args.get("sport", "").strip()
    city = request.args.get("city", "").strip()
    province = request.args.get("province", "").strip()
    status = request.args.get("status", "").strip()
    organizer = request.args.get("organizer", "").strip()
    source = request.args.get("source", "").strip()
    verification_status = request.args.get("verification_status", "").strip()
    start_date_from_raw = request.args.get("start_date_from", "").strip()
    start_date_to_raw = request.args.get("start_date_to", "").strip()
    page = request.args.get("page", 1, type=int)

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

    items, total_count, total_pages = EventIntelligenceService.get_workspace_events(
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
        page=page,
        per_page=15,
    )

    # Unique filter options
    event_types = [
        r[0] for r in db.session.query(Event.event_type)
        .filter(Event.event_type.isnot(None), Event.event_type != "")
        .distinct().order_by(Event.event_type).all()
    ]
    cities = [
        r[0] for r in db.session.query(Event.city)
        .filter(Event.city.isnot(None), Event.city != "")
        .distinct().order_by(Event.city).all()
    ]
    from app.utils import get_all_indonesia_provinces
    db_provinces = [
        r[0] for r in db.session.query(Event.province)
        .filter(Event.province.isnot(None), Event.province != "")
        .distinct().all()
    ]
    provinces = get_all_indonesia_provinces(db_provinces)

    # Metrics summary & category breakdown
    total_events = Event.query.count()
    high_rel_count = Event.query.filter(Event.relevance_score >= 80).count()
    total_participants = EventParticipant.query.count()
    category_summary = {
        "expo_b2b": Event.query.filter(db.or_(Event.event_type.ilike("%expo%"), Event.event_type.ilike("%exhibition%"), Event.event_type.ilike("%trade%"))).count(),
        "tournament": Event.query.filter(db.or_(Event.event_type.ilike("%sport%"), Event.event_type.ilike("%tournament%"))).count(),
        "career_fair": Event.query.filter(Event.event_type.ilike("%fair%")).count(),
        "conference": Event.query.filter(Event.event_type.ilike("%conference%")).count(),
    }

    return render_template(
        "events/index.html",
        items=items,
        total_count=total_count,
        total_pages=total_pages,
        current_page=page,
        category_summary=category_summary,
        filters={
            "q": q,
            "event_type": event_type,
            "relevance": relevance,
            "sport": sport,
            "city": city,
            "province": province,
            "status": status,
            "organizer": organizer,
            "source": source,
            "verification_status": verification_status,
            "start_date_from": start_date_from_raw,
            "start_date_to": start_date_to_raw,
        },
        event_types=event_types,
        all_sports=["Futsal", "Sepak Bola", "Basket", "Running", "Badminton", "Voli", "Sepeda", "Esports", "Tenis"],
        cities=cities,
        provinces=provinces,
        total_events=total_events,
        high_rel_count=high_rel_count,
        total_participants=total_participants,
    )


@events_bp.route("/<int:event_id>")
@login_required
@roles_required("business_analyst", "marketing", "management")
def detail(event_id: int):
    """Detail Event Intelligence - Metadata, Organizer, Exhibitors, Sponsors, Partners, Speakers."""
    detail_data = EventIntelligenceService.get_event_detail(event_id)
    if not detail_data:
        flash("Event tidak ditemukan.", "danger")
        return redirect(url_for("events.index"))

    return render_template(
        "events/detail.html",
        event=detail_data["event"],
        socials=detail_data["socials"],
        participants_count=detail_data["participants_count"],
        by_role=detail_data["by_role"],
        relevance_badge=detail_data["relevance_badge"],
    )


@events_bp.route("/calendar")
@login_required
@roles_required("business_analyst", "marketing", "management")
def calendar():
    """Upcoming events timeline & calendar view."""
    upcoming_events = Event.query.filter(
        Event.status.in_(["upcoming", "ongoing"])
    ).order_by(Event.start_date.asc()).all()

    return render_template(
        "events/calendar.html",
        events=upcoming_events,
    )


@events_bp.route("/api/calendar")
@login_required
@roles_required("business_analyst", "marketing", "management")
def api_calendar():
    """API endpoint returning events formatted for calendar components."""
    events = Event.query.order_by(Event.start_date.asc()).all()
    payload = []
    for ev in events:
        payload.append({
            "id": ev.id,
            "title": ev.name,
            "start": ev.start_date.isoformat() if ev.start_date else None,
            "end": ev.end_date.isoformat() if ev.end_date else None,
            "venue": ev.venue,
            "city": ev.city,
            "relevance_score": ev.relevance_score,
            "status": ev.status,
            "url": url_for("events.detail", event_id=ev.id),
        })
    return jsonify(payload)


@events_bp.route("/new", methods=["GET", "POST"])
@login_required
@roles_required("business_analyst", "marketing")
def create_event():
    """Form pembuatan event baru / ingest manual."""
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("Nama event wajib diisi.", "danger")
            return redirect(url_for("events.create_event"))

        event_data = {
            "name": name,
            "event_type": request.form.get("event_type", "Exhibition / Trade Fair"),
            "organizer": request.form.get("organizer", "").strip() or None,
            "venue": request.form.get("venue", "").strip() or None,
            "city": request.form.get("city", "").strip() or None,
            "province": request.form.get("province", "").strip() or None,
            "address": request.form.get("address", "").strip() or None,
            "website": request.form.get("website", "").strip() or None,
            "description": request.form.get("description", "").strip() or None,
            "status": request.form.get("status", "upcoming"),
        }

        # Parse dates
        start_date_str = request.form.get("start_date")
        if start_date_str:
            try:
                event_data["start_date"] = datetime.strptime(start_date_str, "%Y-%m-%d")
            except ValueError:
                pass
        end_date_str = request.form.get("end_date")
        if end_date_str:
            try:
                event_data["end_date"] = datetime.strptime(end_date_str, "%Y-%m-%d")
            except ValueError:
                pass

        event, is_created, msg = EventIntelligenceService.create_or_update_event(event_data)
        log_activity("create_event", f"{'Membuat' if is_created else 'Memperbarui'} event {event.name} (#{event.id})")
        flash(f"Event '{event.name}' berhasil {'disimpan' if is_created else 'diperbarui'} ({msg}).", "success")
        return redirect(url_for("events.detail", event_id=event.id))

    return render_template("events/create.html")


@events_bp.route("/discover", methods=["POST"])
@login_required
@roles_required("business_analyst", "marketing")
def discover_events_action():
    """Trigger dynamic live event discovery across Indonesia."""
    query = request.form.get("query", "").strip()
    sport = request.form.get("sport", "").strip()
    city = request.form.get("city", "").strip()
    province = request.form.get("province", "").strip()
    limit = int(request.form.get("limit", 8))

    if sport:
        if query:
            query = f"Turnamen {sport} {query}"
        else:
            query = f"Turnamen {sport} kejuaraan kompetisi"

    try:
        res = EventIntelligenceService.discover_events(query=query, city=city, province=province, limit=limit)
        wilayah_label = city or province or "Seluruh Indonesia"
        if sport:
            wilayah_label += f" [Olahraga: {sport}]"
        flash(f"Discovery Event ({wilayah_label}) selesai: {res['total_processed']} event diproses ({res['created']} event baru, {res['updated']} diperbarui).", "success")
        log_activity("discover_events", f"Discovery event {wilayah_label}: {res['created']} baru")
    except Exception as e:
        flash(f"Discovery Event gagal: {e}", "danger")
    return redirect(url_for("events.index"))



@events_bp.route("/<int:event_id>/link-participant", methods=["POST"])
@login_required
@roles_required("business_analyst", "marketing")
def link_participant(event_id: int):
    """Menghubungkan organisasi ke event sebagai partisipan."""
    event = db.session.get(Event, event_id)
    if not event:
        flash("Event tidak ditemukan.", "danger")
        return redirect(url_for("events.index"))

    org_id = request.form.get("organization_id", type=int)
    role = request.form.get("role", "exhibitor").strip().lower()
    booth_number = request.form.get("booth_number", "").strip() or None
    notes = request.form.get("notes", "").strip() or None

    if not org_id:
        flash("Organisasi wajib dipilih.", "danger")
        return redirect(url_for("events.detail", event_id=event_id))

    org = db.session.get(Organization, org_id)
    if not org:
        flash("Organisasi tidak ditemukan.", "danger")
        return redirect(url_for("events.detail", event_id=event_id))

    valid_roles = ["organizer", "exhibitor", "sponsor", "partner", "speaker"]
    if role not in valid_roles:
        flash(f"Peran partisipan tidak valid. Pilih salah satu: {', '.join(valid_roles)}", "danger")
        return redirect(url_for("events.detail", event_id=event_id))

    part, is_new = EventIntelligenceService.link_participant(
        event_id=event_id,
        organization_id=org_id,
        role=role,
        booth_number=booth_number,
        notes=notes
    )

    action_str = "ditambahkan sebagai" if is_new else "sudah terhubung sebagai"
    flash(f"Organisasi '{org.name}' berhasil {action_str} {role.upper()} pada event ini.", "success")
    log_activity("link_event_participant", f"Linked Org #{org_id} to Event #{event_id} as {role}")
    return redirect(url_for("events.detail", event_id=event_id))


@events_bp.route("/export")
@login_required
@roles_required("business_analyst", "marketing")
def export():
    """Export Event & Participant Intelligence ke file CSV (Excel-ready UTF-8)."""
    event_id = request.args.get("event_id", type=int)

    query = db.session.query(
        Event.name.label("event_name"),
        Event.event_type,
        Event.status.label("event_status"),
        Event.start_date,
        Event.end_date,
        Event.venue,
        Event.city.label("event_city"),
        Event.relevance_score,
        EventParticipant.role.label("participant_role"),
        EventParticipant.booth_number,
        EventParticipant.notes.label("participant_notes"),
        Organization.id.label("org_id"),
        Organization.name.label("org_name"),
        Organization.industry.label("org_industry"),
        Organization.website.label("org_website"),
        Organization.phone.label("org_phone"),
        Organization.email.label("org_email"),
        Organization.city.label("org_city"),
        Organization.province.label("org_province"),
        Organization.priority_tier.label("org_tier"),
    ).join(EventParticipant, Event.id == EventParticipant.event_id) \
     .join(Organization, EventParticipant.organization_id == Organization.id)

    if event_id:
        query = query.filter(Event.id == event_id)

    rows = query.order_by(Event.start_date.desc(), Organization.name).all()

    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        "Event Name",
        "Event Type",
        "Event Status",
        "Start Date",
        "End Date",
        "Venue",
        "Event City",
        "Relevance Score",
        "Participant Role",
        "Booth Number",
        "Notes",
        "Organization ID",
        "Organization Name",
        "Industry",
        "Website",
        "Phone",
        "Email",
        "City",
        "Province",
        "Priority Tier",
    ])

    for r in rows:
        writer.writerow([
            r.event_name or "",
            r.event_type or "",
            r.event_status or "",
            r.start_date.strftime("%Y-%m-%d") if r.start_date else "",
            r.end_date.strftime("%Y-%m-%d") if r.end_date else "",
            r.venue or "",
            r.event_city or "",
            r.relevance_score or 0,
            r.participant_role or "",
            r.booth_number or "",
            r.participant_notes or "",
            r.org_id or "",
            r.org_name or "",
            r.org_industry or "",
            r.org_website or "",
            r.org_phone or "",
            r.org_email or "",
            r.org_city or "",
            r.org_province or "",
            r.org_tier or "",
        ])

    csv_data = output.getvalue()
    # Add UTF-8 BOM so Excel opens indonesian special characters seamlessly
    response = Response("\ufeff" + csv_data, mimetype="text/csv; charset=utf-8")
    filename = f"event_participants_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    log_activity("export_event_participants", f"Exported {len(rows)} event participant records")
    return response
