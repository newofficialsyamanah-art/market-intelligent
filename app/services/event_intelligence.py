"""Event Intelligence Service (Phase 5).

Menyediakan engine modular untuk penemuan, validasi, deduplikasi, skoring relevansi,
dan relasi partisipan (organizer, exhibitor, sponsor, partner, speaker) ke Master Organizations.
"""

import re
import json
import logging
from datetime import datetime, timezone, date
from urllib.parse import urlparse
from typing import Dict, Any, List, Optional, Tuple

from app.extensions import db
from app.models import Event, EventParticipant, Organization, DuplicateCandidate, utc_now
from app.services.dedup_engine import (
    normalize_company_name,
    extract_domain,
    DIRECTORY_AND_AGGREGATOR_DOMAINS,
    PUBLIC_EMAIL_DOMAINS,
)

logger = logging.getLogger(__name__)

# Kamus Relevansi untuk B2B Apparel / Uniform / Merchandise Opportunity
HIGH_RELEVANCE_KEYWORDS = [
    "textile", "tekstil", "garment", "garmen", "apparel", "pakaian", "fashion", "busana",
    "seragam", "uniform", "merchandise", "convection", "konveksi", "sablon", "bordir",
    "indo intertex", "inatex", "inacraft", "jakarta fashion week", "jfw", "trade expo indonesia",
    "procurement", "pengadaan", "corporate apparel", "workwear", "safety wear"
]

MEDIUM_RELEVANCE_KEYWORDS = [
    "manufacturing", "manufaktur", "industrial", "industri", "expo", "pameran", "b2b",
    "leather", "alas kaki", "footwear", "giias", "otomotif", "automotive", "mining",
    "pertambangan", "oil", "gas", "konstruksi", "construction", "packaging", "kemasan",
    "hospitality", "hotel", "f&b", "kuliner", "food & beverage", "career expo", "job fair",
    "campus expo", "university fair"
]

LOW_RELEVANCE_KEYWORDS = [
    "property", "properti", "wedding", "pernikahan", "baby", "anak", "pet", "hewan",
    "beauty", "kecantikan", "art", "seni", "book", "buku", "education", "pendidikan"
]

REJECT_KEYWORDS = [
    "spam", "judi", "slot", "togel", "casino", "porn", "dating", "crypto giveaway"
]


def normalize_event_name(name: str) -> str:
    """Menormalisasi nama event untuk perbandingan deduplikasi."""
    if not name:
        return ""
    text = name.lower()
    text = re.sub(r"\b(the|indonesia|jakarta|international|annual|annualy|ke-\d+|\d{4})\b", " ", text)
    text = re.sub(r"[^\w\s]", " ", text)
    tokens = [t.strip() for t in text.split() if len(t.strip()) > 1]
    return " ".join(tokens)


