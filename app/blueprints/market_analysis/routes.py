import json
from collections import Counter
from datetime import datetime
from flask import Blueprint, render_template, flash, redirect, url_for, request, abort, jsonify, send_file
from flask_login import login_required, current_user
from sqlalchemy import func

from app.extensions import db, csrf
from app.models import Prospect, MarketAnalysis, Organization
from app import ai_agent
from app.utils import log_activity, roles_required
from app.services.intelligence_analytics import (
    get_executive_overview,
    get_industry_analytics,
    get_regional_analytics,
    get_segmentation_analysis,
    get_product_fit_matrix,
    get_data_quality_and_freshness,
    get_white_space_clusters,
    search_master_organizations,
    get_all_matching_master_organizations,
    get_organization_detail,
)
from app.services.company_intelligence_excel import create_company_intelligence_workbook
from app.services.market_size_service import (
    get_market_size_and_share,
    simulate_expansion,
    get_financial_summary,
    get_syamanah_benchmark_report,
)

market_analysis_bp = Blueprint("market_analysis", __name__)


def _distribution(field):
    """Fungsi helper legacy untuk backward compatibility."""
    rows = db.session.query(getattr(Prospect, field), func.count(Prospect.id)) \
        .filter(getattr(Prospect, field).isnot(None)).group_by(getattr(Prospect, field)).all()
    return {k: v for k, v in rows if k}


def _company_explorer_filter_state():
    min_score_raw = request.args.get("min_score", "").strip()
    search_filters = {
        "q": request.args.get("q", "").strip(),
        "industry": request.args.get("industry", "").strip(),
        "province": request.args.get("province", "").strip(),
        "sport": request.args.get("sport", "").strip(),
        "priority_tier": request.args.get("priority_tier", "").strip(),
        "min_score": int(min_score_raw) if min_score_raw.isdigit() else None,
        "has_contact": request.args.get("has_contact") == "1",
        "missing_website": request.args.get("missing_website") == "1",
        "missing_social": request.args.get("missing_social") == "1",
        "missing_phone": request.args.get("missing_phone") == "1",
        "missing_email": request.args.get("missing_email") == "1",
        "missing_address": request.args.get("missing_address") == "1",
        "missing_employee_size": request.args.get("missing_employee_size") == "1",
        "review_status": request.args.get("review_status", "").strip(),
        "size_status": request.args.get("size_status", "").strip(),
    }
    display_filters = {
        "q": search_filters["q"],
        "industry": search_filters["industry"],
        "province": search_filters["province"],
        "sport": search_filters["sport"],
        "priority_tier": search_filters["priority_tier"],
        "min_score": min_score_raw,
        "has_contact": "1" if search_filters["has_contact"] else "",
        "missing_website": "1" if search_filters["missing_website"] else "",
        "missing_social": "1" if search_filters["missing_social"] else "",
        "missing_phone": "1" if search_filters["missing_phone"] else "",
        "missing_email": "1" if search_filters["missing_email"] else "",
        "missing_address": "1" if search_filters["missing_address"] else "",
        "missing_employee_size": "1" if search_filters["missing_employee_size"] else "",
        "review_status": search_filters["review_status"],
        "size_status": search_filters["size_status"],
    }
    return search_filters, display_filters


