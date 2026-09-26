"""Routes for Marketing Intelligence Workspace (Phase 6).

BUKAN CRM: Tidak ada sales pipeline, deals, stages, atau tracking aktivitas sales.
Berfokus pada eksplorasi target pasar B2B, segmentasi preset apparel/merchandise,
analisis peluang event-driven, dan export akun target berkualitas tinggi.
"""

import io
import csv
import json
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, Response
from flask_login import login_required, current_user

from app.extensions import db
from app.models import Organization, Event, EventParticipant, Campaign, CampaignTarget, Prospect, utc_now
from app.utils import log_activity, roles_required
from app.services.marketing_intelligence import MarketingIntelligenceService, SEGMENT_PRESETS
from app.services.product_fit_service import ProductFitService, SUPPORTED_PRODUCTS

marketing_bp = Blueprint("marketing", __name__)


@marketing_bp.route("/")
@marketing_bp.route("/index")
@marketing_bp.route("/dashboard")
@login_required
@roles_required("marketing", "business_analyst", "management")
def dashboard():
    """Marketing Intelligence Dashboard - Agregat pasar, prioritas akun, demand apparel, dan contactability."""
    metrics = MarketingIntelligenceService.get_marketing_dashboard_metrics()
    presets = MarketingIntelligenceService.get_segment_presets_overview()
    return render_template(
        "marketing/dashboard.html",
        metrics=metrics,
        presets=presets,
    )


# Alias endpoint untuk kompatibilitas backward dengan url_for('marketing.index')
marketing_bp.add_url_rule("/", endpoint="index", view_func=dashboard)
marketing_bp.add_url_rule("/index", endpoint="index", view_func=dashboard)
marketing_bp.add_url_rule("/dashboard", endpoint="dashboard", view_func=dashboard)



