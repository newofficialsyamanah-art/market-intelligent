"""Business Analyst Intelligence Analytics Service.

Menyediakan engine analitik untuk BA Workspace yang membaca langsung dari tabel
Master Organization Intelligence (`organizations`) sebagai Single Source of Truth.
Mendukung:
1. Market & Industry Analytics (Distribusi industri, skor rata-rata per sektor).
2. Company Segmentation (Priority Tiers A/B/C/D, tipe organisasi, ukuran).
3. Opportunity & Product-Fit Analysis (Kebutuhan produk seragam/apparel, skor kelayakan).
4. Data Quality & Freshness Visibility (Tingkat kelengkapan kontak, kebaruan data).
5. White-Space Analysis (Identifikasi kluster pasar bernilai tinggi yang belum tersentuh).
6. Filter & Drill-Down ke profil lengkap entitas master perusahaan.
"""

import json
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy import func, or_, and_, desc, asc

from app.extensions import db
from app.models import Organization, DuplicateCandidate, Prospect


def get_executive_overview() -> Dict[str, Any]:
    """Ringkasan eksekutif metrik Company & Market Intelligence untuk Business Analyst."""
    total_orgs = Organization.query.count()
    if total_orgs == 0:
        return {
            "total_orgs": 0,
            "avg_opportunity_score": 0.0,
            "high_priority_count": 0,
            "high_priority_pct": 0.0,
            "contactable_count": 0,
            "contactability_rate": 0.0,
            "pending_candidates_count": 0,
            "prospects_synced_count": 0,
        }

    # Rata-rata skor peluang
    avg_score = db.session.query(func.avg(Organization.opportunity_score)).scalar() or 0.0

    # Jumlah dan persentase prioritas tinggi (Tier A & B)
    high_priority_count = Organization.query.filter(
        or_(
            Organization.priority_tier.in_(["A - HOT", "Tier A", "B - WARM", "Tier B"]),
            Organization.opportunity_score >= 65
        )
    ).count()
    high_priority_pct = (high_priority_count / total_orgs) * 100.0

    # Contactability (memiliki minimal salah satu: domain/website, telepon, atau email)
    contactable_count = Organization.query.filter(
        or_(
            and_(Organization.phone.isnot(None), Organization.phone != "", Organization.phone != "-"),
            and_(Organization.email.isnot(None), Organization.email != "", Organization.email != "-"),
            and_(Organization.domain.isnot(None), Organization.domain != ""),
            and_(Organization.website.isnot(None), Organization.website != "", Organization.website != "-")
        )
    ).count()
    contactability_rate = (contactable_count / total_orgs) * 100.0

    # Jumlah review pending
    pending_candidates_count = DuplicateCandidate.query.filter_by(status="pending").count()

    # Total prospect di compatibility layer
    prospects_synced_count = Prospect.query.count()

    return {
        "total_orgs": total_orgs,
        "avg_opportunity_score": round(float(avg_score or 0), 1),
        "high_priority_count": high_priority_count,
        "high_priority_pct": round(high_priority_pct, 1),
        "contactable_count": contactable_count,
        "contactability_rate": round(contactability_rate, 1),
        "pending_candidates_count": pending_candidates_count,
        "prospects_synced_count": prospects_synced_count,
    }


def get_industry_analytics(limit: int = 10) -> List[Dict[str, Any]]:
    """Analisis distribusi sektor industri beserta rata-rata skor peluang per sektor."""
    rows = (
        db.session.query(
            Organization.industry,
            func.count(Organization.id).label("count"),
            func.avg(Organization.opportunity_score).label("avg_score")
        )
        .filter(Organization.industry.isnot(None), Organization.industry != "")
        .group_by(Organization.industry)
        .order_by(desc("count"))
        .limit(limit)
        .all()
    )

    results = []
    for ind, count, avg_score in rows:
        results.append({
            "industry": ind or "OTHER",
            "count": count,
            "avg_score": round(float(avg_score or 0.0), 1),
        })
    return results


def get_regional_analytics(limit: int = 10) -> Dict[str, Any]:
    """Analisis persebaran geografis berdasarkan Provinsi dan Kota/Kabupaten utama."""
    prov_rows = (
        db.session.query(
            Organization.province,
            func.count(Organization.id).label("count")
        )
        .filter(Organization.province.isnot(None), Organization.province != "", Organization.province != "nan")
        .group_by(Organization.province)
        .order_by(desc("count"))
        .limit(limit)
        .all()
    )

    city_rows = (
        db.session.query(
            Organization.city,
            func.count(Organization.id).label("count")
        )
        .filter(Organization.city.isnot(None), Organization.city != "", Organization.city != "nan")
        .group_by(Organization.city)
        .order_by(desc("count"))
        .limit(limit)
        .all()
    )

    return {
        "by_province": [{"province": p, "count": c} for p, c in prov_rows],
        "by_city": [{"city": c, "count": cnt} for c, cnt in city_rows],
    }


