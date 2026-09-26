"""Marketing Intelligence Service (Phase 6).

Menyediakan engine analisis target pasar, segmentasi preset B2B,
metrik peluang event-driven, dan export akun target berbasis Master Organizations (SSoT).
BUKAN CRM: Tidak ada sales pipeline, deals, stages, atau tracking aktivitas sales.
"""

import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy import func, or_, and_

from app.extensions import db
from app.models import Organization, Event, EventParticipant

logger = logging.getLogger(__name__)

# Kamus Segmentasi Preset B2B (F6.2 Minimal Support: Corporate, Manufacturing, Government, University, School, Association, Event Organizer, Textile, Garment, Fashion, Industrial)
SEGMENT_PRESETS = {
    # 1. Corporate
    "corporate": {
        "key": "corporate",
        "title": "Corporate & Enterprise",
        "description": "Perusahaan skala menengah-besar, jasa keuangan, konsultan, teknologi, dan korporat yang membutuhkan kemeja formal, batik seragam, dan polo shirt kantor.",
        "icon": "bi-briefcase",
        "color": "primary"
    },
    # 2. Manufacturing
    "manufacturing": {
        "key": "manufacturing",
        "title": "Manufacturing Sector",
        "description": "Pabrik dan industri pengolahan dengan kebutuhan pakaian kerja harian, seragam lini produksi, dan wearpack.",
        "icon": "bi-gear-wide-connected",
        "color": "secondary"
    },
    # 3. Government
    "government": {
        "key": "government",
        "title": "Government & Public Institutions",
        "description": "Instansi pemerintah, dinas kementerian, BUMN, dan lembaga publik dengan kebutuhan seragam dinas harian (PDH) dan seragam dinas lapangan (PDL).",
        "icon": "bi-bank",
        "color": "success"
    },
    # 4. University
    "university": {
        "key": "university",
        "title": "University & Higher Education",
        "description": "Perguruan tinggi, universitas, institut, dan politeknik dengan kebutuhan jas almamater, seragam panitia ospek/kegiatan, dan merchandise kampus.",
        "icon": "bi-mortarboard",
        "color": "info"
    },
    # 5. School
    "school": {
        "key": "school",
        "title": "School & Vocational Education",
        "description": "Sekolah menengah, kejuruan (SMK), dan yayasan pendidikan dengan kebutuhan seragam sekolah, wearpack bengkel/praktik, dan seragam olahraga.",
        "icon": "bi-book",
        "color": "warning"
    },
    # 6. Association
    "association": {
        "key": "association",
        "title": "Industry Associations & Chambers",
        "description": "Asosiasi industri, federasi bisnis, perhimpunan profesi, dan kamar dagang dengan kebutuhan polo shirt anggota, kemeja asosiasi, dan merchandise kongres.",
        "icon": "bi-diagram-3",
        "color": "dark"
    },
    # 7. Event Organizer
    "event_organizer": {
        "key": "event_organizer",
        "title": "Event Organizers & Exhibition Agencies",
        "description": "Penyelenggara pameran, event organizer (EO), dan promotor expo dengan kebutuhan merchandise massal, kaos panitia, lanyard, dan goodie bag.",
        "icon": "bi-calendar-event",
        "color": "danger"
    },
    # 8. Textile
    "textile": {
        "key": "textile",
        "title": "Textile Supply Chain",
        "description": "Pabrik tekstil, produsen kain, dan industri pemintalan benang bahan baku seragam.",
        "icon": "bi-threads",
        "color": "primary"
    },
    # 9. Garment
    "garment": {
        "key": "garment",
        "title": "Garment & Apparel Manufacturers",
        "description": "Pabrik garmen, konveksi skala besar, dan produsen pakaian jadi.",
        "icon": "bi-scissors",
        "color": "info"
    },
    # 10. Fashion
    "fashion": {
        "key": "fashion",
        "title": "Fashion Brands & Retailers",
        "description": "Brand busana, produsen fashion muslim, dan ritel pakaian jadi.",
        "icon": "bi-gem",
        "color": "success"
    },
    # 11. Industrial
    "industrial": {
        "key": "industrial",
        "title": "Industrial & Heavy Equipment",
        "description": "Sektor kimia, plastik, otomotif, konstruksi, dan industri berat dengan kebutuhan wearpack K3 tahan api/noda dan rompi safety lapangan.",
        "icon": "bi-tools",
        "color": "warning"
    },
    # Additional Strategic Presets
    "corporate_uniform": {
        "key": "corporate_uniform",
        "title": "Corporate Apparel & Executive Uniform",
        "description": "Perusahaan skala menengah-besar yang membutuhkan kemeja formal, batik seragam, dan polo shirt kantor.",
        "icon": "bi-briefcase",
        "color": "primary"
    },
    "event_merchandise": {
        "key": "event_merchandise",
        "title": "Event & Exhibition Merchandise",
        "description": "Organisasi yang aktif mengikuti atau menyelenggarakan expo, pameran industri, dan konferensi bisnis dengan kebutuhan goodie bag, lanyard, kaos event, dan souvenir.",
        "icon": "bi-calendar-event",
        "color": "info"
    },
    "industrial_safety": {
        "key": "industrial_safety",
        "title": "Industrial & Safety Wear (Wearpack / Rompi)",
        "description": "Sektor manufaktur, plastik, kimia, konstruksi, dan industri berat dengan kebutuhan seragam lapangan tahan api/noda, wearpack K3, dan rompi safety.",
        "icon": "bi-gear-wide-connected",
        "color": "warning"
    },
    "hospitality_service": {
        "key": "hospitality_service",
        "title": "Hospitality & Service Uniform",
        "description": "Sektor kuliner, F&B, hotel, retail, logistik, dan pergudangan dengan kebutuhan seragam operasional, apron, polo shirt kasir/kurir, dan topi.",
        "icon": "bi-shop",
        "color": "success"
    },
    "hot_targets": {
        "key": "hot_targets",
        "title": "High Opportunity Accounts (Tier A - HOT)",
        "description": "Akun target prioritas tertinggi dengan opportunity score >= 80 yang memiliki kesesuaian produk maksimal dan profil kontak terverifikasi.",
        "icon": "bi-fire",
        "color": "danger"
    },
    "contactable_ready": {
        "key": "contactable_ready",
        "title": "Contactable Ready-to-Engage",
        "description": "Akun yang telah memiliki jalur komunikasi langsung (email korporat aktif atau nomor telepon valid) dan website resmi siap untuk program marketing.",
        "icon": "bi-telephone-inbound",
        "color": "secondary"
    }
}