@market_analysis_bp.route("/")
@login_required
@roles_required("business_analyst", "management")
def index():
    """Dashboard Utama Business Analyst (BA) Intelligence Workspace.
    Menampilkan visualisasi analitik berbasis Master Organization Single Source of Truth:
    - Executive KPIs (Total Orgs, Avg Opportunity Score, High Priority %, Contactability %)
    - Industry Breakdown & Regional Concentration
    - Priority Segmentation & Organization Types
    - Product-Fit Apparel/Merchandise Demand Matrix
    - Data Quality & Freshness Visibility
    - White-Space Market Gap Analysis
    """
    # 1. Metrik Master Intelligence Baru (Phase 4)
    overview = get_executive_overview()
    industry_analytics = get_industry_analytics(limit=10)
    regional_analytics = get_regional_analytics(limit=10)
    segmentation = get_segmentation_analysis()
    product_fit_matrix = get_product_fit_matrix()
    data_quality = get_data_quality_and_freshness()
    white_space = get_white_space_clusters(limit=8)

    # 2. Compatibility metrics (untuk backward compatibility chart legacy jika dipanggil)
    industry_dist = {item["industry"]: item["count"] for item in industry_analytics}
    region_dist = {item["province"]: item["count"] for item in regional_analytics.get("by_province", [])}
    size_dist = _distribution("company_size")
    try:
        trend_rows = db.session.query(
            func.date_format(Prospect.created_at, "%Y-%m").label("ym"), func.count(Prospect.id)
        ).group_by("ym").order_by("ym").all()
        trend = {ym: c for ym, c in trend_rows}
    except Exception:
        trend = {}

    # 3. Pre-formatted Chart Data untuk Chart.js di template
    chart_data = {
        "ind_labels": [item["industry"] for item in industry_analytics],
        "ind_counts": [item["count"] for item in industry_analytics],
        "prov_labels": [item["province"] for item in regional_analytics.get("by_province", [])],
        "prov_counts": [item["count"] for item in regional_analytics.get("by_province", [])],
        "prod_labels": [item["product_key"] for item in product_fit_matrix],
        "prod_counts": [item["count"] for item in product_fit_matrix],
        "tier_labels": ["Tier A (HOT)", "Tier B (WARM)", "Tier C (POTENTIAL)", "Tier D (LOW)", "Lainnya"],
        "tier_data": [
            segmentation["tiers"]["A - HOT"],
            segmentation["tiers"]["B - WARM"],
            segmentation["tiers"]["C - POTENTIAL"],
            segmentation["tiers"]["D - LOW"],
            segmentation["tiers"].get("OTHER", 0)
        ]
    }

    return render_template(
        "market_analysis/index.html",
        overview=overview,
        industry_analytics=industry_analytics,
        regional_analytics=regional_analytics,
        segmentation=segmentation,
        product_fit_matrix=product_fit_matrix,
        data_quality=data_quality,
        white_space=white_space,
        chart_data=chart_data,
        # Legacy props:
        industry_dist=industry_dist,
        region_dist=region_dist,
        size_dist=size_dist,
        trend=trend,
    )


# ---------- Market Size (TAM/SAM/SOM) & Market Share Analytics ----------

@market_analysis_bp.route("/market-size")
@login_required
@roles_required("business_analyst", "management", "marketing")
def market_size():
    """Halaman Analisis Komprehensif Market Size (TAM, SAM, SOM) & Market Share Syamanah."""
    spend_raw = request.args.get("spend_per_person", "").strip()
    custom_spend = int(spend_raw) if spend_raw.isdigit() and int(spend_raw) > 0 else None
    
    data = get_market_size_and_share(custom_avg_spend=custom_spend)
    return render_template("market_analysis/market_size.html", **data)


@market_analysis_bp.route("/api/market-size-simulate", methods=["POST"])
@csrf.exempt
@login_required
@roles_required("business_analyst", "management", "marketing")
def api_simulate_market_size():
    """API endpoint interaktif untuk simulator skenario pertumbuhan pasar (What-If Analysis)."""
    payload = request.get_json() or {}
    tier_c_pct = float(payload.get("additional_tier_c_pct", 5.0))
    price_change_pct = float(payload.get("price_change_pct", 0.0))

    result = simulate_expansion(additional_tier_c_pct=tier_c_pct, price_change_pct=price_change_pct)
    return jsonify({
        "success": True,
        "data": result
    })


@market_analysis_bp.route("/market-size/report")
@login_required
@roles_required("business_analyst", "management", "marketing")
def market_size_report():
    """Halaman Laporan Eksekutif Market Size & Market Share Versi Syamanah (Format Presentasi & Siap Cetak PDF)."""
    data = get_syamanah_benchmark_report()
    return render_template("market_analysis/market_size_report.html", **data)