@marketing_bp.route("/targets")
@login_required
@roles_required("marketing", "business_analyst")
def targets():
    """Target Intelligence & Account Explorer - Eksplorasi akun target B2B dengan filter komprehensif (F6.1)."""
    q = request.args.get("q", "").strip()
    priority_tier = request.args.get("priority_tier", "").strip()
    industry = request.args.get("industry", "").strip()
    organization_type = request.args.get("organization_type", "").strip()
    organization_subtype = request.args.get("organization_subtype", "").strip()
    sport = request.args.get("sport", "").strip()
    employee_size = request.args.get("employee_size", "").strip()
    event_relevance = request.args.get("event_relevance", "").strip()
    province = request.args.get("province", "").strip()
    city = request.args.get("city", "").strip()
    product_fit = request.args.get("product_fit", "").strip()
    has_event = request.args.get("has_event") == "1"
    event_id = request.args.get("event_id", type=int)
    has_email = request.args.get("has_email") == "1"
    has_phone = request.args.get("has_phone") == "1"
    has_website = request.args.get("has_website") == "1"
    has_social = request.args.get("has_social") == "1"
    has_instagram = request.args.get("has_instagram") == "1"
    has_tiktok = request.args.get("has_tiktok") == "1"
    has_facebook = request.args.get("has_facebook") == "1"
    has_linkedin = request.args.get("has_linkedin") == "1"
    min_score_raw = request.args.get("min_score", "").strip()
    page = request.args.get("page", 1, type=int)

    min_score = int(min_score_raw) if min_score_raw.isdigit() else None

    items, total_count, total_pages = MarketingIntelligenceService.search_marketing_targets(
        q=q,
        priority_tier=priority_tier,
        industry=industry,
        province=province,
        city=city,
        product_fit=product_fit,
        organization_type=organization_type,
        organization_subtype=organization_subtype,
        sport=sport,
        employee_size=employee_size,
        event_relevance=event_relevance,
        has_event=has_event,
        event_id=event_id,
        has_email=has_email,
        has_phone=has_phone,
        has_website=has_website,
        has_social=has_social,
        has_instagram=has_instagram,
        has_tiktok=has_tiktok,
        has_facebook=has_facebook,
        has_linkedin=has_linkedin,
        min_score=min_score,
        page=page,
        per_page=25,
    )

    all_industries = [
        r[0] for r in db.session.query(Organization.industry)
        .filter(Organization.industry.isnot(None), Organization.industry != "")
        .distinct().order_by(Organization.industry).limit(80).all()
    ]
    all_org_types = [
        r[0] for r in db.session.query(Organization.organization_type)
        .filter(Organization.organization_type.isnot(None), Organization.organization_type != "")
        .distinct().order_by(Organization.organization_type).all()
    ]
    all_sports = [
        r[0] for r in db.session.query(Organization.sport)
        .filter(Organization.sport.isnot(None), Organization.sport != "")
        .distinct().order_by(Organization.sport).all()
    ]
    all_provinces = [
        r[0] for r in db.session.query(Organization.province)
        .filter(Organization.province.isnot(None), Organization.province != "", Organization.province != "nan")
        .distinct().order_by(Organization.province).all()
    ]
    all_events = Event.query.order_by(Event.start_date.desc()).all()
    active_campaigns = Campaign.query.filter(Campaign.status.in_(["draft", "ready", "active"])).order_by(Campaign.created_at.desc()).all()

    return render_template(
        "marketing/targets.html",
        items=items,
        total_count=total_count,
        total_pages=total_pages,
        current_page=page,
        filters={
            "q": q,
            "priority_tier": priority_tier,
            "industry": industry,
            "organization_type": organization_type,
            "organization_subtype": organization_subtype,
            "sport": sport,
            "employee_size": employee_size,
            "event_relevance": event_relevance,
            "province": province,
            "city": city,
            "product_fit": product_fit,
            "has_event": "1" if has_event else "",
            "event_id": event_id or "",
            "has_email": "1" if has_email else "",
            "has_phone": "1" if has_phone else "",
            "has_website": "1" if has_website else "",
            "has_social": "1" if has_social else "",
            "has_instagram": "1" if has_instagram else "",
            "has_tiktok": "1" if has_tiktok else "",
            "has_facebook": "1" if has_facebook else "",
            "has_linkedin": "1" if has_linkedin else "",
            "min_score": min_score_raw,
        },
        all_industries=all_industries,
        all_org_types=all_org_types,
        all_sports=all_sports,
        all_provinces=all_provinces,
        all_events=all_events,
        active_campaigns=active_campaigns,
    )


@marketing_bp.route("/segments")
@login_required
@roles_required("marketing", "business_analyst")
def segments():
    """Segmentation Engine - Preset segmentasi pasar dan drill-down akun target."""
    preset_key = request.args.get("preset", "corporate_uniform").strip()
    if preset_key not in SEGMENT_PRESETS:
        preset_key = "corporate_uniform"

    page = request.args.get("page", 1, type=int)

    items, total_count, total_pages, current_preset = MarketingIntelligenceService.get_segment_drilldown(
        preset_key=preset_key,
        page=page,
        per_page=25
    )

    presets_overview = MarketingIntelligenceService.get_segment_presets_overview()

    return render_template(
        "marketing/segments.html",
        items=items,
        total_count=total_count,
        total_pages=total_pages,
        current_page=page,
        current_preset=current_preset,
        presets_overview=presets_overview,
        active_preset_key=preset_key,
    )


