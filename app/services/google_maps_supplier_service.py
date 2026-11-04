"""Google Maps Places Supplier Intelligence Service.

Menghubungkan aplikasi ke Google Places API (New) untuk mencari toko bahan kain,
sentra konveksi, garmen, dan supplier tekstil lokal di seluruh wilayah Indonesia
lengkap dengan alamat, nomor telepon/WhatsApp, rating bintang, dan ulasan.
"""

import os
import re
import json
import logging
import urllib.request
import urllib.parse
from typing import Dict, Any, List, Optional

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


def clean_phone_number(raw_phone: Optional[str]) -> Optional[str]:
    """Membersihkan nomor telepon dan memformatnya agar siap dihubungi."""
    if not raw_phone:
        return None
    # Hapus karakter selain digit dan tanda tambah
    cleaned = re.sub(r"[^\d+]", "", raw_phone)
    if len(cleaned) < 7:
        return None
    return cleaned


def to_whatsapp_number(phone: Optional[str]) -> Optional[str]:
    """Mengubah nomor telepon Indonesia ke format WhatsApp internasional (628...)."""
    if not phone:
        return None
    num = re.sub(r"[^\d]", "", phone)
    if num.startswith("08"):
        return f"62{num[1:]}"
    elif num.startswith("628"):
        return num
    elif num.startswith("8") and len(num) >= 10:
        return f"62{num}"
    return None


def extract_materials(text: str) -> List[str]:
    """Mendeteksi jenis bahan/material dari nama toko atau deskripsi."""
    if not text:
        return []
    text_low = text.lower()
    found = []
    for mat in MATERIAL_KEYWORDS:
        if mat in text_low:
            found.append(mat.title())
    return list(dict.fromkeys(found))


