"""Meta Ad Library Supplier Intelligence Service.

Menghubungkan aplikasi ke Meta Graph API (Ad Library) untuk menemukan supplier kain,
konveksi, garmen, dan vendor bahan baku aktif di Indonesia dari iklan bersponsor FB/IG.
"""

import re
import json
import logging
import urllib.request
import urllib.parse
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.extensions import db
from app.models import ProcurementSupplier, utc_now

logger = logging.getLogger(__name__)

# Kamus deteksi material tekstil & apparel
MATERIAL_KEYWORDS = [
    "cotton combed", "combed 30s", "combed 24s", "combed 20s", "katun combed",
    "fleece", "baby terry", "drill", "american drill", "japan drill",
    "canvas", "kanvas", "rayon", "viscose", "spandex", "polyester",
    "dryfit", "milano", "scuba", "lotto", "diadora", "taslan", "parasut",
    "ripstop", "oxford", "chambray", "linen", "jersey", "hyget", "twill",
    "sublim", "sublimasi", "print sublim", "sublimation", "kain sublim", "jersey sublim"
]

def extract_phone_numbers(text: str) -> List[str]:
    """Mengekstrak nomor WhatsApp/telepon Indonesia dari teks iklan."""
    if not text:
        return []
    # Pola: 08xx-xxxx-xxxx atau +628xx atau 628xx
    pattern = r"(?:\+?62|0)8[1-9][0-9\-\s]{6,12}[0-9]"
    raw_matches = re.findall(pattern, text)
    cleaned = []
    for m in raw_matches:
        num = re.sub(r"[^\d+]", "", m)
        if len(num) >= 10:
            cleaned.append(num)
    return list(dict.fromkeys(cleaned))

def extract_materials(text: str) -> List[str]:
    """Mendeteksi jenis bahan/material yang ditawarkan pada copywriting iklan."""
    if not text:
        return []
    text_low = text.lower()
    found = []
    for mat in MATERIAL_KEYWORDS:
        if mat in text_low:
            found.append(mat.title())
    return list(dict.fromkeys(found))


class MetaAdSupplierService:
    """Engine penarik dan parser supplier dari Meta Ad Library API."""

    GRAPH_API_VERSION = "v19.0"
    BASE_URL = f"https://graph.facebook.com/{GRAPH_API_VERSION}/ads_archive"

    @classmethod
    def fetch_supplier_ads(
        cls,
        access_token: str,
        search_terms: str = "supplier kain",
        country: str = "ID",
        limit: int = 25
    ) -> Dict[str, Any]:
        """Menembak endpoint Meta Ad Library API untuk mengambil data iklan supplier."""
        params = {
            "ad_reached_countries": f"['{country}']",
            "ad_type": "ALL",
            "search_terms": search_terms,
            "fields": (
                "id,page_id,page_name,ad_creative_bodies,"
                "ad_creative_link_captions,ad_creative_link_titles,"
                "publisher_platforms,ad_delivery_start_time"
            ),
            "limit": limit,
            "access_token": access_token
        }

        query_str = urllib.parse.urlencode(params)
        req_url = f"{cls.BASE_URL}?{query_str}"

        try:
            req = urllib.request.Request(req_url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return {"success": True, "data": data.get("data", []), "paging": data.get("paging", {})}
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8")
            try:
                err_json = json.loads(err_body)
                err_msg = err_json.get("error", {}).get("message", err_body)
                err_subcode = err_json.get("error", {}).get("error_subcode")
                user_msg = err_json.get("error", {}).get("error_user_msg", "")
            except Exception:
                err_msg = err_body
                err_subcode = None
                user_msg = ""
            return {
                "success": False,
                "error": err_msg,
                "error_subcode": err_subcode,
                "error_user_msg": user_msg,
                "status_code": e.code
            }
        except Exception as e:
            return {"success": False, "error": str(e), "status_code": 500}

    @classmethod
    def ingest_ads_to_suppliers(
        cls,
        ads_data: List[Dict[str, Any]],
        default_category: str = "raw material",
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Mem-parsing data iklan Meta dan menyimpannya ke tabel procurement_suppliers."""
        created_count = 0
        updated_count = 0
        saved_items = []

        for item in ads_data:
            ad_id = item.get("id")
            page_name = (item.get("page_name") or "").strip()
            if not page_name:
                continue

            bodies = item.get("ad_creative_bodies") or []
            body_text = "\n".join(bodies) if bodies else ""

            # Ekstrak nomor kontak WA
            phones = extract_phone_numbers(body_text)
            contact_phone = phones[0] if phones else None

            # Ekstrak material kain
            materials = extract_materials(body_text)
            material_str = ", ".join(materials) if materials else "Kain & Tekstil Komersial"

            # Ekstrak URL tujuan iklan
            captions = item.get("ad_creative_link_captions") or []
            dest_url = captions[0] if captions else None
            if not dest_url and contact_phone:
                dest_url = f"https://wa.me/{contact_phone.lstrip('+')}"

            source_url = f"https://www.facebook.com/ads/library/?id={ad_id}"

            # Cek apakah supplier dengan sumber ini sudah pernah masuk
            existing = ProcurementSupplier.query.filter(
                db.or_(
                    ProcurementSupplier.source_url == source_url,
                    ProcurementSupplier.company_name == page_name
                )
            ).first()

            if existing:
                # Update informasi jika ada data kontak baru
                if contact_phone and not existing.contact_phone:
                    existing.contact_phone = contact_phone
                if material_str and not existing.material:
                    existing.material = material_str
                if dest_url and not existing.website:
                    existing.website = dest_url
                updated_count += 1
                saved_items.append({"id": existing.id, "name": existing.company_name, "is_new": False})
            else:
                supplier = ProcurementSupplier(
                    company_name=page_name,
                    product=f"Bahan Baku: {material_str}",
                    material=material_str,
                    region="Indonesia",
                    website=dest_url,
                    source_url=source_url,
                    contact_phone=contact_phone,
                    description=body_text[:500] if body_text else f"Supplier aktif dari iklan Meta ({item.get('page_name')})",
                    fit_score=85 if contact_phone else 70,
                    verification_status="verified_active_ad",
                    created_by=user_id,
                    created_at=utc_now()
                )
                db.session.add(supplier)
                created_count += 1
                saved_items.append({"id": supplier.id, "name": supplier.company_name, "is_new": True})

        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error saving Meta Ad suppliers to DB: {e}")
            return {"success": False, "error": str(e)}

        return {
            "success": True,
            "total_processed": len(ads_data),
            "created": created_count,
            "updated": updated_count,
            "suppliers": saved_items
        }