@marketing_bp.route("/export")
@login_required
@roles_required("marketing", "business_analyst")
def export():
    """Export akun target pasar ke CSV / Excel (F6.5).
    Menghasilkan 22 kolom minimal berbasis entitas Master Organization:
    organization, organization_type, industry, product_fit, opportunity_score, priority_tier,
    website, domain, instagram, facebook, linkedin, phone, email, address, city, province,
    employee_size, event_count, high_relevance_event_count, latest_event, source, freshness.
    """
    preset_key = request.args.get("preset", "").strip()
    priority_tier = request.args.get("priority_tier", "").strip()
    industry = request.args.get("industry", "").strip()
    organization_type = request.args.get("organization_type", "").strip()
    has_event = request.args.get("has_event") == "1"
    contactable_only = request.args.get("contactable_only") == "1"
    export_format = request.args.get("format", "csv").lower()

    query = db.session.query(Organization)

    if preset_key and preset_key in SEGMENT_PRESETS:
        query = MarketingIntelligenceService.get_segment_query(preset_key)

    if priority_tier:
        query = query.filter(Organization.priority_tier == priority_tier)

    if industry:
        query = query.filter(Organization.industry == industry)

    if organization_type:
        query = query.filter(Organization.organization_type == organization_type)

    if has_event:
        query = query.join(EventParticipant, Organization.id == EventParticipant.organization_id).distinct()

    if contactable_only:
        query = query.filter(
            db.or_(
                db.and_(Organization.email.isnot(None), Organization.email != "", Organization.email != "nan"),
                db.and_(Organization.phone.isnot(None), Organization.phone != "", Organization.phone != "nan")
            )
        )

    # Batasi export maksimal 10.000 records per stream untuk stabilitas memori
    orgs = query.order_by(Organization.opportunity_score.desc(), Organization.id.asc()).limit(10000).all()

    # Minimal fields F6.5
    headers = [
        "organization",
        "organization_type",
        "industry",
        "product_fit",
        "opportunity_score",
        "priority_tier",
        "website",
        "domain",
        "instagram",
        "facebook",
        "linkedin",
        "phone",
        "email",
        "address",
        "city",
        "province",
        "employee_size",
        "event_count",
        "high_relevance_event_count",
        "latest_event",
        "source",
        "freshness"
    ]

    rows = []
    for org in orgs:
        socials = {}
        if org.social_json:
            try:
                socials = json.loads(org.social_json) if isinstance(json.loads(org.social_json), dict) else {}
            except Exception:
                socials = {}

        parts = org.participations
        event_count = len(parts)
        high_rel_count = sum(1 for p in parts if p.event and (p.event.relevance_score or 0) >= 80)

        latest_event_name = ""
        if parts:
            sorted_parts = sorted(
                parts,
                key=lambda p: (p.event.start_date if p.event and p.event.start_date else datetime.min),
                reverse=True
            )
            if sorted_parts and sorted_parts[0].event:
                latest_event_name = sorted_parts[0].event.name

        freshness_str = org.data_freshness.strftime("%Y-%m-%d %H:%M") if org.data_freshness else (
            org.last_seen.strftime("%Y-%m-%d %H:%M") if org.last_seen else ""
        )

        rows.append([
            org.name,
            org.organization_type or "Perusahaan",
            org.industry or "",
            org.product_fit or "",
            org.opportunity_score or 0,
            org.priority_tier or "",
            org.website if org.website != "nan" else "",
            org.domain if org.domain != "nan" else "",
            socials.get("instagram", ""),
            socials.get("facebook", ""),
            socials.get("linkedin", ""),
            org.phone if org.phone != "nan" else "",
            org.email if org.email != "nan" else "",
            org.address if org.address != "nan" else "",
            org.city if org.city != "nan" else "",
            org.province if org.province != "nan" else "",
            org.employee_size if org.employee_size != "nan" else "",
            event_count,
            high_rel_count,
            latest_event_name,
            org.source_type or "",
            freshness_str,
        ])

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_filename = f"marketing_targets_{preset_key or 'all'}_{timestamp}"

    if export_format in ("xlsx", "excel"):
        try:
            from openpyxl import Workbook
            wb = Workbook()
            ws = wb.active
            ws.title = "Marketing Targets"
            ws.append(headers)
            for r in rows:
                ws.append(r)
            buf = io.BytesIO()
            wb.save(buf)
            buf.seek(0)
            response = Response(
                buf.getvalue(),
                mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            response.headers["Content-Disposition"] = f"attachment; filename={base_filename}.xlsx"
            log_activity("export_marketing_targets", f"Exported {len(orgs)} target accounts (format: XLSX)")
            return response
        except ImportError:
            pass

    # CSV with UTF-8 BOM
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    for r in rows:
        writer.writerow(r)

    csv_data = output.getvalue()
    response = Response("\ufeff" + csv_data, mimetype="text/csv; charset=utf-8")
    response.headers["Content-Disposition"] = f"attachment; filename={base_filename}.csv"
    log_activity("export_marketing_targets", f"Exported {len(orgs)} target accounts (format: CSV)")
    return response


# ---------- Campaign Management Workspace (F6 & Core Requirement #15-#18) ----------

@marketing_bp.route("/campaigns")
@login_required
@roles_required("marketing", "business_analyst", "management")
def campaigns_index():
    """Daftar seluruh campaign marketing dengan ringkasan status, produk, dan target."""
    campaigns = Campaign.query.order_by(Campaign.created_at.desc()).all()
    status_filter = request.args.get("status", "").strip()
    if status_filter:
        campaigns = [c for c in campaigns if c.status == status_filter]

    total_campaigns = Campaign.query.count()
    active_campaigns = Campaign.query.filter_by(status="active").count()
    ready_campaigns = Campaign.query.filter_by(status="ready").count()
    draft_campaigns = Campaign.query.filter_by(status="draft").count()

    return render_template(
        "marketing/campaigns.html",
        campaigns=campaigns,
        total_campaigns=total_campaigns,
        active_campaigns=active_campaigns,
        ready_campaigns=ready_campaigns,
        draft_campaigns=draft_campaigns,
        current_status=status_filter,
    )


@marketing_bp.route("/campaigns/new", methods=["GET", "POST"])
@login_required
@roles_required("marketing", "business_analyst")
def create_campaign():
    """Form & Handler pembuatan Campaign baru."""
    if request.method == "POST":
        name = request.form.get("name", "").strip() or request.form.get("campaign_name", "").strip()
        product = request.form.get("product", "").strip() or "Jersey / Custom Teamwear"
        description = request.form.get("description", "").strip()
        target_segment = request.form.get("target_segment", "").strip()
        organization_type = request.form.get("organization_type", "").strip()
        province = request.form.get("province", "").strip()
        city = request.form.get("city", "").strip()
        channel = request.form.get("channel", "").strip()
        notes = request.form.get("notes", "").strip()
        status = request.form.get("status", "draft")

        start_date = None
        end_date = None
        if request.form.get("start_date"):
            try:
                start_date = datetime.strptime(request.form.get("start_date"), "%Y-%m-%d")
            except ValueError:
                pass
        if request.form.get("end_date"):
            try:
                end_date = datetime.strptime(request.form.get("end_date"), "%Y-%m-%d")
            except ValueError:
                pass

        if not name:
            flash("Nama campaign wajib diisi.", "warning")
            return redirect(url_for("marketing.create_campaign"))

        campaign = Campaign(
            name=name,
            product=product,
            description=description or None,
            target_segment=target_segment or None,
            organization_type=organization_type or None,
            province=province or None,
            city=city or None,
            start_date=start_date,
            end_date=end_date,
            channel=channel or None,
            notes=notes or None,
            status=status,
            created_by=current_user.id,
        )
        db.session.add(campaign)
        db.session.flush()

        # Jika ada organization_ids yang dipilih langsung (misal dari Explorer)
        org_ids_raw = request.form.get("selected_org_ids", "")
        added_count = 0
        if org_ids_raw:
            org_id_list = [int(oid.strip()) for oid in org_ids_raw.split(",") if oid.strip().isdigit()]
            for oid in org_id_list:
                org = db.session.get(Organization, oid)
                if org:
                    ct = CampaignTarget(
                        campaign_id=campaign.id,
                        organization_id=org.id,
                        product_fit_snapshot=org.product_fit or campaign.product,
                        opportunity_score_snapshot=org.opportunity_score or 0,
                        status="targeted"
                    )
                    db.session.add(ct)
                    added_count += 1
            campaign.prospect_count = added_count

        db.session.commit()
        log_activity("create_campaign", f"Campaign '{name}' (#{campaign.id}) dibuat dengan {added_count} target akun")
        flash(f"Campaign '{name}' berhasil dibuat dengan {added_count} target akun.", "success")
        return redirect(url_for("marketing.campaign_detail", cid=campaign.id))

    return render_template("marketing/campaign_form.html", campaign=None, supported_products=SUPPORTED_PRODUCTS)


@marketing_bp.route("/campaigns/<int:cid>")
@login_required
@roles_required("marketing", "business_analyst", "management")
def campaign_detail(cid):
    """Detail Campaign - Profil, intelijen target Master Organization, event, sinyal sosial, dan aksi."""
    campaign = Campaign.query.get_or_404(cid)

    # Ambil seluruh target yang terhubung
    targets = CampaignTarget.query.filter_by(campaign_id=campaign.id).all()

    # Hitung metrik intelijen target
    total_targets = len(targets)
    contactable_count = 0
    high_fit_count = 0
    event_linked_count = 0
    sport_linked_count = 0

    for t in targets:
        org = t.organization
        if org:
            if (org.email and org.email != "nan") or (org.phone and org.phone != "nan"):
                contactable_count += 1
            if (t.opportunity_score_snapshot or org.opportunity_score or 0) >= 80:
                high_fit_count += 1
            if org.participations:
                event_linked_count += 1
            if org.sport:
                sport_linked_count += 1

    return render_template(
        "marketing/campaign_detail.html",
        campaign=campaign,
        targets=targets,
        total_targets=total_targets,
        contactable_count=contactable_count,
        high_fit_count=high_fit_count,
        event_linked_count=event_linked_count,
        sport_linked_count=sport_linked_count,
    )


@marketing_bp.route("/campaigns/<int:cid>/edit", methods=["GET", "POST"])
@login_required
@roles_required("marketing", "business_analyst")
def edit_campaign(cid):
    """Edit metadata campaign."""
    campaign = Campaign.query.get_or_404(cid)

    if request.method == "POST":
        campaign.name = request.form.get("name", campaign.name).strip()
        campaign.product = request.form.get("product", campaign.product).strip()
        campaign.description = request.form.get("description", campaign.description).strip() or None
        campaign.target_segment = request.form.get("target_segment", campaign.target_segment).strip() or None
        campaign.organization_type = request.form.get("organization_type", campaign.organization_type).strip() or None
        campaign.province = request.form.get("province", campaign.province).strip() or None
        campaign.city = request.form.get("city", campaign.city).strip() or None
        campaign.channel = request.form.get("channel", campaign.channel).strip() or None
        campaign.status = request.form.get("status", campaign.status)
        campaign.notes = request.form.get("notes", campaign.notes).strip() or None

        if request.form.get("start_date"):
            try:
                campaign.start_date = datetime.strptime(request.form.get("start_date"), "%Y-%m-%d")
            except ValueError:
                pass
        if request.form.get("end_date"):
            try:
                campaign.end_date = datetime.strptime(request.form.get("end_date"), "%Y-%m-%d")
            except ValueError:
                pass

        db.session.commit()
        log_activity("edit_campaign", f"Campaign #{campaign.id} '{campaign.name}' diperbarui")
        flash(f"Campaign '{campaign.name}' berhasil diperbarui.", "success")
        return redirect(url_for("marketing.campaign_detail", cid=campaign.id))

    return render_template("marketing/campaign_form.html", campaign=campaign, supported_products=SUPPORTED_PRODUCTS)


@marketing_bp.route("/campaigns/<int:cid>/add-targets", methods=["POST"])
@login_required
@roles_required("marketing", "business_analyst")
def campaign_add_targets(cid):
    """Menambahkan Master Organization target ke dalam Campaign."""
    campaign = Campaign.query.get_or_404(cid)
    raw_candidates = []
    for key in ("organization_ids", "org_ids", "organization_id", "org_id"):
        val = request.form.get(key)
        if val:
            raw_candidates.extend(str(val).split(","))
        list_vals = request.form.getlist(key)
        if list_vals:
            for lv in list_vals:
                raw_candidates.extend(str(lv).split(","))

    org_id_list = []
    for x in raw_candidates:
        x_clean = str(x).strip()
        if x_clean.isdigit():
            org_id_list.append(int(x_clean))
    org_id_list = list(dict.fromkeys(org_id_list))

    if not org_id_list:
        flash("Tidak ada organisasi yang dipilih untuk ditambahkan.", "warning")
        return redirect(url_for("marketing.campaign_detail", cid=cid))

    notes = request.form.get("notes")
    status = request.form.get("status", "selected")
    added_count = 0
    for oid in org_id_list:
        existing = CampaignTarget.query.filter_by(campaign_id=campaign.id, organization_id=oid).first()
        if not existing:
            org = db.session.get(Organization, oid)
            if org:
                ct = CampaignTarget(
                    campaign_id=campaign.id,
                    organization_id=org.id,
                    product_fit_snapshot=org.product_fit or campaign.product,
                    opportunity_score_snapshot=org.opportunity_score or 0,
                    status=status,
                    notes=notes
                )
                db.session.add(ct)
                added_count += 1

    campaign.prospect_count = CampaignTarget.query.filter_by(campaign_id=campaign.id).count() + added_count
    db.session.commit()
    log_activity("campaign_add_targets", f"Menambahkan {added_count} target ke campaign #{campaign.id}")
    flash(f"Berhasil menambahkan {added_count} target akun ke Campaign '{campaign.name}'.", "success")
    return redirect(url_for("marketing.campaign_detail", cid=cid))


@marketing_bp.route("/campaigns/<int:cid>/targets/<int:org_id>/remove", methods=["POST"])
@login_required
@roles_required("marketing", "business_analyst")
def campaign_remove_target(cid, org_id):
    """Menghapus organisasi target dari campaign."""
    target = CampaignTarget.query.filter_by(campaign_id=cid, organization_id=org_id).first_or_404()
    db.session.delete(target)
    campaign = Campaign.query.get(cid)
    if campaign:
        campaign.prospect_count = max(0, (campaign.prospect_count or 1) - 1)
    db.session.commit()
    log_activity("campaign_remove_target", f"Target org #{org_id} dihapus dari campaign #{cid}")
    flash("Target organisasi dihapus dari campaign.", "success")
    return redirect(url_for("marketing.campaign_detail", cid=cid))


@marketing_bp.route("/campaigns/<int:cid>/targets/<int:org_id>/status", methods=["POST"])
@login_required
@roles_required("marketing", "business_analyst")
def campaign_update_target_status(cid, org_id):
    """Memperbarui status tindak lanjut target dalam campaign."""
    target = CampaignTarget.query.filter_by(campaign_id=cid, organization_id=org_id).first_or_404()
    new_status = request.form.get("status", target.status)
    target.status = new_status
    target.notes = request.form.get("notes", target.notes)
    db.session.commit()
    log_activity("campaign_update_target_status", f"Target org #{org_id} di campaign #{cid} -> {new_status}")
    flash("Status target berhasil diperbarui.", "success")
    return redirect(url_for("marketing.campaign_detail", cid=cid))


@marketing_bp.route("/campaigns/<int:cid>/delete", methods=["POST"])
@login_required
@roles_required("marketing", "business_analyst")
def delete_campaign(cid):
    """Menghapus campaign dan targetnya."""
    campaign = Campaign.query.get_or_404(cid)
    camp_name = campaign.name
    db.session.delete(campaign)
    db.session.commit()
    log_activity("delete_campaign", f"Campaign #{cid} '{camp_name}' dihapus")
    flash(f"Campaign '{camp_name}' berhasil dihapus.", "success")
    return redirect(url_for("marketing.campaigns_index"))


@marketing_bp.route("/campaigns/<int:cid>/status", methods=["POST"])
@login_required
@roles_required("marketing", "business_analyst")
def update_campaign_status(cid):
    """Memperbarui status campaign (draft, ready, active, completed, closed)."""
    campaign = Campaign.query.get_or_404(cid)
    campaign.status = request.form.get("status", campaign.status)
    db.session.commit()
    log_activity("update_campaign_status", f"Campaign #{cid} status -> {campaign.status}")
    flash(f"Status campaign diperbarui menjadi '{campaign.status}'.", "success")
    return redirect(url_for("marketing.campaign_detail", cid=cid))


@marketing_bp.route("/campaigns/<int:cid>/export")
@marketing_bp.route("/campaigns/<int:cid>/export-targets")
@login_required
@roles_required("marketing", "business_analyst", "management")
def export_campaign(cid):
    """Mengekspor akun target dalam Campaign ke CSV dengan intelijen lengkap (F6.5 & Requirement #18)."""
    campaign = Campaign.query.get_or_404(cid)
    targets = CampaignTarget.query.filter_by(campaign_id=campaign.id).all()

    headers = [
        "Campaign Name", "Target Status", "Organization Name", "Organization Type",
        "Organization Subtype", "Sport", "Industry", "Product Fit", "AI Product Fit Score",
        "AI Product Fit Label", "AI Reasoning", "Priority Tier", "Opportunity Score",
        "Website", "Domain", "Instagram", "Facebook", "LinkedIn", "Phone", "Email",
        "City", "Province", "Events Participated", "Notes"
    ]

    rows = []
    if targets:
        for t in targets:
            org = t.organization
            if not org:
                continue
            socials = {}
            if org.social_json:
                try:
                    socials = json.loads(org.social_json) if isinstance(json.loads(org.social_json), dict) else {}
                except Exception:
                    pass

            events_str = "; ".join([p.event.name for p in org.participations if p.event]) if org.participations else ""

            rows.append([
                campaign.name,
                t.status,
                org.name,
                org.organization_type or "Perusahaan",
                org.organization_subtype or "",
                org.sport or "",
                org.industry or "",
                t.product_fit_snapshot or org.product_fit or campaign.product,
                org.ai_product_fit_score,
                org.ai_product_fit_label,
                org.ai_reasoning,
                org.priority_tier or "",
                t.opportunity_score_snapshot or org.opportunity_score or 0,
                org.website if org.website != "nan" else "",
                org.domain if org.domain != "nan" else "",
                socials.get("instagram", ""),
                socials.get("facebook", ""),
                socials.get("linkedin", ""),
                org.phone if org.phone != "nan" else "",
                org.email if org.email != "nan" else "",
                org.city if org.city != "nan" else "",
                org.province if org.province != "nan" else "",
                events_str,
                t.notes or ""
            ])
    else:
        # Fallback ke legacy prospects jika belum ada targets di tabel campaign_targets
        filt = json.loads(campaign.segment_filter_json) if campaign.segment_filter_json else {}
        query = Prospect.query
        if filt.get("industry"):
            query = query.filter(Prospect.industry == filt["industry"])
        if filt.get("region"):
            query = query.filter(Prospect.region == filt["region"])
        if filt.get("segment"):
            query = query.filter(Prospect.segment == filt["segment"])
        if filt.get("min_score"):
            query = query.filter(Prospect.score >= int(filt["min_score"]))
        prospects = query.all()
        for p in prospects:
            rows.append([
                campaign.name, "targeted", p.company_name, "Perusahaan", "", "", p.industry or "",
                campaign.product, p.score, "Potential", p.score_reason or "", "", p.score,
                p.website or "", "", "", "", "", p.contact_phone or "", p.contact_email or "",
                p.region or "", "", "", ""
            ])

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    for r in rows:
        writer.writerow(r)

    csv_data = output.getvalue()
    campaign.status = "exported"
    db.session.commit()
    log_activity("export_campaign", f"Export campaign #{cid} ({len(rows)} targets)")

    return Response(
        "\ufeff" + csv_data,
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment;filename=campaign_{cid}_{campaign.name.replace(' ', '_')}_targets.csv"}
    )
