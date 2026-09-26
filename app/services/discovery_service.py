"""Indonesia Market & Organization Intelligence Discovery Service.

Mengimplementasikan Discovery Universe komprehensif untuk:
A. PENDIDIKAN (Education Discovery):
   - PAUD, TK, SD, MI, SMP, MTs, SMA, MA, SMK, Pesantren
   - Perguruan Tinggi: Universitas, Institut, Politeknik, Sekolah Tinggi, Akademi
B. ORGANISASI MAHASISWA:
   - BEM, DPM, HIMA (Himpunan Mahasiswa), UKM (Unit Kegiatan Mahasiswa Olahraga & Seni)
C. KOMUNITAS:
   - Olahraga: Futsal, Sepak Bola, Basket, Voli, Running, Cycling, Esports, Badminton
   - Hobi, Profesi, Sosial, Pemuda
D. ORGANISASI:
   - Perusahaan, Asosiasi, Yayasan, NGO, Ormas, Event Organizer

Setiap hasil penemuan mengikuti alur arsitektur inti:
SOURCE -> DISCOVERY -> PROSPECT -> IDENTITY RESOLUTION -> MASTER ORGANIZATION
Dengan rekaman provenance lengkap: source, source_url, source_type, discovered_at, confidence, raw_reference.
"""

import re
import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
from urllib.parse import urlparse

from app.extensions import db
from app.models import Organization, Prospect, DiscoverySource, utc_now
from app.services.dedup_engine import (
    IdentityResolutionEngine,
    safe_merge_organization,
    create_organization_from_source,
    normalize_company_name,
    extract_domain,
)
from app.services.social_connector import SocialConnectorService

logger = logging.getLogger(__name__)

