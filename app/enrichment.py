"""Enrichment Service untuk Dataset Bisnis & BPS.

Menyediakan engine enrichment berbasis file yang cepat, scalable (8.500 - 10.000+ baris),
mampu mengklasifikasikan kategori industri, merekomendasikan produk apparel/merchandise,
menghitung sales score, menentukan tingkat prioritas (A/B/C/D), mengekspor ke Excel,
serta menyimpan hasil akhir ke database secara bertahap (batch / chunk).
"""

import os
import re
import json
import uuid
import logging
from typing import Optional, Tuple, Dict, Any, List
import pandas as pd
from app.extensions import db
from app.models import Prospect, Organization, DuplicateCandidate, RawData
from app.services.dedup_engine import (
    IdentityResolutionEngine,
    safe_merge_organization,
    create_organization_from_source,
    normalize_company_name,
    extract_domain,
    normalize_phone,
    normalize_location,
)

logger = logging.getLogger(__name__)

# Standard column mapping aliases
COLUMN_ALIASES = {
    "nama_perusahaan": ["nama_perusahaan", "nama perusahaan", "perusahaan", "company", "company_name", "nama", "nama_badan_usaha"],
    "alamat": ["alamat", "address", "alamat_perusahaan", "street"],
    "kota": ["kota", "city", "kabupaten", "kabupaten/kota", "kabupaten_kota"],
    "provinsi": ["provinsi", "province", "prov"],
    "produk_utama": ["produk_utama", "produk", "products", "main_product", "komoditas"],
    "industri": ["industri", "industry", "kbli", "kode_kbli", "sektor", "sector"],
    "telepon": ["telepon", "telp", "phone", "contact_phone", "no_telp", "no_telepon", "mobile"],
    "email": ["email", "e-mail", "contact_email", "surel"],
    "website": ["website", "web", "url", "site", "web_address"],
    "instagram": ["instagram", "ig", "instagram_url"],
    "facebook": ["facebook", "fb", "facebook_url"],
    "linkedin": ["linkedin", "linkedin_url"],
    "source": ["source", "sumber", "data_source"]
}