@market_analysis_bp.route("/market-size/export-excel")
@login_required
@roles_required("business_analyst", "management", "marketing")
def export_market_size_excel():
    """Ekspor Komprehensif Laporan Market Size, Market Share & Brand Leaderboard ke file Excel (.xlsx)."""
    from flask import send_file
    from app.services.market_size_excel import generate_market_size_excel_bytes

    excel_buffer = generate_market_size_excel_bytes()
    filename = "Laporan_Market_Size_Share_Syamanah_2026.xlsx"
    return send_file(
        excel_buffer,
        as_attachment=True,
        download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )



# ---------- Company Intelligence Explorer & Drill-Down (Phase 4) ----------

@market_analysis_bp.route("/explorer")
@market_analysis_bp.route("/organizations")
@login_required
@roles_required("business_analyst", "marketing", "management")
def explorer():
    """Pencarian dan penyaringan data Master Organization Intelligence."""
    search_filters, display_filters = _company_explorer_filter_state()
    page = request.args.get("page", 1, type=int)

    items, total_count, total_pages = search_master_organizations(
        **search_filters,
        page=page,
        per_page=25,
    )
    page = min(max(page, 1), total_pages)

    # Dapatkan daftar opsi industri dan provinsi untuk dropdown filter
    all_industries = [
        r[0] for r in db.session.query(Organization.industry)
        .filter(Organization.industry.isnot(None), Organization.industry != "")
        .distinct()
        .order_by(Organization.industry)
        .limit(100)
        .all()
    ]
    all_sports = ["Futsal", "Sepak Bola", "Basket", "Running", "Badminton", "Voli", "Sepeda", "Esports", "Tenis"]
    from app.utils import get_all_indonesia_provinces
    db_provinces = [
        r[0] for r in db.session.query(Organization.province)
        .filter(Organization.province.isnot(None), Organization.province != "", Organization.province != "nan")
        .distinct()
        .all()
    ]
    all_provinces = get_all_indonesia_provinces(db_provinces)

    category_summary = {
        "perusahaan": Organization.query.filter(Organization.organization_type.in_(["Perusahaan", "corporate", "company"])).count(),
        "komunitas": Organization.query.filter(Organization.organization_type.in_(["community", "Komunitas Olahraga", "sports_club"])).count(),
        "pendidikan": Organization.query.filter(Organization.organization_type.in_(["education", "school", "university"])).count(),
        "mahasiswa": Organization.query.filter(Organization.organization_type.in_(["student_organization", "student_org"])).count(),
        "tier_hot": Organization.query.filter(Organization.priority_tier == "A - HOT").count(),
        "tier_warm": Organization.query.filter(Organization.priority_tier == "B - WARM").count(),
        "size_actual": Organization.query.filter_by(size_status="actual").count(),
        "size_estimated": Organization.query.filter(db.or_(Organization.size_status.is_(None), Organization.size_status != "actual")).count(),
    }

    return render_template(
        "market_analysis/explorer.html",
        items=items,
        total_count=total_count,
        total_pages=total_pages,
        current_page=page,
        category_summary=category_summary,
        filters=display_filters,
        all_industries=all_industries,
        all_sports=all_sports,
        all_provinces=all_provinces,
    )