class GoogleMapsSupplierService:
    """Engine penarik dan parser supplier dari Google Places API (New)."""

    SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"

    @classmethod
    def search_places(
        cls,
        query: str = "supplier kain",
        location: Optional[str] = None,
        limit: int = 15,
        api_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """Mencari tempat/toko supplier menggunakan Google Places API (New)."""
        key = api_key or os.environ.get("GOOGLE_SEARCH_API_KEY") or os.environ.get("GOOGLE_MAPS_API_KEY", "")
        if not key:
            return {
                "success": False,
                "error": "Google API Key belum dikonfigurasi di file .env (GOOGLE_SEARCH_API_KEY)."
            }

        # Gabungkan kata kunci dengan lokasi jika ada
        search_text = query.strip()
        if location and location.strip().lower() not in ["semua", "indonesia", ""]:
            loc_str = location.strip()
            if loc_str.lower() not in search_text.lower():
                search_text = f"{search_text} di {loc_str}"

        payload = {
            "textQuery": search_text,
            "pageSize": max(1, min(20, limit)),
            "languageCode": "id"
        }

        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": key,
            "X-Goog-FieldMask": (
                "places.id,"
                "places.displayName,"
                "places.formattedAddress,"
                "places.nationalPhoneNumber,"
                "places.internationalPhoneNumber,"
                "places.websiteUri,"
                "places.rating,"
                "places.userRatingCount,"
                "places.googleMapsUri,"
                "places.regularOpeningHours,"
                "places.location"
            )
        }

        try:
            req = urllib.request.Request(
                cls.SEARCH_URL,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers
            )
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                raw_places = data.get("places", [])

                formatted = []
                for p in raw_places:
                    name = (p.get("displayName", {}).get("text") or "").strip()
                    if not name:
                        continue

                    phone = clean_phone_number(
                        p.get("nationalPhoneNumber") or p.get("internationalPhoneNumber")
                    )
                    wa_num = to_whatsapp_number(phone)
                    address = p.get("formattedAddress", "")
                    rating = p.get("rating", 0.0)
                    rating_count = p.get("userRatingCount", 0)
                    maps_url = p.get("googleMapsUri") or f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(name + ' ' + address)}"
                    website = p.get("websiteUri")
                    loc = p.get("location", {})

                    formatted.append({
                        "place_id": p.get("id"),
                        "name": name,
                        "address": address,
                        "phone": phone,
                        "whatsapp_number": wa_num,
                        "whatsapp_url": f"https://wa.me/{wa_num}" if wa_num else None,
                        "rating": rating,
                        "rating_count": rating_count,
                        "maps_url": maps_url,
                        "website": website,
                        "location": loc,
                        "opening_hours": p.get("regularOpeningHours", {}).get("weekdayDescriptions", [])
                    })

                return {
                    "success": True,
                    "query": search_text,
                    "data": formatted,
                    "total": len(formatted)
                }

        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8")
            err_msg = err_body
            is_service_disabled = False
            activation_url = "https://console.developers.google.com/apis/api/places.googleapis.com/overview?project=416634491004"

            try:
                err_json = json.loads(err_body)
                err_msg = err_json.get("error", {}).get("message", err_body)
                if "places.googleapis.com" in err_msg or "SERVICE_DISABLED" in err_body or "not been used" in err_msg:
                    is_service_disabled = True
            except Exception:
                pass

            return {
                "success": False,
                "error": err_msg,
                "is_service_disabled": is_service_disabled,
                "activation_url": activation_url,
                "status_code": e.code
            }
        except Exception as e:
            return {"success": False, "error": str(e), "status_code": 500}

    @classmethod
    def ingest_places_to_suppliers(
        cls,
        places_data: List[Dict[str, Any]],
        default_category: str = "raw material",
        default_material: Optional[str] = None,
        region_label: Optional[str] = None,
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Mem-parsing hasil pencarian Google Places dan menyimpannya ke tabel procurement_suppliers."""
        created_count = 0
        updated_count = 0
        saved_items = []

        for p in places_data:
            name = (p.get("name") or "").strip()
            if not name:
                continue

            address = p.get("address") or ""
            phone = p.get("phone")
            wa_num = p.get("whatsapp_number")
            maps_url = p.get("maps_url") or f"https://maps.google.com/?q={urllib.parse.quote(name)}"
            website = p.get("website") or maps_url
            rating = p.get("rating", 0.0)
            rating_count = p.get("rating_count", 0)

            # Deteksi material dari nama toko & query
            detected_mats = extract_materials(f"{name} {default_material or ''}")
            material_str = ", ".join(detected_mats) if detected_mats else (default_material or "Kain & Tekstil Komersial")

            # Tentukan region
            region = region_label or "Indonesia"
            if "Bandung" in address:
                region = "Bandung, Jawa Barat"
            elif "Jakarta" in address:
                region = "Jakarta"
            elif "Solo" in address or "Surakarta" in address:
                region = "Solo, Jawa Tengah"
            elif "Surabaya" in address:
                region = "Surabaya, Jawa Timur"

            # Hitung skor kecocokan (fit_score)
            fit_score = 70
            if phone or wa_num:
                fit_score += 10
            if rating >= 4.5:
                fit_score += 10
            elif rating >= 4.0:
                fit_score += 5
            if rating_count >= 20:
                fit_score += 10
            elif rating_count >= 5:
                fit_score += 5
            fit_score = min(98, fit_score)

            # Metadata JSON tambahan
            rec_meta = {
                "source": "google_maps",
                "place_id": p.get("place_id"),
                "rating": rating,
                "rating_count": rating_count,
                "maps_url": maps_url,
                "address": address,
                "whatsapp_number": wa_num,
                "whatsapp_url": p.get("whatsapp_url"),
                "location": p.get("location")
            }

            desc = f"Supplier fisik / Toko dari Google Maps di {address}. Rating Google: {rating} ({rating_count} ulasan)."

            # Cek apakah sudah pernah tersimpan (berdasarkan source_url atau company_name)
            existing = ProcurementSupplier.query.filter(
                db.or_(
                    ProcurementSupplier.source_url == maps_url,
                    ProcurementSupplier.company_name == name
                )
            ).first()

            if existing:
                if phone and not existing.contact_phone:
                    existing.contact_phone = phone
                if address and not existing.region:
                    existing.region = region
                if not existing.recommendation_json:
                    existing.recommendation_json = json.dumps(rec_meta)
                updated_count += 1
                saved_items.append({"id": existing.id, "name": existing.company_name, "is_new": False})
            else:
                supplier = ProcurementSupplier(
                    company_name=name,
                    product=f"Bahan Baku: {material_str}",
                    material=material_str,
                    region=region,
                    website=website,
                    source_url=maps_url,
                    contact_phone=phone or (f"+{wa_num}" if wa_num else None),
                    description=desc,
                    fit_score=fit_score,
                    recommendation_json=json.dumps(rec_meta),
                    verification_status="verified_maps_listing",
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
            logger.error(f"Error saving Google Maps suppliers to DB: {e}")
            return {"success": False, "error": str(e)}

        return {
            "success": True,
            "total_processed": len(places_data),
            "created": created_count,
            "updated": updated_count,
            "suppliers": saved_items
        }