# Industry keywords mapping
INDUSTRY_PATTERNS = [
    ("TEXTILE", re.compile(r"\b(TEXTILE|TEKSTIL|SPINNING|WEAVING|TENUN|RAJUT|BENANG|KNITTING)\b", re.IGNORECASE)),
    ("GARMENT / APPAREL", re.compile(r"\b(GARMENT|APPAREL|KONVEKSI|BUSANA|PAKAIAN|JAHIT)\b", re.IGNORECASE)),
    ("FOOD / F&B", re.compile(r"\b(FOOD|MEAT|SEAFOOD|COCOA|SUSU|NABATI|BASO|BAKSO|SNACK|BEVERAGE|KULINER|ROTI|BAKERY|KECAP|KOPI|COFFEE|TEA|TEH|BERAS|FLOUR|TEPUNG|MINUMAN|MAKANAN)\b", re.IGNORECASE)),
    ("AUTOMOTIVE", re.compile(r"\b(MOTOR|MOTORS|MOBIL|MOBILITAS|MOTORINDO|AUTOMOTIVE|OTOMOTIF|VEHICLE|CHASSIS|SPAREPART|BAN)\b", re.IGNORECASE)),
    ("CHEMICAL", re.compile(r"\b(CHEMICAL|KIMIA|PLASTIK|PLASTIC|RESIN|CAT|PAINT|PUPUK|PHARMA|FARMASI|OBAT)\b", re.IGNORECASE)),
    ("ELECTRONIC", re.compile(r"\b(ELECTRONIC|ELECTRONICS|ELEKTRONIK|KABEL|CABLE|KOMPONEN|LAMPU|SEMICONDUCTOR)\b", re.IGNORECASE)),
    ("CONSTRUCTION", re.compile(r"\b(CONSTRUCTION|KONSTRUKSI|BUILDING|BUILDINGS|SEMEN|BETON|BAJA|CERAMICS|BANGUNAN)\b", re.IGNORECASE)),
    ("MANUFACTURING", re.compile(r"\b(MANUFACTURING|MANUFACTURE|INDUSTRI|INDUSTRY|INDUSTRIES|PABRIK|FACTORY|PRODUKSI)\b", re.IGNORECASE)),
]


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Menyelaraskan nama kolom input ke standar internal."""
    rename_map = {}
    lower_cols = {str(c).strip().lower(): c for c in df.columns}
    
    for standard_col, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            if alias in lower_cols:
                rename_map[lower_cols[alias]] = standard_col
                break
                
    if rename_map:
        df = df.rename(columns=rename_map)
    return df


def classify_industry(name: str, product: str = "", raw_ind: str = "") -> str:
    """Mengklasifikasikan nama dan konteks perusahaan ke kategori industri."""
    combined = f"{name} {product} {raw_ind}".upper()
    categories = []
    
    for cat_name, pattern in INDUSTRY_PATTERNS:
        if pattern.search(combined):
            categories.append(cat_name)
            
    if not categories:
        return "OTHER"
    return ", ".join(categories)


def recommend_products(category: str) -> str:
    """Merekomendasikan produk merchandise / seragam berdasarkan kategori industri."""
    if not category or category == "OTHER":
        return None
        
    is_textile_garment = "TEXTILE" in category or "GARMENT / APPAREL" in category
    is_mfg = "MANUFACTURING" in category
    is_auto = "AUTOMOTIVE" in category
    is_food = "FOOD / F&B" in category
    is_chem = "CHEMICAL" in category
    is_const = "CONSTRUCTION" in category
    is_elec = "ELECTRONIC" in category
    
    if is_textile_garment:
        if is_mfg:
            return "Jaket, Kaos, Polo Shirt, Seragam, Wearpack"
        return "Jaket, Kaos, Polo Shirt, Seragam"
        
    if is_mfg:
        if is_food:
            return "Jaket, Kaos, Polo Shirt, Seragam, Wearpack"
        return "Jaket, Polo Shirt, Seragam, Wearpack"
        
    if is_auto or is_const:
        return "Jaket, Polo Shirt, Wearpack"
        
    if is_food:
        return "Kaos, Polo Shirt, Seragam"
        
    if is_elec:
        return "Jaket, Polo Shirt, Seragam"
        
    return "Jaket, Polo Shirt, Seragam, Wearpack"


def calculate_sales_score(category: str, phone: str = "", email: str = "", web: str = "", socials: bool = False) -> int:
    """Menghitung skor kelayakan prospek penjualan (0-100)."""
    # Base score by industry relevance
    if "GARMENT / APPAREL" in category or "TEXTILE" in category:
        base = 60
    elif "MANUFACTURING" in category:
        base = 50
    elif "AUTOMOTIVE" in category:
        base = 45
    elif "FOOD / F&B" in category or "CHEMICAL" in category or "ELECTRONIC" in category:
        base = 40
    else:
        base = 30
        
    # Completeness bonus
    bonus = 0
    if phone and str(phone).strip() and str(phone).lower() not in ("nan", "none", "-", ""):
        bonus += 5
    if email and str(email).strip() and str(email).lower() not in ("nan", "none", "-", ""):
        bonus += 10
    if web and str(web).strip() and str(web).lower() not in ("nan", "none", "-", ""):
        bonus += 10
    if socials:
        bonus += 5
        
    total = base + bonus
    return min(100, max(0, total))


def determine_priority(score: int) -> str:
    """Menentukan tier prioritas berdasarkan skor."""
    if score >= 80:
        return "A - HOT"
    if score >= 65:
        return "B - WARM"
    if score >= 50:
        return "C - POTENTIAL"
    return "D - LOW"


def enrich_dataset(df: pd.DataFrame) -> pd.DataFrame:
    """Melakukan proses enrichment menyeluruh terhadap DataFrame."""
    df = normalize_columns(df)
    
    # Pastikan kolom wajib minimal tersedia
    if "nama_perusahaan" not in df.columns:
        first_col = df.columns[0]
        df = df.rename(columns={first_col: "nama_perusahaan"})
        
    total_rows = len(df)
    logger.info(f"Memulai enrichment untuk {total_rows} baris...")
    
    # Siapkan kolom-kolom enrichment
    kategori_list = []
    rekomendasi_list = []
    scores_list = []
    priority_list = []
    status_enrichment_list = []
    
    for _, row in df.iterrows():
        name = str(row.get("nama_perusahaan") or "").strip()
        prod = str(row.get("produk_utama") or "")
        ind = str(row.get("industri") or "")
        phone = str(row.get("telepon") or "")
        email = str(row.get("email") or "")
        web = str(row.get("website") or "")
        
        has_social = bool(
            (row.get("instagram") and str(row.get("instagram")).strip() and str(row.get("instagram")).lower() != "nan") or
            (row.get("facebook") and str(row.get("facebook")).strip() and str(row.get("facebook")).lower() != "nan") or
            (row.get("linkedin") and str(row.get("linkedin")).strip() and str(row.get("linkedin")).lower() != "nan")
        )
        
        # Jika kolom sudah ada sebelumnya (misal file hasil enrichment diunggah kembali), pertahankan atau hitung
        existing_kat = row.get("kategori_industri")
        if pd.notna(existing_kat) and str(existing_kat).strip() != "":
            kat = str(existing_kat).strip()
        else:
            kat = classify_industry(name, prod, ind)
            
        existing_rek = row.get("rekomendasi_produk")
        if pd.notna(existing_rek) and str(existing_rek).strip() != "":
            rek = str(existing_rek).strip()
        else:
            rek = recommend_products(kat)
            
        existing_score = row.get("sales_score")
        if pd.notna(existing_score) and str(existing_score).strip() != "":
            try:
                score = int(float(existing_score))
            except (ValueError, TypeError):
                score = calculate_sales_score(kat, phone, email, web, has_social)
        else:
            score = calculate_sales_score(kat, phone, email, web, has_social)
            
        priority = determine_priority(score)
        
        # Status enrichment
        has_contact = bool(
            (phone and phone.lower() not in ("nan", "none", "-")) or
            (email and email.lower() not in ("nan", "none", "-")) or
            (web and web.lower() not in ("nan", "none", "-"))
        )
        status_enrichment = "Selesai" if has_contact or kat != "OTHER" else "Selesai"
        
        kategori_list.append(kat)
        rekomendasi_list.append(rek)
        scores_list.append(score)
        priority_list.append(priority)
        status_enrichment_list.append(status_enrichment)
        
    df["status_enrichment"] = status_enrichment_list
    df["kategori_industri"] = kategori_list
    df["rekomendasi_produk"] = rekomendasi_list
    df["sales_score"] = scores_list
    df["priority"] = priority_list
    
    if "source" not in df.columns:
        df["source"] = "BPS / Master Data"
        
    logger.info(f"Enrichment selesai untuk {total_rows} baris.")
    return df


def export_to_excel(df: pd.DataFrame, output_path: str) -> str:
    """Mengekspor DataFrame hasil enrichment ke file Excel."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df.to_excel(output_path, index=False, engine="openpyxl")
    return output_path