def get_segmentation_analysis() -> Dict[str, Any]:
    """Segmentasi perusahaan berdasarkan Priority Tier dan Tipe Organisasi."""
    tier_rows = (
        db.session.query(
            Organization.priority_tier,
            func.count(Organization.id).label("count")
        )
        .group_by(Organization.priority_tier)
        .all()
    )

    tiers_map = {"A - HOT": 0, "B - WARM": 0, "C - POTENTIAL": 0, "D - LOW": 0, "OTHER": 0}
    for tier, count in tier_rows:
        if tier in tiers_map:
            tiers_map[tier] += count
        elif tier in ("Tier A", "HOT"):
            tiers_map["A - HOT"] += count
        elif tier in ("Tier B", "WARM"):
            tiers_map["B - WARM"] += count
        elif tier in ("Tier C", "POTENTIAL"):
            tiers_map["C - POTENTIAL"] += count
        elif tier in ("Tier D", "LOW"):
            tiers_map["D - LOW"] += count
        else:
            tiers_map["OTHER"] += count

    type_rows = (
        db.session.query(
            Organization.organization_type,
            func.count(Organization.id).label("count")
        )
        .filter(Organization.organization_type.isnot(None))
        .group_by(Organization.organization_type)
        .order_by(desc("count"))
        .all()
    )

    return {
        "tiers": tiers_map,
        "types": [{"type": t or "Perusahaan", "count": c} for t, c in type_rows],
    }


def get_product_fit_matrix() -> List[Dict[str, Any]]:
    """Analisis peluang rekomendasi produk apparel / merchandise bagi BA."""
    # Produk-produk utama yang direkomendasikan sistem
    product_keywords = [
        ("Wearpack", "Wearpack Pabrik & Keselamatan"),
        ("Seragam", "Seragam Kerja Kantor / Pabrik"),
        ("Polo Shirt", "Polo Shirt Perusahaan"),
        ("Jaket", "Jaket Lapangan & Bomber"),
        ("Kaos", "Kaos Event & Promosi"),
    ]

    total_with_fit = Organization.query.filter(Organization.product_fit.isnot(None)).count()
    results = []

    for kw, label in product_keywords:
        c = Organization.query.filter(Organization.product_fit.ilike(f"%{kw}%")).count()
        avg_score = db.session.query(func.avg(Organization.opportunity_score)).filter(
            Organization.product_fit.ilike(f"%{kw}%")
        ).scalar() or 0.0

        pct = (c / total_with_fit * 100.0) if total_with_fit > 0 else 0.0
        results.append({
            "product_key": kw,
            "product_label": label,
            "count": c,
            "percentage": round(pct, 1),
            "avg_score": round(avg_score, 1),
        })

    return sorted(results, key=lambda x: x["count"], reverse=True)


def get_data_quality_and_freshness() -> Dict[str, Any]:
    """Metrik kualitas data, kelengkapan profil, dan visibilitas kesegaran data."""
    total = Organization.query.count()
    if total == 0:
        return {
            "phone_pct": 0, "email_pct": 0, "domain_pct": 0, "address_pct": 0,
            "fresh_30d": 0, "moderate_90d": 0, "older_90d": 0,
        }

    phone_cnt = Organization.query.filter(Organization.phone.isnot(None), Organization.phone != "", Organization.phone != "-").count()
    email_cnt = Organization.query.filter(Organization.email.isnot(None), Organization.email != "", Organization.email != "-").count()
    domain_cnt = Organization.query.filter(Organization.domain.isnot(None), Organization.domain != "").count()
    addr_cnt = Organization.query.filter(Organization.address.isnot(None), Organization.address != "", Organization.address != "nan").count()

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    t_30d = now - timedelta(days=30)
    t_90d = now - timedelta(days=90)

    fresh_30d = Organization.query.filter(Organization.data_freshness >= t_30d).count()
    moderate_90d = Organization.query.filter(Organization.data_freshness < t_30d, Organization.data_freshness >= t_90d).count()
    older_90d = Organization.query.filter(or_(Organization.data_freshness < t_90d, Organization.data_freshness.is_(None))).count()

    return {
        "phone_pct": round((phone_cnt / total) * 100, 1),
        "email_pct": round((email_cnt / total) * 100, 1),
        "domain_pct": round((domain_cnt / total) * 100, 1),
        "address_pct": round((addr_cnt / total) * 100, 1),
        "fresh_30d": fresh_30d,
        "moderate_90d": moderate_90d,
        "older_90d": older_90d,
        "fresh_pct": round((fresh_30d / total) * 100, 1),
    }