# Direktori & Dataset Resmi Terverifikasi Pendidikan Indonesia (Sample Seed Directories)
VERIFIED_INDONESIA_EDUCATION_SEEDS = [
    # Perguruan Tinggi Negeri & Swasta Terkemuka
    {"name": "Institut Teknologi Bandung", "subtype": "Institut", "province": "Jawa Barat", "city": "Bandung", "website": "https://www.itb.ac.id", "domain": "itb.ac.id", "source": "direktori_dikti"},
    {"name": "Universitas Indonesia", "subtype": "Universitas", "province": "DKI Jakarta", "city": "Depok", "website": "https://www.ui.ac.id", "domain": "ui.ac.id", "source": "direktori_dikti"},
    {"name": "Universitas Gadjah Mada", "subtype": "Universitas", "province": "DI Yogyakarta", "city": "Sleman", "website": "https://www.ugm.ac.id", "domain": "ugm.ac.id", "source": "direktori_dikti"},
    {"name": "Institut Pertanian Bogor", "subtype": "Institut", "province": "Jawa Barat", "city": "Bogor", "website": "https://www.ipb.ac.id", "domain": "ipb.ac.id", "source": "direktori_dikti"},
    {"name": "Universitas Airlangga", "subtype": "Universitas", "province": "Jawa Timur", "city": "Surabaya", "website": "https://www.unair.ac.id", "domain": "unair.ac.id", "source": "direktori_dikti"},
    {"name": "Institut Teknologi Sepuluh Nopember", "subtype": "Institut", "province": "Jawa Timur", "city": "Surabaya", "website": "https://www.its.ac.id", "domain": "its.ac.id", "source": "direktori_dikti"},
    {"name": "Universitas Diponegoro", "subtype": "Universitas", "province": "Jawa Tengah", "city": "Semarang", "website": "https://www.undip.ac.id", "domain": "undip.ac.id", "source": "direktori_dikti"},
    {"name": "Universitas Padjadjaran", "subtype": "Universitas", "province": "Jawa Barat", "city": "Sumedang", "website": "https://www.unpad.ac.id", "domain": "unpad.ac.id", "source": "direktori_dikti"},
    {"name": "Universitas Brawijaya", "subtype": "Universitas", "province": "Jawa Timur", "city": "Malang", "website": "https://www.ub.ac.id", "domain": "ub.ac.id", "source": "direktori_dikti"},
    {"name": "Universitas Sebelas Maret", "subtype": "Universitas", "province": "Jawa Tengah", "city": "Surakarta", "website": "https://www.uns.ac.id", "domain": "uns.ac.id", "source": "direktori_dikti"},
    {"name": "Universitas Hasanuddin", "subtype": "Universitas", "province": "Sulawesi Selatan", "city": "Makassar", "website": "https://www.unhas.ac.id", "domain": "unhas.ac.id", "source": "direktori_dikti"},
    {"name": "Politeknik Negeri Bandung", "subtype": "Politeknik", "province": "Jawa Barat", "city": "Bandung Barat", "website": "https://www.polban.ac.id", "domain": "polban.ac.id", "source": "direktori_dikti"},
    {"name": "Politeknik Negeri Jakarta", "subtype": "Politeknik", "province": "DKI Jakarta", "city": "Depok", "website": "https://www.pnj.ac.id", "domain": "pnj.ac.id", "source": "direktori_dikti"},
    {"name": "Telkom University", "subtype": "Universitas", "province": "Jawa Barat", "city": "Bandung", "website": "https://www.telkomuniversity.ac.id", "domain": "telkomuniversity.ac.id", "source": "direktori_dikti"},
    {"name": "Universitas Bina Nusantara", "subtype": "Universitas", "province": "DKI Jakarta", "city": "Jakarta Barat", "website": "https://www.binus.ac.id", "domain": "binus.ac.id", "source": "direktori_dikti"},
    
    # Jenjang Sekolah Menengah & Kejuruan (SMA/SMK/Pesantren)
    {"name": "SMK Negeri 1 Cimahi", "subtype": "SMK", "province": "Jawa Barat", "city": "Cimahi", "website": "https://www.smkn1-cmi.sch.id", "domain": "smkn1-cmi.sch.id", "source": "direktori_kemendikbud"},
    {"name": "SMK Negeri 2 Bandung", "subtype": "SMK", "province": "Jawa Barat", "city": "Bandung", "website": "https://www.smkn2bandung.sch.id", "domain": "smkn2bandung.sch.id", "source": "direktori_kemendikbud"},
    {"name": "SMA Negeri 3 Bandung", "subtype": "SMA", "province": "Jawa Barat", "city": "Bandung", "website": "https://www.sman3bdg.sch.id", "domain": "sman3bdg.sch.id", "source": "direktori_kemendikbud"},
    {"name": "SMA Negeri 8 Jakarta", "subtype": "SMA", "province": "DKI Jakarta", "city": "Jakarta Selatan", "website": "https://www.sman8jkt.sch.id", "domain": "sman8jkt.sch.id", "source": "direktori_kemendikbud"},
    {"name": "Pondok Pesantren Modern Gontor", "subtype": "Pesantren", "province": "Jawa Timur", "city": "Ponorogo", "website": "https://www.gontor.ac.id", "domain": "gontor.ac.id", "source": "direktori_kemenag"},
]