@market_analysis_bp.route("/explorer/export.xlsx")
@login_required
@roles_required("business_analyst", "marketing", "management")
def export_company_intelligence_excel():
    """Ekspor semua organisasi yang cocok dengan filter Company Intelligence Explorer."""
    search_filters, display_filters = _company_explorer_filter_state()
    organizations = get_all_matching_master_organizations(**search_filters)
    workbook = create_company_intelligence_workbook(organizations, filters=display_filters)
    log_activity(
        "export_company_intelligence_excel",
        f"Exported {len(organizations)} organizations from Company Intelligence Explorer",
    )
    return send_file(
        workbook,
        as_attachment=True,
        download_name=f"Company_Intelligence_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@market_analysis_bp.route("/organization/<int:org_id>")
@market_analysis_bp.route("/organizations/<int:org_id>")
@login_required
@roles_required("business_analyst", "marketing", "management")
def org_detail(org_id: int):
    """Melihat profil lengkap Company Intelligence dari entitas Master Organization."""
    detail = get_organization_detail(org_id)
    if not detail:
        flash("Entitas organisasi tidak ditemukan.", "danger")
        return redirect(url_for("market_analysis.explorer"))

    return render_template(
        "market_analysis/org_detail.html",
        org=detail["organization"],
        social=detail["social"],
        provenance=detail["provenance"],
        field_provenance=detail.get("field_provenance", {}),
        candidates=detail["candidates"],
        legacy_prospects_count=detail["legacy_prospects_count"],
        participations=detail.get("participations", []),
    )


@market_analysis_bp.route("/organization/<int:org_id>/update_size", methods=["POST"])
@login_required
@roles_required("business_analyst", "marketing", "management", "admin")
def update_org_size(org_id: int):
    """Update atau verifikasi manual jumlah anggota/karyawan organisasi menjadi Aktual."""
    import re
    from app.services.org_size_estimator import determine_tier_from_number

    org = db.session.get(Organization, org_id)
    if not org:
        flash("Entitas organisasi tidak ditemukan.", "danger")
        return redirect(url_for("market_analysis.explorer"))

    raw_members = request.form.get("estimated_members", "").strip()
    employee_size = request.form.get("employee_size", "").strip()
    size_status = request.form.get("size_status", "actual").strip()
    size_source = request.form.get("size_source", "manual_verified").strip()

    try:
        if raw_members:
            clean_num = int(re.sub(r"[^\d]", "", raw_members))
            org.estimated_members = clean_num
            if not employee_size:
                org.employee_size = determine_tier_from_number(clean_num)
        if employee_size:
            org.employee_size = employee_size

        org.size_status = size_status
        org.size_source = size_source
        db.session.commit()
        flash(f"Data skala & jumlah anggota/karyawan {org.name} berhasil diperbarui ({org.size_badge_label})!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Gagal memperbarui data: {e}", "danger")

    return redirect(url_for("market_analysis.org_detail", org_id=org.id))


# ---------- Rekomendasi Potensi Produk (AI Agent) ----------

@market_analysis_bp.route("/product-recommendation", methods=["POST"])
@login_required
@roles_required("business_analyst", "management", "marketing", "admin")
def product_recommendation():
    org_provinces = dict(
        db.session.query(Organization.province, func.count(Organization.id))
        .filter(Organization.province.isnot(None), Organization.province != "", Organization.province != "nan")
        .group_by(Organization.province)
        .order_by(func.count(Organization.id).desc())
        .limit(10)
        .all()
    )
    org_industries = dict(
        db.session.query(Organization.industry, func.count(Organization.id))
        .filter(Organization.industry.isnot(None), Organization.industry != "")
        .group_by(Organization.industry)
        .order_by(func.count(Organization.id).desc())
        .limit(10)
        .all()
    )
    org_types = dict(
        db.session.query(Organization.organization_type, func.count(Organization.id))
        .filter(Organization.organization_type.isnot(None), Organization.organization_type != "")
        .group_by(Organization.organization_type)
        .all()
    )
    summary = {
        "master_organizations_count": Organization.query.count(),
        "provinces_distribution": org_provinces,
        "industry_distribution": org_industries,
        "organization_types": org_types,
        "total_prospects": Prospect.query.count(),
    }
    try:
        result = ai_agent.recommend_products(summary)
        analysis = MarketAnalysis(
            analysis_type="product_recommendation",
            title="Rekomendasi Potensi Produk B2B Apparel & Merchandise",
            result_json=json.dumps(result),
            created_by=current_user.id,
        )
        db.session.add(analysis)
        db.session.commit()
        log_activity("product_recommendation", "Generate rekomendasi produk AI se-Indonesia")
        flash("Rekomendasi produk pasar se-Indonesia berhasil dibuat oleh AI.", "success")
    except Exception as e:
        flash(f"Gagal membuat rekomendasi: {e}", "danger")
    return redirect(url_for("market_analysis.history"))


@market_analysis_bp.route("/history")
@login_required
@roles_required("business_analyst")
def history():
    analyses = MarketAnalysis.query.order_by(MarketAnalysis.created_at.desc()).limit(50).all()
    parsed = []
    for a in analyses:
        try:
            parsed.append((a, json.loads(a.result_json) if a.result_json else {}))
        except Exception:
            parsed.append((a, {}))
    return render_template("market_analysis/history.html", analyses=parsed)


# ---------- Google Trends Intelligence (Fitur Tren Pasar Penelusuran) ----------

@market_analysis_bp.route("/google-trends")
@market_analysis_bp.route("/trends")
@login_required
@roles_required("business_analyst", "management", "marketing", "admin")
def google_trends():
    """Halaman Utama Google Trends Intelligence untuk Analisis Tren Permintaan Pasar & Penelusuran Konsumen/B2B."""
    from app.services.google_trends_service import (
        get_daily_trending_searches,
        get_keyword_trend_analysis,
        get_comparative_apparel_trends,
        APP_KEYWORDS_PRESETS,
    )

    q = request.args.get("q", "jersey printing").strip()
    geo = request.args.get("geo", "ID").strip()
    active_tab = request.args.get("tab", "keyword").strip()

    # 1. Analisis Tren Kata Kunci Terpilih
    keyword_trend = get_keyword_trend_analysis(query_keyword=q, geo=geo)

    # 2. Komparasi 4 Kategori Lini Produk Syamanah 12 Bulan Terakhir
    comparative_trends = get_comparative_apparel_trends()

    # 3. Live Daily Trending Searches di Indonesia dari Google Trends RSS
    daily_trends = get_daily_trending_searches(geo=geo)

    return render_template(
        "market_analysis/google_trends.html",
        q=q,
        geo=geo,
        active_tab=active_tab,
        keyword_trend=keyword_trend,
        comparative_trends=comparative_trends,
        daily_trends=daily_trends,
        presets=APP_KEYWORDS_PRESETS,
    )


@market_analysis_bp.route("/api/trends")
@login_required
@roles_required("business_analyst", "management", "marketing", "admin")
def api_google_trends():
    """API Asynchronous untuk pencarian data Google Trends dinamis tanpa reload halaman."""
    from app.services.google_trends_service import get_keyword_trend_analysis

    q = request.args.get("q", "jersey printing").strip()
    geo = request.args.get("geo", "ID").strip()

    data = get_keyword_trend_analysis(query_keyword=q, geo=geo)
    return jsonify({
        "success": True,
        "data": data
    })


@market_analysis_bp.route("/trends/save", methods=["POST"])
@login_required
@roles_required("business_analyst", "management", "marketing", "admin")
def save_google_trends():
    """Menyimpan snapshot hasil analisis Google Trends ke tabel database `market_analyses`."""
    from app.services.google_trends_service import get_keyword_trend_analysis, save_trend_analysis_snapshot

    q = request.form.get("q", "jersey printing").strip()
    geo = request.form.get("geo", "ID").strip()
    title = request.form.get("title", f"Tren Google: {q} ({geo})").strip()

    trend_data = get_keyword_trend_analysis(query_keyword=q, geo=geo)
    try:
        save_trend_analysis_snapshot(
            title=title,
            query=q,
            data=trend_data,
            user_id=current_user.id
        )
        log_activity("save_trend_snapshot", f"Menyimpan snapshot Google Trends untuk kata kunci: {q}")
        flash(f"Snapshot analisis tren '{q}' berhasil disimpan ke histori Market Analysis!", "success")
    except Exception as e:
        flash(f"Gagal menyimpan snapshot tren: {e}", "danger")

    return redirect(url_for("market_analysis.google_trends", q=q, geo=geo))