def get_white_space_clusters(limit: int = 10) -> List[Dict[str, Any]]:
    """White-Space Analysis: Mengidentifikasi kluster pasar dengan skor kelayakan tinggi
    yang belum tergarap (status discovered) berdasarkan provinsi & industri.
    """
    rows = (
        db.session.query(
            Organization.province,
            Organization.industry,
            func.count(Organization.id).label("cluster_size"),
            func.avg(Organization.opportunity_score).label("avg_score")
        )
        .filter(
            Organization.province.isnot(None),
            Organization.province != "",
            Organization.province != "nan",
            Organization.industry.isnot(None),
            Organization.industry != "",
            Organization.industry != "OTHER",
            Organization.verification_status == "discovered"
        )
        .group_by(Organization.province, Organization.industry)
        .having(func.avg(Organization.opportunity_score) >= 40)
        .order_by(desc("cluster_size"), desc("avg_score"))
        .limit(limit)
        .all()
    )

    clusters = []
    for prov, ind, count, avg_score in rows:
        clusters.append({
            "province": prov,
            "industry": ind,
            "count": count,
            "avg_score": round(avg_score or 0.0, 1),
            "potential_tag": "Tinggi" if (avg_score or 0) >= 60 else "Menengah",
        })
    return clusters


def search_master_organizations(
    q: str = "",
    industry: str = "",
    province: str = "",
    sport: str = "",
    priority_tier: str = "",
    min_score: Optional[int] = None,
    has_contact: bool = False,
    missing_website: bool = False,
    missing_social: bool = False,
    missing_phone: bool = False,
    missing_email: bool = False,
    missing_address: bool = False,
    missing_employee_size: bool = False,
    review_status: str = "",
    size_status: str = "",
    page: int = 1,
    per_page: int = 25
) -> Tuple[List[Organization], int, int]:
    """Pencarian dan penyaringan fleksibel untuk drill-down Company Intelligence.
    Mendukung filter kelengkapan data (missing fields) dan status review untuk BA.
    Mengembalikan (items, total_count, total_pages).
    """
    query = Organization.query

    if q:
        like_expr = f"%{q}%"
        query = query.filter(
            or_(
                Organization.name.ilike(like_expr),
                Organization.normalized_name.ilike(like_expr),
                Organization.domain.ilike(like_expr),
                Organization.city.ilike(like_expr),
                Organization.province.ilike(like_expr),
                Organization.address.ilike(like_expr),
                Organization.phone.ilike(like_expr),
                Organization.email.ilike(like_expr),
            )
        )

    if sport:
        sport_expr = f"%{sport}%"
        query = query.filter(
            or_(
                Organization.sport.ilike(sport_expr),
                Organization.organization_subtype.ilike(sport_expr),
                Organization.name.ilike(sport_expr),
            )
        )

    if industry:
        query = query.filter(Organization.industry.ilike(f"%{industry}%"))

    if province:
        query = query.filter(Organization.province.ilike(f"%{province}%"))

    if priority_tier:
        if priority_tier in ("A", "Tier A", "A - HOT"):
            query = query.filter(Organization.priority_tier.in_(["A - HOT", "Tier A"]))
        elif priority_tier in ("B", "Tier B", "B - WARM"):
            query = query.filter(Organization.priority_tier.in_(["B - WARM", "Tier B"]))
        elif priority_tier in ("C", "Tier C", "C - POTENTIAL"):
            query = query.filter(Organization.priority_tier.in_(["C - POTENTIAL", "Tier C"]))
        elif priority_tier in ("D", "Tier D", "D - LOW"):
            query = query.filter(Organization.priority_tier.in_(["D - LOW", "Tier D"]))
        else:
            query = query.filter(Organization.priority_tier == priority_tier)

    if min_score is not None:
        query = query.filter(Organization.opportunity_score >= min_score)

    if has_contact:
        query = query.filter(
            or_(
                and_(Organization.phone.isnot(None), Organization.phone != "", Organization.phone != "-"),
                and_(Organization.email.isnot(None), Organization.email != "", Organization.email != "-"),
                and_(Organization.domain.isnot(None), Organization.domain != "")
            )
        )

    # Filter Missing Fields untuk BA Intelligence Workflow
    if missing_website:
        query = query.filter(or_(Organization.website.is_(None), Organization.website == "", Organization.website == "-"))
    if missing_social:
        query = query.filter(or_(Organization.social_json.is_(None), Organization.social_json == "", Organization.social_json == "{}", Organization.social_json == "[]"))
    if missing_phone:
        query = query.filter(or_(Organization.phone.is_(None), Organization.phone == "", Organization.phone == "-"))
    if missing_email:
        query = query.filter(or_(Organization.email.is_(None), Organization.email == "", Organization.email == "-"))
    if missing_address:
        query = query.filter(or_(Organization.address.is_(None), Organization.address == "", Organization.address == "-"))
    if missing_employee_size:
        query = query.filter(or_(Organization.employee_size.is_(None), Organization.employee_size == ""))

    if review_status:
        if review_status == "pending":
            query = query.join(DuplicateCandidate, DuplicateCandidate.organization_id == Organization.id).filter(DuplicateCandidate.status == "pending")

    if size_status:
        if size_status == "actual":
            query = query.filter(Organization.size_status == "actual")
        elif size_status == "estimated":
            query = query.filter(or_(Organization.size_status.is_(None), Organization.size_status == "estimated"))

    total_count = query.count()
    total_pages = max(1, (total_count + per_page - 1) // per_page)
    offset = (page - 1) * per_page

    items = (
        query.order_by(Organization.opportunity_score.desc(), Organization.created_at.desc())
        .offset(offset)
        .limit(per_page)
        .all()
    )

    return items, total_count, total_pages


def get_organization_detail(org_id: int) -> Optional[Dict[str, Any]]:
    """Mengambil detail komprehensif profil entitas Company Intelligence."""
    org = db.session.get(Organization, org_id)
    if not org:
        return None

    provenance_list = []
    field_provenance = {}
    if org.provenance_json:
        try:
            parsed = json.loads(org.provenance_json)
            if isinstance(parsed, list):
                provenance_list = parsed
            elif isinstance(parsed, dict):
                provenance_list = parsed.get("merge_history", [])
                field_provenance = parsed.get("fields", {})
        except Exception:
            provenance_list = []

    # Ambil kandidat review yang terkait
    candidates = DuplicateCandidate.query.filter_by(organization_id=org.id).all()
    candidate_list = []
    for c in candidates:
        payload = {}
        if c.candidate_payload_json:
            try:
                payload = json.loads(c.candidate_payload_json)
            except Exception:
                pass
        candidate_list.append({
            "id": c.id,
            "candidate_name": c.candidate_name,
            "match_tier": c.match_tier,
            "confidence_score": c.confidence_score,
            "status": c.status,
            "payload": payload,
            "created_at": c.created_at,
        })

    # Prospek legacy yang terhubung
    legacy_count = org.prospects_legacy.count() if hasattr(org, "prospects_legacy") else 0

    # Parse media sosial terstruktur (Instagram, Facebook, LinkedIn)
    social_data = {"instagram": None, "facebook": None, "linkedin": None}
    if org.social_json:
        try:
            parsed_social = json.loads(org.social_json)
            if isinstance(parsed_social, dict):
                for k in ("instagram", "facebook", "linkedin"):
                    val = parsed_social.get(k) or parsed_social.get(k.capitalize())
                    if val and str(val).strip() and str(val).lower() not in ("nan", "none", "-", ""):
                        social_data[k] = str(val).strip()
            elif isinstance(parsed_social, list):
                for url in parsed_social:
                    u_str = str(url).strip()
                    u_low = u_str.lower()
                    if "instagram.com" in u_low and not social_data["instagram"]:
                        social_data["instagram"] = u_str
                    elif "facebook.com" in u_low and not social_data["facebook"]:
                        social_data["facebook"] = u_str
                    elif "linkedin.com" in u_low and not social_data["linkedin"]:
                        social_data["linkedin"] = u_str
        except Exception:
            pass

    # Event Participations (F6.3 Event-Based Intelligence)
    participations_list = []
    if hasattr(org, "participations") and org.participations:
        for p in org.participations:
            participations_list.append({
                "id": p.id,
                "role": p.role,
                "booth_number": p.booth_number,
                "notes": p.notes,
                "event_id": p.event.id if p.event else None,
                "event_name": p.event.name if p.event else "Unknown Event",
                "event_type": p.event.event_type if p.event else "-",
                "venue": p.event.venue if p.event else "-",
                "city": p.event.city if p.event else "-",
                "province": p.event.province if p.event else "-",
                "start_date": p.event.start_date if p.event else None,
                "end_date": p.event.end_date if p.event else None,
                "relevance_score": p.event.relevance_score if p.event else 0,
                "verification_status": p.event.verification_status if p.event else "discovered",
            })

    return {
        "organization": org,
        "social": social_data,
        "provenance": provenance_list,
        "field_provenance": field_provenance,
        "candidates": candidate_list,
        "legacy_prospects_count": legacy_count,
        "participations": participations_list,
    }