# Komunitas Olahraga & Organisasi Mahasiswa Terverifikasi (Sample Seed Directories)
VERIFIED_COMMUNITY_SEEDS = [
    # Komunitas Olahraga
    {"name": "Bandung Futsal Community", "type": "Komunitas Olahraga", "subtype": "Klub Futsal", "sport": "Futsal", "city": "Bandung", "province": "Jawa Barat", "source": "community_directory", "socials": {"instagram": "https://www.instagram.com/bandungfutsal"}},
    {"name": "Jakarta Futsal League", "type": "Komunitas Olahraga", "subtype": "Liga Olahraga", "sport": "Futsal", "city": "Jakarta Selatan", "province": "DKI Jakarta", "source": "community_directory", "socials": {"instagram": "https://www.instagram.com/jakartafutsalleague"}},
    {"name": "Indorunners Bandung", "type": "Komunitas Olahraga", "subtype": "Komunitas Lari", "sport": "Running", "city": "Bandung", "province": "Jawa Barat", "source": "community_directory", "socials": {"instagram": "https://www.instagram.com/indorunnersbdg"}},
    {"name": "Jakarta Cycling Community", "type": "Komunitas Olahraga", "subtype": "Komunitas Sepeda", "sport": "Cycling", "city": "Jakarta Pusat", "province": "DKI Jakarta", "source": "community_directory", "socials": {"instagram": "https://www.instagram.com/jktcycling"}},
    {"name": "Surabaya Basketball Club", "type": "Komunitas Olahraga", "subtype": "Klub Basket", "sport": "Basket", "city": "Surabaya", "province": "Jawa Timur", "source": "community_directory", "socials": {"instagram": "https://www.instagram.com/subbasketball"}},
    {"name": "Bogor Volleyball Association", "type": "Komunitas Olahraga", "subtype": "Klub Voli", "sport": "Voli", "city": "Bogor", "province": "Jawa Barat", "source": "community_directory", "socials": {"facebook": "https://www.facebook.com/bogorvolley"}},
    {"name": "EVOS Esports Community", "type": "Komunitas Olahraga", "subtype": "Komunitas Gaming", "sport": "Esports", "city": "Jakarta Selatan", "province": "DKI Jakarta", "source": "community_directory", "socials": {"instagram": "https://www.instagram.com/evosesports"}},

    # Organisasi Mahasiswa
    {"name": "BEM KEMA Institut Teknologi Bandung", "type": "Organisasi Mahasiswa", "subtype": "BEM", "city": "Bandung", "province": "Jawa Barat", "source": "student_directory", "socials": {"instagram": "https://www.instagram.com/bemkemaitb"}},
    {"name": "BEM Universitas Indonesia", "type": "Organisasi Mahasiswa", "subtype": "BEM", "city": "Depok", "province": "DKI Jakarta", "source": "student_directory", "socials": {"instagram": "https://www.instagram.com/bemui_official"}},
    {"name": "UKM Sepak Bola & Futsal UGM", "type": "Organisasi Mahasiswa", "subtype": "UKM Olahraga", "sport": "Futsal", "city": "Sleman", "province": "DI Yogyakarta", "source": "student_directory", "socials": {"instagram": "https://www.instagram.com/futsalugm"}},
    {"name": "UKM Basket Universitas Airlangga", "type": "Organisasi Mahasiswa", "subtype": "UKM Olahraga", "sport": "Basket", "city": "Surabaya", "province": "Jawa Timur", "source": "student_directory", "socials": {"instagram": "https://www.instagram.com/basketunair"}},
    {"name": "HIMA Manajemen Universitas Padjadjaran", "type": "Organisasi Mahasiswa", "subtype": "Himpunan Mahasiswa", "city": "Sumedang", "province": "Jawa Barat", "source": "student_directory", "socials": {"instagram": "https://www.instagram.com/himamaunpad"}},
]