class EventIntelligenceService:
    """Service modular untuk Event Intelligence (Phase 5)."""

    @staticmethod
    def calculate_relevance(name: str, event_type: str = "", description: str = "", organizer: str = "") -> Tuple[str, int, str]:
        """Menghitung klasifikasi relevansi (HIGH, MEDIUM, LOW, REJECT) dan score 0-100
        terhadap potensi kebutuhan seragam, apparel kerja, dan merchandise B2B.
        """
        combined = f"{name} {event_type} {description} {organizer}".lower()

        # 1. Cek Reject (Spam / Invalid)
        for bad in REJECT_KEYWORDS:
            if bad in combined:
                return "REJECT", 0, f"Terdeteksi kata terlarang/spam: '{bad}'"

        # 2. Cek High Relevance
        high_matches = [k for k in HIGH_RELEVANCE_KEYWORDS if k in combined]
        if high_matches:
            score = min(80 + len(high_matches) * 5, 100)
            return "HIGH", score, f"Relevansi Tinggi: Terkait industri apparel/tekstil/pengadaan ({', '.join(high_matches[:3])})"

        # 3. Cek Medium Relevance
        med_matches = [k for k in MEDIUM_RELEVANCE_KEYWORDS if k in combined]
        if med_matches:
            score = min(50 + len(med_matches) * 5, 79)
            return "MEDIUM", score, f"Relevansi Menengah: Event industri/B2B/kampus dengan peluang seragam ({', '.join(med_matches[:3])})"

        # 4. Cek Low Relevance
        low_matches = [k for k in LOW_RELEVANCE_KEYWORDS if k in combined]
        if low_matches:
            return "LOW", 35, f"Relevansi Rendah: Event umum/konsumen ({', '.join(low_matches[:2])})"

        return "LOW", 30, "Relevansi Rendah: Informasi tidak spesifik apparel/B2B"

    @classmethod
    def deduplicate_event(cls, event_data: Dict[str, Any]) -> Tuple[Optional[Event], str, float]:
        """Mengecek apakah event sudah ada di database menggunakan multi-signal matching:
        - Canonical URL exact match (Tier 1)
        - Normalized name + Start Date + City (Tier 2)
        - Normalized name + Organizer (Tier 3)
        Mengembalikan (event, match_tier, confidence) atau (None, "none", 0.0)
        """
        url = event_data.get("website") or event_data.get("source_url")
        name = event_data.get("name", "").strip()
        start_date = event_data.get("start_date")
        city = event_data.get("city", "").strip()
        venue = event_data.get("venue", "").strip()
        organizer = event_data.get("organizer", "").strip()

        # Tier 1: Canonical URL
        if url:
            dom = extract_domain(url)
            if dom and dom not in DIRECTORY_AND_AGGREGATOR_DOMAINS:
                existing = Event.query.filter(
                    db.or_(Event.website.like(f"%{dom}%"), Event.source_url.like(f"%{dom}%"))
                ).first()
                if existing:
                    return existing, "tier1_canonical_url", 0.98

        norm_name = normalize_event_name(name)
        if not norm_name:
            return None, "none", 0.0

        all_events = Event.query.all()
        for ev in all_events:
            ev_norm = normalize_event_name(ev.name)
            if not ev_norm:
                continue

            # Exact normalized name match
            if norm_name == ev_norm:
                # Cek tanggal dan lokasi
                if start_date and ev.start_date and start_date == ev.start_date:
                    return ev, "tier2_name_date", 0.95
                if venue and ev.venue and venue.lower() == ev.venue.lower():
                    return ev, "tier2_name_venue", 0.92
                if city and ev.city and city.lower() == ev.city.lower():
                    return ev, "tier2_name_city", 0.90
                if organizer and ev.organizer and organizer.lower() == ev.organizer.lower():
                    return ev, "tier3_name_organizer", 0.85

        return None, "none", 0.0

    @classmethod
    def create_or_update_event(cls, event_data: Dict[str, Any], dry_run: bool = False) -> Tuple[Event, bool, str]:
        """Membuat atau memperbarui event secara idempotent dan non-destructive."""
        existing, match_tier, confidence = cls.deduplicate_event(event_data)

        # Hitung relevansi
        relevance_cat, rel_score, rel_notes = cls.calculate_relevance(
            name=event_data.get("name", ""),
            event_type=event_data.get("event_type", ""),
            description=event_data.get("description", ""),
            organizer=event_data.get("organizer", "")
        )

        if existing:
            # Safe Non-Destructive Update
            if not dry_run:
                if not existing.description and event_data.get("description"):
                    existing.description = event_data["description"]
                if not existing.venue and event_data.get("venue"):
                    existing.venue = event_data["venue"]
                if not existing.city and event_data.get("city"):
                    existing.city = event_data["city"]
                if not existing.province and event_data.get("province"):
                    existing.province = event_data["province"]
                if not existing.website and event_data.get("website"):
                    existing.website = event_data["website"]
                if not existing.social_json and event_data.get("social_json"):
                    existing.social_json = event_data["social_json"]
                if rel_score > (existing.relevance_score or 0):
                    existing.relevance_score = rel_score
                    existing.relevance_notes = rel_notes
                existing.last_seen = utc_now()
                db.session.commit()
            return existing, False, f"Updated ({match_tier})"

        # Buat Event Baru
        event = Event(
            name=event_data["name"].strip(),
            event_type=event_data.get("event_type", "Exhibition / Trade Fair"),
            organizer=event_data.get("organizer"),
            organizer_id=event_data.get("organizer_id"),
            status=event_data.get("status", "upcoming"),
            start_date=event_data.get("start_date"),
            end_date=event_data.get("end_date"),
            venue=event_data.get("venue"),
            city=event_data.get("city"),
            province=event_data.get("province"),
            address=event_data.get("address"),
            website=event_data.get("website"),
            social_json=event_data.get("social_json"),
            source_url=event_data.get("source_url"),
            description=event_data.get("description"),
            relevance_notes=rel_notes,
            relevance_score=rel_score,
            verification_status="verified" if relevance_cat in ("HIGH", "MEDIUM") else "discovered",
            created_at=utc_now(),
            last_seen=utc_now()
        )

        if not dry_run:
            db.session.add(event)
            db.session.commit()

        return event, True, "Created"

    @classmethod
    def discover_events(
        cls,
        query: str = "",
        city: str = "",
        province: str = "",
        limit: int = 8,
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Menemukan event pameran, expo, festival B2B, dan turnamen olahraga nyata
        secara dinamis di seluruh Indonesia menggunakan AI & Market Intelligence.
        """
        from app.ai_agent import _chat_json

        target_loc = []
        if city:
            target_loc.append(city)
        if province:
            target_loc.append(province)
        location_str = ", ".join(target_loc) if target_loc else "seluruh Indonesia (Surabaya, Malang, Jakarta, Bandung, Semarang, Medan, Bali, Makassar, dll)"

        prompt = f"""Kamu adalah AI Event Intelligence Indonesia.
Tugas: Temukan dan berikan daftar {limit} event bisnis, pameran (expo/trade fair), konferensi B2B, festival industri, atau turnamen olahraga besar nyata di:
- Lokasi: {location_str}
- Topik / Kategori Event: {query or 'Pameran Bisnis, Industri, Manufaktur, Tekstil, Otomotif, UMKM, Turnamen Futsal/Lari/Basket'}

Format respon HANYA list JSON valid:
[
  {{
    "name": "Nama Lengkap Event (contoh: Jatim Expo 2026, IIMS Surabaya 2026, Bromo Marathon 2026)",
    "event_type": "Exhibition / Trade Fair / Conference / Sports Tournament",
    "venue": "Nama Gedung / Tempat (contoh: Grand City Surabaya, Jatim Expo, DBL Arena, JIExpo, dll)",
    "city": "Kota",
    "province": "Provinsi",
    "organizer": "Nama Penyelenggara / EO",
    "description": "Deskripsi singkat profil event dan potensi kebutuhan seragam/apparel",
    "status": "upcoming"
  }}
]
"""
        created_count = 0
        updated_count = 0
        items = []

        try:
            raw_data = _chat_json(
                system_prompt="Kamu adalah AI Event Intelligence spesialis penemuan event B2B, expo, dan turnamen olahraga di Indonesia.",
                user_prompt=prompt,
                temperature=0.3
            )
            candidates = raw_data if isinstance(raw_data, list) else raw_data.get("events") or raw_data.get("items") or []

            for c in candidates[:limit]:
                if not isinstance(c, dict) or not c.get("name"):
                    continue

                event_dict = {
                    "name": c.get("name", "").strip(),
                    "event_type": c.get("event_type", "Exhibition / Trade Fair"),
                    "venue": c.get("venue"),
                    "city": c.get("city") or city or None,
                    "province": c.get("province") or province or None,
                    "organizer": c.get("organizer"),
                    "description": c.get("description"),
                    "status": c.get("status", "upcoming"),
                    "source_url": "ai_event_discovery"
                }

                event, is_new, msg = cls.create_or_update_event(event_dict)
                if is_new:
                    created_count += 1
                else:
                    updated_count += 1
                items.append({
                    "id": event.id,
                    "name": event.name,
                    "city": event.city,
                    "province": event.province,
                    "is_new": is_new,
                    "relevance_score": event.relevance_score
                })

        except Exception as e:
            logger.error(f"Error in discover_events: {e}")
            return {
                "total_processed": 0,
                "created": 0,
                "updated": 0,
                "items": [],
                "error": str(e)
            }

        return {
            "total_processed": len(items),
            "created": created_count,
            "updated": updated_count,
            "items": items
        }

    @classmethod
    def match_organization(cls, company_name: str, domain: Optional[str] = None) -> Tuple[Optional[Organization], str]:
        """Mencari entitas Master Organization yang cocok untuk menjadi peserta/organizer.
        Menggunakan Domain Match (Tier 1) atau Normalized Legal Name (Tier 2).
        Jika ambigu, mengembalikan (None, 'ambiguous').
        """
        if not company_name:
            return None, "empty_name"

        # 1. Domain match jika ada
        if domain and domain not in DIRECTORY_AND_AGGREGATOR_DOMAINS and domain not in PUBLIC_EMAIL_DOMAINS:
            org = Organization.query.filter(Organization.domain == domain).first()
            if org:
                return org, "tier1_domain"

        # 2. Normalized name match
        norm = normalize_company_name(company_name)
        if norm:
            org = Organization.query.filter(
                db.or_(
                    Organization.name == company_name,
                    Organization.name.like(f"%{norm}%")
                )
            ).first()
            if org:
                return org, "tier2_normalized_name"

        return None, "not_found"

    @classmethod
    def link_participant(
        cls,
        event_id: int,
        organization_id: int,
        role: str = "exhibitor",
        booth_number: Optional[str] = None,
        notes: Optional[str] = None,
        dry_run: bool = False
    ) -> Tuple[Optional[EventParticipant], bool]:
        """Menghubungkan organisasi master sebagai peserta event (organizer, exhibitor, sponsor, partner, speaker).
        Idempotent dan menjaga unique constraint uq_event_org_role.
        """
        existing = EventParticipant.query.filter_by(
            event_id=event_id,
            organization_id=organization_id,
            role=role
        ).first()

        if existing:
            if not dry_run and (booth_number or notes):
                if booth_number and not existing.booth_number:
                    existing.booth_number = booth_number
                if notes and not existing.notes:
                    existing.notes = notes
                db.session.commit()
            return existing, False

        part = EventParticipant(
            event_id=event_id,
            organization_id=organization_id,
            role=role,
            booth_number=booth_number,
            notes=notes,
            created_at=utc_now()
        )

        if not dry_run:
            db.session.add(part)
            db.session.commit()

        return part, True

    @classmethod
    def get_workspace_events(
        cls,
        q: str = "",
        event_type: str = "",
        relevance: str = "",
        city: str = "",
        province: str = "",
        status: str = "",
        organizer: str = "",
        start_date_from: Optional[datetime] = None,
        start_date_to: Optional[datetime] = None,
        source: str = "",
        verification_status: str = "",
        page: int = 1,
        per_page: int = 20
    ) -> Tuple[List[Event], int, int]:
        """Pencarian dan penyaringan data Event Intelligence Workspace."""
        query = Event.query

        if q:
            query = query.filter(
                db.or_(
                    Event.name.like(f"%{q}%"),
                    Event.organizer.like(f"%{q}%"),
                    Event.venue.like(f"%{q}%"),
                    Event.city.like(f"%{q}%"),
                    Event.province.like(f"%{q}%"),
                    Event.description.like(f"%{q}%")
                )
            )

        if event_type:
            query = query.filter(Event.event_type == event_type)

        if city:
            query = query.filter(
                db.or_(
                    Event.city.ilike(f"%{city}%"),
                    Event.province.ilike(f"%{city}%")
                )
            )

        if province:
            query = query.filter(Event.province.ilike(f"%{province}%"))

        if status:
            query = query.filter(Event.status == status)

        if organizer:
            query = query.filter(Event.organizer.like(f"%{organizer}%"))

        if start_date_from:
            query = query.filter(Event.start_date >= start_date_from)

        if start_date_to:
            query = query.filter(Event.start_date <= start_date_to)

        if source:
            query = query.filter(
                db.or_(
                    Event.website.like(f"%{source}%"),
                    Event.source_url.like(f"%{source}%")
                )
            )

        if verification_status:
            query = query.filter(Event.verification_status == verification_status)

        if relevance == "HIGH":
            query = query.filter(Event.relevance_score >= 80)
        elif relevance == "MEDIUM":
            query = query.filter(Event.relevance_score >= 50, Event.relevance_score < 80)
        elif relevance == "LOW":
            query = query.filter(Event.relevance_score < 50)

        total_count = query.count()
        total_pages = (total_count + per_page - 1) // per_page if total_count > 0 else 1

        items = query.order_by(
            Event.relevance_score.desc(),
            Event.start_date.desc()
        ).offset((page - 1) * per_page).limit(per_page).all()

        return items, total_count, total_pages

    @classmethod
    def get_event_detail(cls, event_id: int) -> Optional[Dict[str, Any]]:
        """Mengambil profil lengkap event, organizer, peserta per peran, dan statistik."""
        event = db.session.get(Event, event_id)
        if not event:
            return None

        # Kelompokkan partisipan berdasarkan peran
        participants = EventParticipant.query.filter_by(event_id=event_id).all()
        by_role = {
            "organizers": [],
            "exhibitors": [],
            "sponsors": [],
            "partners": [],
            "speakers": []
        }

        for p in participants:
            role_key = f"{p.role}s" if not p.role.endswith("s") else p.role
            if role_key in by_role:
                by_role[role_key].append({
                    "id": p.id,
                    "organization_id": p.organization_id,
                    "organization_name": p.organization.name if p.organization else "Unknown",
                    "organization_industry": p.organization.industry if p.organization else None,
                    "organization_website": p.organization.website if p.organization else None,
                    "booth_number": p.booth_number,
                    "notes": p.notes
                })

        socials = {}
        if event.social_json:
            try:
                socials = json.loads(event.social_json) if isinstance(json.loads(event.social_json), dict) else {}
            except Exception:
                socials = {}

        return {
            "event": event,
            "socials": socials,
            "participants_count": len(participants),
            "by_role": by_role,
            "relevance_badge": "HIGH" if (event.relevance_score or 0) >= 80 else ("MEDIUM" if (event.relevance_score or 0) >= 50 else "LOW")
        }