class BatchSaveResult(int):
    """Hasil operasi batch database yang sepenuhnya kompatibel dengan int.
    
    Menyediakan backward compatibility bagi pemanggil lama (seperti `saved_count == X`),
    sekaligus menyediakan statistik mendalam mengenai pembentukan Master Organization Intelligence,
    penggabungan deduplikasi, kandidat review, dan sinkronisasi compatibility layer.
    """
    def __new__(cls, val, **kwargs):
        obj = super().__new__(cls, val)
        for k, v in kwargs.items():
            setattr(obj, k, v)
        return obj

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_saved": int(self),
            "total_processed": getattr(self, "total_processed", 0),
            "orgs_created": getattr(self, "orgs_created", 0),
            "orgs_updated": getattr(self, "orgs_updated", 0),
            "candidates_flagged": getattr(self, "candidates_flagged", 0),
            "prospects_synced": getattr(self, "prospects_synced", 0),
        }


def save_enriched_to_db_in_batches(
    df: pd.DataFrame,
    raw_data_id: int,
    user_id: int,
    batch_size: int = 250,
    engine: Optional[IdentityResolutionEngine] = None
) -> Tuple[BatchSaveResult, Optional[str]]:
    """Menyimpan hasil enrichment ke database dalam batch/chunk kecil (~250 record)
    menggunakan arsitektur Master Intelligence:
    1. `organizations` adalah Single Source of Truth untuk data profil entitas.
    2. Menggunakan `IdentityResolutionEngine` (Phase 2) untuk mencocokkan sinyal identitas Tier 1-4.
    3. Auto-match digabungkan secara aman & non-destructive via `safe_merge_organization` dengan log audit provenance.
    4. Sinyal ambigu (Tier 4 / konflik lokasi) TIDAK di-merge otomatis, melainkan dicatat ke `duplicate_candidates` (pending review)
       dan entitas master tersendiri dibuat agar data tidak hilang.
    5. Setiap entitas master disinkronisasikan ke `prospects` sebagai transitional compatibility layer
       dengan relasi foreign key `prospects.organization_id = organizations.id`.
    6. Operasi bersifat IDEMPOTENT: penjalanan berulang dengan dataset/raw_data yang sama tidak menimbulkan duplikasi.
    """
    total_rows = len(df)
    total_processed = 0
    orgs_created = 0
    orgs_updated = 0
    candidates_flagged = 0
    prospects_synced = 0
    error_msg = None

    try:
        # Cek foreign key data_sources.id yang valid dari RawData
        valid_data_source_id = None
        if raw_data_id:
            rd = db.session.get(RawData, raw_data_id)
            if rd:
                valid_data_source_id = rd.source_id

        # Inisialisasi engine resolusi identitas jika belum disuplai
        if engine is None:
            existing_orgs = Organization.query.all()
            engine = IdentityResolutionEngine(existing_orgs=existing_orgs)

        # Muat prospect yang sudah ada untuk raw_data_id ini demi menjaga idempotency
        existing_prospects_by_org: Dict[int, Prospect] = {}
        existing_prospects_by_name: Dict[str, Prospect] = {}
        if raw_data_id:
            for p in Prospect.query.filter_by(raw_data_id=raw_data_id).all():
                if p.organization_id:
                    existing_prospects_by_org[p.organization_id] = p
                if p.company_name:
                    existing_prospects_by_name[p.company_name.strip().lower()] = p

        for start_idx in range(0, total_rows, batch_size):
            chunk = df.iloc[start_idx : start_idx + batch_size]
            pending_candidates = []  # List of tuples: (matched_org, incoming_data, match_result)
            pending_prospects = []   # List of tuples: (target_org, incoming_data)

            for _, row in chunk.iterrows():
                raw_name = str(row.get("nama_perusahaan") or "").strip()
                if not raw_name or raw_name.lower() in ("nan", "none", "null", "-", ""):
                    continue

                total_processed += 1
                kat = str(row.get("kategori_industri") or "")[:150]
                kota = str(row.get("kota") or "")
                prov = str(row.get("provinsi") or "")
                alamat = str(row.get("alamat") or "")

                phone = str(row.get("telepon") or "")
                if phone.lower() in ("nan", "none", ""):
                    phone = ""
                elif phone.endswith(".0"):
                    phone = phone[:-2]

                email = str(row.get("email") or "")
                if email.lower() in ("nan", "none", ""):
                    email = ""

                web = str(row.get("website") or "")
                if web.lower() in ("nan", "none", ""):
                    web = ""

                # Ekstraksi akun media sosial jika tersedia di dataset
                ig = str(row.get("instagram") or "").strip()
                if ig.lower() in ("nan", "none", "-", ""):
                    ig = ""

                fb = str(row.get("facebook") or "").strip()
                if fb.lower() in ("nan", "none", "-", ""):
                    fb = ""

                li = str(row.get("linkedin") or "").strip()
                if li.lower() in ("nan", "none", "-", ""):
                    li = ""

                social_dict = {}
                if ig:
                    social_dict["instagram"] = ig
                if fb:
                    social_dict["facebook"] = fb
                if li:
                    social_dict["linkedin"] = li
                social_json_str = json.dumps(social_dict, ensure_ascii=False) if social_dict else None

                rek = str(row.get("rekomendasi_produk") or "")
                if rek.lower() in ("nan", "none", ""):
                    rek = ""

                prio = str(row.get("priority") or "")
                score = int(row.get("sales_score", 0)) if pd.notna(row.get("sales_score")) else 0

                incoming_data = {
                    "name": raw_name,
                    "organization_type": "Perusahaan",
                    "industry": kat or None,
                    "address": alamat or None,
                    "city": kota or None,
                    "province": prov or None,
                    "phone": phone or None,
                    "email": email or None,
                    "website": web or None,
                    "social_json": social_json_str,
                    "product_fit": rek or None,
                    "opportunity_score": score,
                    "priority_tier": prio or None,
                    "source_id": valid_data_source_id,
                    "raw_data_id": raw_data_id,
                    "source_type": "bps_upload",
                    "description": rek or None,
                }

                # Evaluasi sinyal identitas menggunakan IdentityResolutionEngine
                match_res = engine.evaluate_candidate(
                    name=raw_name,
                    website=web,
                    email=email,
                    phone=phone,
                    city=kota,
                    province=prov
                )

                if match_res.decision == "auto_match":
                    target_org = match_res.matched_org
                    is_mod, _ = safe_merge_organization(target_org, incoming_data, match_res)
                    if is_mod:
                        engine.index_organization(target_org)
                    orgs_updated += 1
                    pending_prospects.append((target_org, incoming_data))

                elif match_res.decision == "review_candidate":
                    # Ambigu: JANGAN auto-merge! Buat master entity mandiri & rekam ke duplicate_candidates
                    target_org = create_organization_from_source(incoming_data)
                    db.session.add(target_org)
                    engine.index_organization(target_org)
                    orgs_created += 1

                    pending_candidates.append((match_res.matched_org, incoming_data, match_res))
                    pending_prospects.append((target_org, incoming_data))

                else:  # unmatched
                    target_org = create_organization_from_source(incoming_data)
                    db.session.add(target_org)
                    engine.index_organization(target_org)
                    orgs_created += 1
                    pending_prospects.append((target_org, incoming_data))

            # 1. Flush Organization baru ke DB agar ID terisi untuk relasi anak
            db.session.flush()

            # 2. Rekam entri DuplicateCandidate untuk review manual Business Analyst / Marketing
            for matched_org, inc_data, m_res in pending_candidates:
                if matched_org and matched_org.id:
                    cand = DuplicateCandidate(
                        organization_id=matched_org.id,
                        candidate_name=inc_data["name"][:255],
                        candidate_source=f"raw_data:{raw_data_id}" if raw_data_id else "bps_upload",
                        candidate_payload_json=json.dumps(inc_data, ensure_ascii=False),
                        match_tier=m_res.tier,
                        confidence_score=m_res.confidence,
                        status="pending"
                    )
                    db.session.add(cand)
                    candidates_flagged += 1

            # 3. Sinkronisasikan ke compatibility layer: Prospect (menjaga backward compatibility modul lama)
            # Query prospect yang sudah ada di database untuk organisasi dalam chunk ini (mencegah duplikasi global)
            target_org_ids = [org.id for org, _ in pending_prospects if org and org.id]
            target_org_names = [org.name.strip().lower() for org, _ in pending_prospects if org and org.name]
            if target_org_ids or target_org_names:
                filters = []
                if target_org_ids:
                    filters.append(Prospect.organization_id.in_(target_org_ids))
                if target_org_names:
                    filters.append(db.func.lower(Prospect.company_name).in_(target_org_names))
                db_prospects = Prospect.query.filter(db.or_(*filters)).all()
                for p in db_prospects:
                    if p.organization_id:
                        existing_prospects_by_org[p.organization_id] = p
                    if p.company_name:
                        existing_prospects_by_name[p.company_name.strip().lower()] = p

            new_prospects = []
            for target_org, inc_data in pending_prospects:
                existing_p = (
                    existing_prospects_by_org.get(target_org.id)
                    or existing_prospects_by_name.get(target_org.name.strip().lower())
                )

                region_str = f"{target_org.city or ''}, {target_org.province or ''}".strip(", ") or None
                if region_str:
                    region_str = region_str[:150]

                score_val = target_org.opportunity_score or 0
                prio_val = target_org.priority_tier or ""
                rek_val = target_org.product_fit or ""
                score_reason = f"Priority: {prio_val}. Rekomendasi: {rek_val}".strip(". ") if prio_val or rek_val else None

                if existing_p:
                    existing_p.organization_id = target_org.id
                    existing_p.industry = target_org.industry[:150] if target_org.industry else None
                    existing_p.region = region_str
                    existing_p.website = target_org.website[:255] if target_org.website else None
                    existing_p.contact_phone = target_org.phone[:50] if target_org.phone else None
                    existing_p.contact_email = target_org.email[:150] if target_org.email else None
                    existing_p.description = rek_val[:500] if rek_val else None
                    existing_p.segment = prio_val[:100] if prio_val else None
                    existing_p.score = score_val
                    existing_p.score_reason = score_reason
                else:
                    p = Prospect(
                        company_name=target_org.name[:255],
                        industry=target_org.industry[:150] if target_org.industry else None,
                        region=region_str,
                        website=target_org.website[:255] if target_org.website else None,
                        contact_phone=target_org.phone[:50] if target_org.phone else None,
                        contact_email=target_org.email[:150] if target_org.email else None,
                        description=rek_val[:500] if rek_val else None,
                        segment=prio_val[:100] if prio_val else None,
                        score=score_val,
                        score_reason=score_reason,
                        status="new",
                        raw_data_id=raw_data_id,
                        organization_id=target_org.id,
                        created_by=user_id,
                    )
                    new_prospects.append(p)
                    if target_org.id:
                        existing_prospects_by_org[target_org.id] = p
                    existing_prospects_by_name[target_org.name.strip().lower()] = p

                prospects_synced += 1

            # Simpan seluruh prospek baru dalam satu multi-row INSERT (bulk) per chunk
            if new_prospects:
                db.session.bulk_save_objects(new_prospects)

            # Commit batch chunk (250 record)
            db.session.commit()

    except Exception as e:
        db.session.rollback()
        error_msg = str(e)
        logger.warning(f"Batch insert database error: {e}")

    result = BatchSaveResult(
        prospects_synced,
        total_processed=total_processed,
        orgs_created=orgs_created,
        orgs_updated=orgs_updated,
        candidates_flagged=candidates_flagged,
        prospects_synced=prospects_synced,
    )
    return result, error_msg