class MarketingIntelligenceService:
    """Service modular untuk Marketing Intelligence Workspace (Phase 6)."""

    @classmethod
    def get_marketing_dashboard_metrics(cls) -> Dict[str, Any]:
        """Menghitung metrik agregat pasar, distribusi tier prioritas, demand produk,
        dan peluang berbasis partisipasi event (F6.4).
        """
        total_orgs = Organization.query.count()
        total_events = Event.query.count()

        # 1. Priority Tiers Breakdown
        tier_counts = dict(
            db.session.query(Organization.priority_tier, func.count(Organization.id))
            .group_by(Organization.priority_tier).all()
        )
        tier_a = tier_counts.get("A - HOT", 0)
        tier_b = tier_counts.get("B - WARM", 0)
        tier_c = tier_counts.get("C - POTENTIAL", 0)
        tier_d = tier_counts.get("D - LOW", 0)
        tier_other = total_orgs - (tier_a + tier_b + tier_c + tier_d)

        # 2. Priority Organizations & High Opportunity Accounts (Score >= 80)
        high_opp_count = Organization.query.filter(Organization.opportunity_score >= 80).count()
        priority_orgs_count = tier_a + tier_b

        # 3. Contactability Metrics
        with_website = Organization.query.filter(
            Organization.website.isnot(None), Organization.website != "", Organization.website != "nan"
        ).count()

        with_phone = Organization.query.filter(
            Organization.phone.isnot(None), Organization.phone != "", Organization.phone != "nan"
        ).count()

        with_email = Organization.query.filter(
            Organization.email.isnot(None), Organization.email != "", Organization.email != "nan"
        ).count()

        with_social = Organization.query.filter(
            Organization.social_json.isnot(None),
            Organization.social_json != "",
            Organization.social_json != "{}",
            Organization.social_json != "nan"
        ).count()

        # Enriched organizations
        enriched_orgs = Organization.query.filter(
            or_(
                and_(Organization.website.isnot(None), Organization.website != "", Organization.website != "nan"),
                and_(Organization.domain.isnot(None), Organization.domain != "", Organization.domain != "nan"),
                and_(Organization.phone.isnot(None), Organization.phone != "", Organization.phone != "nan"),
                and_(Organization.email.isnot(None), Organization.email != "", Organization.email != "nan")
            )
        ).count()
        enrichment_coverage = round((enriched_orgs / total_orgs * 100), 1) if total_orgs > 0 else 0.0

        # Accounts with direct contact (email OR phone)
        contactable_accounts = Organization.query.filter(
            or_(
                and_(Organization.email.isnot(None), Organization.email != "", Organization.email != "nan"),
                and_(Organization.phone.isnot(None), Organization.phone != "", Organization.phone != "nan")
            )
        ).count()

        contactability_pct = round((contactable_accounts / total_orgs * 100), 1) if total_orgs > 0 else 0.0

        # 4. Event-Driven Opportunities & Coverage
        participating_org_ids = db.session.query(EventParticipant.organization_id).distinct().all()
        event_driven_orgs_count = len(participating_org_ids)
        event_coverage = round((event_driven_orgs_count / total_orgs * 100), 2) if total_orgs > 0 else 0.0

        # Upcoming & High Relevance Events
        upcoming_events_count = Event.query.filter(Event.status == "upcoming").count()
        high_rel_events_count = Event.query.filter(Event.relevance_score >= 80).count()

        # Top Participating Organizations
        top_event_orgs_raw = db.session.query(
            Organization.id,
            Organization.name,
            Organization.industry,
            Organization.priority_tier,
            func.count(EventParticipant.id).label("events_count")
        ).join(EventParticipant, Organization.id == EventParticipant.organization_id) \
         .group_by(Organization.id, Organization.name, Organization.industry, Organization.priority_tier) \
         .order_by(func.count(EventParticipant.id).desc()) \
         .limit(5).all()

        top_event_orgs = [
            {
                "id": r[0],
                "name": r[1],
                "industry": r[2] or "Umum",
                "priority_tier": r[3] or "C - POTENTIAL",
                "events_count": r[4]
            }
            for r in top_event_orgs_raw
        ]

        # 5. Product-Fit Demand Breakdown
        prod_counts = dict(
            db.session.query(Organization.product_fit, func.count(Organization.id))
            .filter(Organization.product_fit.isnot(None), Organization.product_fit != "")
            .group_by(Organization.product_fit)
            .order_by(func.count(Organization.id).desc())
            .limit(6).all()
        )

        # 6. Industry & Geographic Distribution
        ind_rows = db.session.query(Organization.industry, func.count(Organization.id)) \
            .filter(Organization.industry.isnot(None), Organization.industry != "", Organization.industry != "nan") \
            .group_by(Organization.industry).order_by(func.count(Organization.id).desc()).limit(8).all()
        industry_distribution = {r[0]: r[1] for r in ind_rows}

        geo_rows = db.session.query(Organization.province, func.count(Organization.id)) \
            .filter(Organization.province.isnot(None), Organization.province != "", Organization.province != "nan") \
            .group_by(Organization.province).order_by(func.count(Organization.id).desc()).limit(8).all()
        geographic_distribution = {r[0]: r[1] for r in geo_rows}

        return {
            "total_organizations": total_orgs,
            "total_events": total_events,
            "enriched_organizations": enriched_orgs,
            "enrichment_coverage": enrichment_coverage,
            "contactable_organizations": contactable_accounts,
            "priority_organizations": priority_orgs_count,
            "event_linked_organizations": event_driven_orgs_count,
            "event_coverage": event_coverage,
            "upcoming_events": upcoming_events_count,
            "high_relevance_events": high_rel_events_count,
            "high_opportunity_count": high_opp_count,
            "tier_distribution": {
                "A": tier_a,
                "B": tier_b,
                "C": tier_c,
                "D": tier_d,
                "Other": tier_other
            },
            "contactability": {
                "contactable_accounts": contactable_accounts,
                "contactability_pct": contactability_pct,
                "with_website": with_website,
                "with_phone": with_phone,
                "with_email": with_email,
                "with_social": with_social,
            },
            "event_driven": {
                "participating_orgs_count": event_driven_orgs_count,
                "top_participating_orgs": top_event_orgs,
            },
            "product_fit_distribution": prod_counts,
            "industry_distribution": industry_distribution,
            "geographic_distribution": geographic_distribution,
        }

    @classmethod
    def search_marketing_targets(
        cls,
        q: str = "",
        priority_tier: str = "",
        industry: str = "",
        province: str = "",
        city: str = "",
        product_fit: str = "",
        organization_type: str = "",
        organization_subtype: str = "",
        sport: str = "",
        employee_size: str = "",
        event_relevance: str = "",
        has_event: bool = False,
        event_id: Optional[int] = None,
        has_email: bool = False,
        has_phone: bool = False,
        has_website: bool = False,
        has_social: bool = False,
        has_instagram: bool = False,
        has_tiktok: bool = False,
        has_facebook: bool = False,
        has_linkedin: bool = False,
        min_score: Optional[int] = None,
        page: int = 1,
        per_page: int = 25
    ) -> Tuple[List[Dict[str, Any]], int, int]:
        """Pencarian target akun komprehensif berdasarkan filter multi-dimensi (F6.1)."""
        query = db.session.query(Organization)

        if q:
            query = query.filter(
                or_(
                    Organization.name.like(f"%{q}%"),
                    Organization.domain.like(f"%{q}%"),
                    Organization.city.like(f"%{q}%"),
                    Organization.industry.like(f"%{q}%"),
                    Organization.sport.like(f"%{q}%")
                )
            )

        if priority_tier:
            query = query.filter(Organization.priority_tier == priority_tier)

        if industry:
            query = query.filter(Organization.industry == industry)

        if province:
            query = query.filter(Organization.province == province)

        if city:
            query = query.filter(Organization.city == city)

        if organization_type:
            query = query.filter(Organization.organization_type == organization_type)

        if organization_subtype:
            query = query.filter(Organization.organization_subtype == organization_subtype)

        if sport:
            query = query.filter(Organization.sport.like(f"%{sport}%"))

        if employee_size:
            query = query.filter(Organization.employee_size.like(f"%{employee_size}%"))

        if product_fit:
            query = query.filter(Organization.product_fit.like(f"%{product_fit}%"))

        if min_score is not None:
            query = query.filter(Organization.opportunity_score >= min_score)

        if has_email:
            query = query.filter(Organization.email.isnot(None), Organization.email != "", Organization.email != "nan")

        if has_phone:
            query = query.filter(Organization.phone.isnot(None), Organization.phone != "", Organization.phone != "nan")

        if has_website:
            query = query.filter(Organization.website.isnot(None), Organization.website != "", Organization.website != "nan")

        if has_social:
            query = query.filter(
                Organization.social_json.isnot(None),
                Organization.social_json != "",
                Organization.social_json != "{}",
                Organization.social_json != "nan"
            )

        if has_instagram:
            query = query.filter(Organization.social_json.like("%instagram%"))

        if has_tiktok:
            query = query.filter(Organization.social_json.like("%tiktok%"))

        if has_facebook:
            query = query.filter(Organization.social_json.like("%facebook%"))

        if has_linkedin:
            query = query.filter(Organization.social_json.like("%linkedin%"))

        if event_relevance:
            query = query.join(EventParticipant, Organization.id == EventParticipant.organization_id) \
                         .join(Event, EventParticipant.event_id == Event.id)
            if event_relevance == "HIGH":
                query = query.filter(Event.relevance_score >= 80)
            elif event_relevance == "MEDIUM":
                query = query.filter(Event.relevance_score >= 50, Event.relevance_score < 80)
            elif event_relevance == "LOW":
                query = query.filter(Event.relevance_score < 50)
            query = query.distinct()
        elif has_event or event_id:
            query = query.join(EventParticipant, Organization.id == EventParticipant.organization_id)
            if event_id:
                query = query.filter(EventParticipant.event_id == event_id)
            query = query.distinct()

        total_count = query.count()
        total_pages = (total_count + per_page - 1) // per_page if total_count > 0 else 1

        orgs = query.order_by(
            Organization.opportunity_score.desc(),
            Organization.id.asc()
        ).offset((page - 1) * per_page).limit(per_page).all()

        results = []
        for org in orgs:
            socials = {}
            if org.social_json:
                try:
                    socials = json.loads(org.social_json) if isinstance(json.loads(org.social_json), dict) else {}
                except Exception:
                    socials = {}

            # Cek partisipasi event
            part_count = len(org.participations)
            high_rel_events = sum(1 for p in org.participations if p.event and (p.event.relevance_score or 0) >= 80)

            results.append({
                "id": org.id,
                "name": org.name,
                "organization_type": org.organization_type or "Perusahaan",
                "organization_subtype": org.organization_subtype,
                "sport": org.sport,
                "industry": org.industry,
                "product_fit": org.product_fit,
                "priority_tier": org.priority_tier,
                "opportunity_score": org.opportunity_score,
                "ai_product_fit_score": org.ai_product_fit_score,
                "ai_product_fit_label": org.ai_product_fit_label,
                "ai_reasoning": org.ai_reasoning,
                "ai_evidence": org.ai_evidence,
                "phone": org.phone if org.phone != "nan" else None,
                "email": org.email if org.email != "nan" else None,
                "website": org.website if org.website != "nan" else None,
                "domain": org.domain if org.domain != "nan" else None,
                "city": org.city if org.city != "nan" else None,
                "province": org.province if org.province != "nan" else None,
                "employee_size": org.employee_size if org.employee_size != "nan" else None,
                "socials": socials,
                "events_count": part_count,
                "high_relevance_events_count": high_rel_events,
            })

        return results, total_count, total_pages

    @classmethod
    def get_segment_query(cls, preset_key: str):
        """Membuat query SQLAlchemy untuk 11 segmen B2B utama dan preset marketing (F6.2)."""
        query = db.session.query(Organization)

        if preset_key in ("corporate", "corporate_uniform"):
            query = query.filter(
                or_(
                    Organization.organization_type == "Perusahaan",
                    Organization.product_fit.like("%Seragam Kantor%"),
                    Organization.product_fit.like("%Korporat%"),
                    Organization.industry.in_([
                        "Jasa Keuangan", "Teknologi Informasi", "Telekomunikasi",
                        "Perbankan", "Konsultan", "Asuransi", "Holding"
                    ])
                )
            )
        elif preset_key == "manufacturing":
            query = query.filter(
                or_(
                    Organization.industry.like("%MANUFACTURING%"),
                    Organization.organization_type == "Manufaktur",
                    Organization.product_fit.like("%Pabrik%"),
                    Organization.product_fit.like("%Manufaktur%")
                )
            )
        elif preset_key == "government":
            query = query.filter(
                or_(
                    Organization.name.like("%dinas%"),
                    Organization.name.like("%kementerian%"),
                    Organization.name.like("%badan %"),
                    Organization.name.like("%pemerintah%"),
                    Organization.name.like("%bumn%"),
                    Organization.name.like("%pemda%")
                )
            )
        elif preset_key == "university":
            query = query.filter(
                or_(
                    Organization.name.like("%universitas%"),
                    Organization.name.like("%univ%"),
                    Organization.name.like("%institut%"),
                    Organization.name.like("%politeknik%"),
                    Organization.name.like("%akademi%"),
                    Organization.name.like("%perguruan tinggi%")
                )
            )
        elif preset_key == "school":
            query = query.filter(
                or_(
                    Organization.name.like("%sekolah%"),
                    Organization.name.like("%smk%"),
                    Organization.name.like("%sma%"),
                    Organization.name.like("%yayasan%"),
                    Organization.name.like("%pesantren%")
                )
            )
        elif preset_key == "association":
            query = query.filter(
                or_(
                    Organization.name.like("%asosiasi%"),
                    Organization.name.like("%perkumpulan%"),
                    Organization.name.like("%ikatan%"),
                    Organization.name.like("%gabungan%"),
                    Organization.name.like("%federasi%"),
                    Organization.name.like("%kadin%")
                )
            )
        elif preset_key == "event_organizer":
            query = query.filter(
                or_(
                    Organization.name.like("%expo%"),
                    Organization.name.like("%organizer%"),
                    Organization.name.like("%pameran%"),
                    Organization.id.in_(db.session.query(EventParticipant.organization_id).filter_by(role="organizer"))
                )
            )
        elif preset_key == "textile":
            query = query.filter(
                or_(
                    Organization.industry.like("%TEXTILE%"),
                    Organization.name.like("%tekstil%"),
                    Organization.name.like("%textile%"),
                    Organization.product_fit.like("%Tekstil%")
                )
            )
        elif preset_key == "garment":
            query = query.filter(
                or_(
                    Organization.industry.like("%GARMENT%"),
                    Organization.name.like("%garmen%"),
                    Organization.name.like("%garment%"),
                    Organization.name.like("%konveksi%"),
                    Organization.product_fit.like("%Garmen%")
                )
            )
        elif preset_key == "fashion":
            query = query.filter(
                or_(
                    Organization.industry.like("%FASHION%"),
                    Organization.name.like("%fashion%"),
                    Organization.name.like("%busana%"),
                    Organization.product_fit.like("%Fashion%")
                )
            )
        elif preset_key in ("industrial", "industrial_safety"):
            query = query.filter(
                or_(
                    Organization.industry.in_(["MANUFACTURING", "CHEMICAL", "AUTOMOTIVE", "CONSTRUCTION", "ELECTRONIC"]),
                    Organization.product_fit.like("%Wearpack%"),
                    Organization.product_fit.like("%Pabrik%"),
                    Organization.product_fit.like("%Safety%"),
                    Organization.industry.like("%Manufaktur%"),
                    Organization.industry.like("%Plastik%"),
                    Organization.industry.like("%Kimia%"),
                    Organization.industry.like("%Konstruksi%")
                )
            )
        elif preset_key == "event_merchandise":
            query = query.join(EventParticipant, Organization.id == EventParticipant.organization_id).distinct()
        elif preset_key == "hospitality_service":
            query = query.filter(
                or_(
                    Organization.product_fit.like("%Polo%"),
                    Organization.product_fit.like("%Kaos%"),
                    Organization.industry.like("%Food%"),
                    Organization.industry.like("%Kuliner%"),
                    Organization.industry.like("%Hotel%"),
                    Organization.industry.like("%Restoran%"),
                    Organization.industry.like("%Logistik%"),
                    Organization.industry.like("%Retail%")
                )
            )
        elif preset_key == "hot_targets":
            query = query.filter(
                or_(
                    Organization.priority_tier == "A - HOT",
                    Organization.opportunity_score >= 80
                )
            )
        elif preset_key == "contactable_ready":
            query = query.filter(
                or_(
                    and_(Organization.email.isnot(None), Organization.email != "", Organization.email != "nan"),
                    and_(Organization.phone.isnot(None), Organization.phone != "", Organization.phone != "nan")
                ),
                Organization.website.isnot(None), Organization.website != "", Organization.website != "nan"
            )

        return query

    @classmethod
    def get_segment_presets_overview(cls) -> List[Dict[str, Any]]:
        """Mengambil rangkuman seluruh segment preset beserta jumlah akun target masing-masing."""
        presets = []
        for key, info in SEGMENT_PRESETS.items():
            q = cls.get_segment_query(key)
            count = q.count()
            presets.append({
                **info,
                "count": count
            })
        return presets

    @classmethod
    def get_segment_drilldown(cls, preset_key: str, page: int = 1, per_page: int = 25) -> Tuple[List[Dict[str, Any]], int, int, Dict[str, Any]]:
        """Melihat daftar akun pada segment preset tertentu secara mendalam."""
        info = SEGMENT_PRESETS.get(preset_key, SEGMENT_PRESETS["hot_targets"])
        query = cls.get_segment_query(preset_key)

        total_count = query.count()
        total_pages = (total_count + per_page - 1) // per_page if total_count > 0 else 1

        orgs = query.order_by(
            Organization.opportunity_score.desc(),
            Organization.id.asc()
        ).offset((page - 1) * per_page).limit(per_page).all()

        results = []
        for org in orgs:
            socials = {}
            if org.social_json:
                try:
                    socials = json.loads(org.social_json) if isinstance(json.loads(org.social_json), dict) else {}
                except Exception:
                    socials = {}

            results.append({
                "id": org.id,
                "name": org.name,
                "industry": org.industry,
                "product_fit": org.product_fit,
                "priority_tier": org.priority_tier,
                "opportunity_score": org.opportunity_score,
                "phone": org.phone if org.phone != "nan" else None,
                "email": org.email if org.email != "nan" else None,
                "website": org.website if org.website != "nan" else None,
                "domain": org.domain if org.domain != "nan" else None,
                "city": org.city if org.city != "nan" else None,
                "province": org.province if org.province != "nan" else None,
                "socials": socials,
                "events_count": len(org.participations),
            })

        return results, total_count, total_pages, info