class DiscoveryPipelineService:
    """Service terpadu untuk Ingestion & Discovery Multi-Universe dengan deduplikasi dan integritas Master Organization."""

    @classmethod
    def ingest_candidate_to_master(
        cls,
        candidate_data: Dict[str, Any],
        engine: Optional[IdentityResolutionEngine] = None,
        user_id: Optional[int] = None
    ) -> Tuple[Organization, bool, str]:
        """Memproses satu kandidat hasil discovery melalui alur arsitektur inti:
        DISCOVERY -> PROSPECT -> IDENTITY RESOLUTION -> MASTER ORGANIZATION
        """
        raw_name = candidate_data.get("name", "").strip()
        if not raw_name:
            raise ValueError("Nama kandidat tidak boleh kosong.")

        if engine is None:
            engine = IdentityResolutionEngine(existing_orgs=Organization.query.all())

        # 1. Evaluasi Identitas dengan IdentityResolutionEngine
        match_res = engine.evaluate_candidate(
            name=raw_name,
            website=candidate_data.get("website", ""),
            email=candidate_data.get("email", ""),
            phone=candidate_data.get("phone", ""),
            city=candidate_data.get("city", ""),
            province=candidate_data.get("province", "")
        )

        now_str = utc_now().isoformat()
        is_new = False
        decision_note = ""

        if match_res.decision == "auto_match":
            master_org = match_res.matched_org
            # Non-destructive safe merge
            is_mod, _ = safe_merge_organization(master_org, candidate_data, match_res)
            if candidate_data.get("sport") and not master_org.sport:
                master_org.sport = candidate_data["sport"]
            if candidate_data.get("organization_subtype") and not master_org.organization_subtype:
                master_org.organization_subtype = candidate_data["organization_subtype"]
            if is_mod:
                engine.index_organization(master_org)
            decision_note = f"Auto-merged with existing Organization #{master_org.id}"
        else:
            # Buat entitas Master Organization baru
            master_org = create_organization_from_source(candidate_data)
            master_org.sport = candidate_data.get("sport")
            master_org.organization_subtype = candidate_data.get("organization_subtype")
            db.session.add(master_org)
            db.session.flush()
            engine.index_organization(master_org)
            is_new = True
            decision_note = f"Created new Master Organization #{master_org.id}"

        # 2. Sinkronisasikan ke Transitional Prospect Layer
        existing_p = Prospect.query.filter_by(organization_id=master_org.id).first()
        if not existing_p:
            existing_p = Prospect.query.filter_by(company_name=master_org.name).first()

        region_str = f"{master_org.city or ''}, {master_org.province or ''}".strip(", ") or None
        if not existing_p:
            p = Prospect(
                company_name=master_org.name,
                industry=master_org.industry,
                region=region_str,
                website=master_org.website,
                contact_phone=master_org.phone,
                contact_email=master_org.email,
                description=master_org.description or f"{master_org.organization_type} ({master_org.organization_subtype or ''})",
                segment=master_org.priority_tier or "C - POTENTIAL",
                score=master_org.opportunity_score or 50,
                score_reason=f"Discovered via {candidate_data.get('source_type', 'public_discovery')}",
                status="new",
                organization_id=master_org.id,
                created_by=user_id,
            )
            db.session.add(p)
        else:
            existing_p.organization_id = master_org.id

        db.session.commit()
        return master_org, is_new, decision_note

    # =========================================================================
    # A. EDUCATION DISCOVERY
    # =========================================================================

    @classmethod
    def discover_education_institutions(
        cls,
        query: str = "",
        level: str = "",
        province: str = "",
        city: str = "",
        limit: int = 15,
        limit_per_level: Optional[int] = None,
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Discovery institusi pendidikan Indonesia (PAUD/TK hingga Universitas).
        Sumber: Direktori resmi Kemendikbud/Dikti dan penemuan web publik terverifikasi.
        """
        engine = IdentityResolutionEngine(existing_orgs=Organization.query.all())
        created_count = 0
        updated_count = 0
        processed_candidates = []

        max_limit = limit_per_level if limit_per_level is not None else limit

        # 1. Filter dari direktori terverifikasi
        seeds = VERIFIED_INDONESIA_EDUCATION_SEEDS
        if level:
            seeds = [s for s in seeds if s["subtype"].lower() == level.lower()]
        if province:
            seeds = [s for s in seeds if s["province"].lower() == province.lower()]
        if city:
            seeds = [s for s in seeds if city.lower() in s.get("city", "").lower()]
        if query:
            q_low = query.lower()
            seeds = [s for s in seeds if q_low in s["name"].lower() or q_low in s.get("city", "").lower()]

        for item in seeds[:max_limit]:
            raw_sub = item.get("subtype", "school").lower()
            if "universitas" in raw_sub or "institut" in raw_sub or "politeknik" in raw_sub:
                norm_subtype = "university"
            elif "smk" in raw_sub:
                norm_subtype = "vocational_school"
            elif "sma" in raw_sub:
                norm_subtype = "high_school"
            elif "smp" in raw_sub:
                norm_subtype = "junior_high"
            elif "sd" in raw_sub or "paud" in raw_sub or "tk" in raw_sub:
                norm_subtype = "primary_school"
            else:
                norm_subtype = raw_sub

            candidate = {
                "name": item["name"],
                "organization_type": "education",
                "organization_subtype": norm_subtype,
                "industry": "Pendidikan",
                "province": item.get("province"),
                "city": item.get("city"),
                "website": item.get("website"),
                "domain": item.get("domain"),
                "source_type": "education_directory",
                "source_url": item.get("website"),
                "product_fit": "Jas Almamater, Kaos Angkatan, Seragam Olahraga, Jersey Panitia",
                "opportunity_score": 75,
                "priority_tier": "B - WARM",
                "provenance": {
                    "source": "kemdikbud_public_directory",
                    "source_type": "education_directory",
                    "source_url": item.get("website"),
                    "confidence": "high",
                    "raw_reference": item.get("domain"),
                    "discovered_at": utc_now().isoformat(),
                }
            }

            org, is_new, note = cls.ingest_candidate_to_master(candidate, engine=engine, user_id=user_id)
            if is_new:
                created_count += 1
            else:
                updated_count += 1
            processed_candidates.append({"org_id": org.id, "name": org.name, "is_new": is_new, "note": note})

        # 2. Public Web Search jika query spesifik disuplai dan hasil seed belum mencapai limit
        if query and len(processed_candidates) < max_limit:
            social_conn = SocialConnectorService()
            search_query = f"universitas sekolah {query} {province or 'Indonesia'}"
            web_results = social_conn.search_public_web(search_query, limit=5)
            for res in web_results:
                clean_title = res.get("title", "").split("-")[0].split("|")[0].strip()
                if len(clean_title) > 3 and not any(p["name"].lower() == clean_title.lower() for p in processed_candidates):
                    parsed_dom = extract_domain(res["url"])
                    cand = {
                        "name": clean_title,
                        "organization_type": "education",
                        "organization_subtype": "university",
                        "industry": "Pendidikan",
                        "province": province or None,
                        "website": res["url"],
                        "domain": parsed_dom,
                        "source_type": "education_directory",
                        "source_url": res["url"],
                        "product_fit": "Seragam Olahraga, Kaos Kegiatan, Jaket Almamater",
                        "opportunity_score": 65,
                        "priority_tier": "C - POTENTIAL",
                        "provenance": {
                            "source": "kemdikbud_public_directory",
                            "source_type": "education_directory",
                            "source_url": res["url"],
                            "confidence": "medium",
                            "discovered_at": utc_now().isoformat(),
                        }
                    }
                    try:
                        org, is_new, note = cls.ingest_candidate_to_master(cand, engine=engine, user_id=user_id)
                        if is_new:
                            created_count += 1
                        else:
                            updated_count += 1
                        processed_candidates.append({"org_id": org.id, "name": org.name, "is_new": is_new, "note": note})
                    except Exception as e:
                        logger.warning(f"Error ingesting web search education candidate: {e}")

        return {
            "category": "education",
            "total_processed": len(processed_candidates),
            "total_ingested": len(processed_candidates),
            "created": created_count,
            "new_organizations": created_count,
            "updated": updated_count,
            "matched_organizations": updated_count,
            "items": processed_candidates
        }

    # =========================================================================
    # B. COMMUNITY & STUDENT ORGANIZATION DISCOVERY
    # =========================================================================

    @classmethod
    def discover_communities(
        cls,
        category: str = "",
        sport: str = "",
        city: str = "",
        limit: int = 15,
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Discovery komunitas olahraga, organisasi mahasiswa, asosiasi, dan ormas."""
        engine = IdentityResolutionEngine(existing_orgs=Organization.query.all())
        created_count = 0
        updated_count = 0
        processed_candidates = []

        seeds = VERIFIED_COMMUNITY_SEEDS
        cat_low = category.lower().strip()
        if cat_low:
            seeds = [
                s for s in seeds
                if cat_low in s.get("type", "").lower()
                or cat_low in s.get("subtype", "").lower()
                or cat_low in s.get("sport", "").lower()
                or (cat_low == "student_org" and "mahasiswa" in s.get("type", "").lower())
            ]
        if sport:
            seeds = [s for s in seeds if s.get("sport", "").lower() == sport.lower()]
        if city:
            seeds = [s for s in seeds if city.lower() in s.get("city", "").lower()]

        for item in seeds[:limit]:
            raw_type = item.get("type", "").lower()
            raw_sport = item.get("sport", "").lower() if item.get("sport") else None

            if "mahasiswa" in raw_type or cat_low == "student_org":
                org_type = "student_org"
                org_subtype = "student_organization"
            else:
                org_type = "community"
                org_subtype = f"{raw_sport}_club" if raw_sport else "community_club"

            candidate = {
                "name": item["name"],
                "organization_type": org_type,
                "organization_subtype": org_subtype,
                "industry": "Komunitas & Olahraga",
                "sport": raw_sport,
                "province": item.get("province"),
                "city": item.get("city"),
                "social_json": json.dumps(item.get("socials", {})),
                "source_type": item.get("source", "community_directory"),
                "product_fit": "Jersey Custom, Teamwear Olahraga, Kaos Komunitas, Jaket Kontingen",
                "opportunity_score": 85 if raw_sport in ("futsal", "sepak bola", "basket", "running") else 75,
                "priority_tier": "A - HOT" if raw_sport in ("futsal", "sepak bola", "basket") else "B - WARM",
                "provenance": {
                    "source": item.get("source", "community_directory"),
                    "source_type": "community_directory",
                    "confidence": "high",
                    "discovered_at": utc_now().isoformat(),
                }
            }

            org, is_new, note = cls.ingest_candidate_to_master(candidate, engine=engine, user_id=user_id)
            if is_new:
                created_count += 1
            else:
                updated_count += 1
            processed_candidates.append({"org_id": org.id, "name": org.name, "is_new": is_new, "note": note})

        return {
            "category": "community",
            "total_processed": len(processed_candidates),
            "total_ingested": len(processed_candidates),
            "created": created_count,
            "new_organizations": created_count,
            "updated": updated_count,
            "matched_organizations": updated_count,
            "items": processed_candidates
        }

    # =========================================================================
    # C. SOCIAL MEDIA DISCOVERY (Instagram, TikTok, Facebook, LinkedIn)
    # =========================================================================

    @classmethod
    def discover_social_media(
        cls,
        platform: str,
        query: str,
        region: str = "Indonesia",
        limit: int = 10,
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """A. SOCIAL DISCOVERY:
        Menemukan komunitas/organisasi baru langsung dari platform media sosial.
        """
        social_conn = SocialConnectorService()
        candidates = social_conn.discover_social_candidates(
            platform=platform,
            query=query,
            region=region,
            limit=limit
        )

        engine = IdentityResolutionEngine(existing_orgs=Organization.query.all())
        created_count = 0
        updated_count = 0
        processed = []

        for cand in candidates:
            sport_detected = cand["signals"]["sport_signals"][0] if cand["signals"]["sport_signals"] else None
            social_dict = {platform: cand["profile_url"]}

            org_payload = {
                "name": cand["profile_name"] or f"@{cand['username']}",
                "organization_type": "Komunitas Olahraga" if sport_detected else "Komunitas Publik",
                "organization_subtype": f"Komunitas {sport_detected.title()}" if sport_detected else "Social Profile",
                "industry": "Komunitas & Olahraga" if sport_detected else "Kreatif & Media",
                "sport": sport_detected.title() if sport_detected else None,
                "social_json": json.dumps(social_dict),
                "source_type": cand["source"],
                "source_url": cand["source_url"],
                "description": cand.get("snippet", "")[:400],
                "product_fit": "Jersey Custom Olahraga, Kaos Event, Merchandise",
                "opportunity_score": 80 if sport_detected or cand["signals"]["product_signals"] else 60,
                "priority_tier": "A - HOT" if sport_detected else "B - WARM",
                "provenance": {
                    "source": cand["source"],
                    "source_url": cand["source_url"],
                    "confidence": "high",
                    "signals": cand["signals"],
                    "discovered_at": utc_now().isoformat(),
                }
            }

            try:
                org, is_new, note = cls.ingest_candidate_to_master(org_payload, engine=engine, user_id=user_id)
                if is_new:
                    created_count += 1
                else:
                    updated_count += 1
                processed.append({"org_id": org.id, "name": org.name, "platform": platform, "is_new": is_new, "note": note})
            except Exception as e:
                logger.error(f"Error ingesting social candidate {cand['username']}: {e}")

        return {
            "platform": platform,
            "query": query,
            "total_processed": len(processed),
            "created": created_count,
            "updated": updated_count,
            "items": processed
        }
