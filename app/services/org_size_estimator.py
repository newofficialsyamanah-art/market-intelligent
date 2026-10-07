"""Organization Member & Employee Size Estimator & Enrichment Service.

Menyediakan:
1. Rule-based heuristic estimation untuk inisialisasi baseline cepat 8.000+ organisasi (Phase 1).
2. Helper regex & parser untuk mengekstraksi data aktual dari web/LinkedIn (Phase 2).
3. Pemisahan tegas data 'estimated' (baseline) vs 'actual' (aktual terverifikasi).
"""

import re
import logging
from typing import Optional, Dict, Any, Tuple
from app.extensions import db
from app.models import Organization

logger = logging.getLogger(__name__)

# Pattern regex untuk ekstraksi headcount aktual dari web text / meta description
HEADCOUNT_TEXT_PATTERNS = [
    # Contoh: "memiliki lebih dari 500 karyawan", "didukung oleh 1.250 staf"
    re.compile(r"(?:memiliki|didukung oleh|dengan|sekitar|lebih dari|mencakup|total)\s+([0-9]{1,3}(?:[.,][0-9]{3})*|[0-9]+)\s*(?:orang\s+)?(karyawan|pegawai|pekerja|staf|karyawan tetap|tenaga kerja|staf profesional)", re.IGNORECASE),
    # Contoh: "500+ employees", "1,200 employees", "over 300 staff"
    re.compile(r"(?:over|more than|approximately|about|around)?\s*([0-9]{1,3}(?:[.,][0-9]{3})*|[0-9]+)\+?\s*(employees|staff|workers|team members)", re.IGNORECASE),
    # Contoh untuk komunitas & pendidikan: "800 siswa", "15.000 mahasiswa", "120 anggota aktif"
    re.compile(r"([0-9]{1,3}(?:[.,][0-9]{3})*|[0-9]+)\s*(?:orang\s+)?(siswa|peserta didik|mahasiswa|anggota|member|anggota aktif)", re.IGNORECASE),
]


def determine_tier_from_number(num: int) -> str:
    """Mengonversi jumlah numerik ke format string tier rentang."""
    if num <= 10:
        return "1-10"
    elif num <= 50:
        return "11-50"
    elif num <= 200:
        return "51-200"
    elif num <= 500:
        return "201-500"
    elif num <= 1000:
        return "501-1000"
    else:
        return "1000+"


def parse_actual_headcount(text: str) -> Optional[Tuple[int, str]]:
    """Mengekstrak angka headcount aktual dan rentang tier dari string teks web."""
    if not text:
        return None

    for pattern in HEADCOUNT_TEXT_PATTERNS:
        match = pattern.search(text)
        if match:
            raw_num = match.group(1).replace(".", "").replace(",", "")
            try:
                num = int(raw_num)
                # Hindari false positive angka tahun (2018-2030) jika berkaitan dengan kalender/akademik
                if 2018 <= num <= 2030:
                    snippet = text[max(0, match.start() - 25):min(len(text), match.end() + 25)].lower()
                    if any(w in snippet for w in ["tahun", "thn", "angkatan", "periode", "wisuda", "kalender", "ajaran", "ta."]):
                        continue

                # Filter out outlier yang tidak masuk akal (misal nomor telepon atau nilai kecil < 5)
                if 5 <= num <= 200000:
                    tier = determine_tier_from_number(num)
                    return num, tier
            except ValueError:
                continue
    return None


def calculate_baseline_estimate(org: Organization) -> Dict[str, Any]:
    """Menghitung estimasi realistis berbasis aturan industri dan tipe organisasi Indonesia."""
    name_upper = (org.name or "").upper()
    org_type_lower = (org.organization_type or "").lower()
    industry_upper = (org.industry or "").upper()
    subtype_lower = (org.organization_subtype or "").lower()
    sport_lower = (org.sport or "").lower()

    # 1. PENDIDIKAN TINGGI (Universitas / Institut / Politeknik / Akademi)
    higher_ed_keywords = ["UNIVERSITAS", "INSTITUT", "POLITEKNIK", "AKADEMI", "STIKES", "SEKOLAH TINGGI", "IAIN", "UIN"]
    if any(k in name_upper for k in higher_ed_keywords) or any(k in subtype_lower for k in ["university", "college", "kampus"]):
        return {
            "estimated_members": 3500,
            "employee_size": "1000+",
            "size_status": "estimated",
            "size_source": "baseline_higher_education"
        }

    # 2. SEKOLAH MENENGAH (SMA / SMK / MAN / High School)
    high_school_keywords = ["SMK", "SMA", "MAN ", "SEKOLAH MENENGAH", "HIGH SCHOOL"]
    if any(k in name_upper for k in high_school_keywords) or any(k in subtype_lower for k in ["sma", "smk", "high_school"]):
        return {
            "estimated_members": 750,
            "employee_size": "501-1000",
            "size_status": "estimated",
            "size_source": "baseline_high_school"
        }

    # 3. PENDIDIKAN DASAR & PESANTREN (SMP / MTS / SD / Pesantren / Yayasan Pendidikan)
    school_keywords = ["SMP", "MTS", "SEKOLAH DASAR", "PESANTREN", "PONDOK", "YAYASAN PENDIDIKAN"]
    if org_type_lower == "education" or any(k in name_upper for k in school_keywords):
        return {
            "estimated_members": 350,
            "employee_size": "201-500",
            "size_status": "estimated",
            "size_source": "baseline_school_general"
        }

    # 4. ORGANISASI MAHASISWA (BEM, Himpunan, UKM, DPM, Senat)
    student_keywords = ["BEM", "HIMPUNAN", "UKM", "SENAT", "MAHASISWA", "DEWAN MAHASISWA"]
    if "student" in org_type_lower or any(k in name_upper for k in student_keywords):
        return {
            "estimated_members": 80,
            "employee_size": "51-200",
            "size_status": "estimated",
            "size_source": "baseline_student_org"
        }

    # 5. KOMUNITAS & OLAHRAGA
    if "community" in org_type_lower or "komunitas" in org_type_lower or org_type_lower == "club" or sport_lower:
        if any(r in name_upper or r in sport_lower for r in ["RUN", "LARI", "GOWES", "SEPEDA", "CYCLING", "MARATHON"]):
            return {
                "estimated_members": 120,
                "employee_size": "51-200",
                "size_status": "estimated",
                "size_source": "baseline_sports_running_cycling"
            }
        elif any(t in name_upper or t in sport_lower for t in ["FUTSAL", "FOOTBALL", "SEPAK BOLA", "BASKET", "VOLI", "BADMINTON", "ESPORTS"]):
            return {
                "estimated_members": 35,
                "employee_size": "11-50",
                "size_status": "estimated",
                "size_source": "baseline_sports_team"
            }
        return {
            "estimated_members": 50,
            "employee_size": "11-50",
            "size_status": "estimated",
            "size_source": "baseline_community_general"
        }

    # 6. PERUSAHAAN BESAR / TBK / BUMN / HOLDING / MULTINASIONAL
    enterprise_keywords = ["TBK", "PERSERO", "HOLDING", "GROUP", "CORPORATION", "INDONESIA TBK", "BUMN", "MULTINASIONAL"]
    if any(k in name_upper for k in enterprise_keywords):
        return {
            "estimated_members": 1500,
            "employee_size": "1000+",
            "size_status": "estimated",
            "size_source": "baseline_enterprise_tbk"
        }

    # 7. MANUFAKTUR / PABRIK / INDUSTRI BERAT / TEKSTIL / GARMENT / OTOMOTIF
    manuf_keywords = ["MANUFACTURING", "TEXTILE", "GARMENT", "GARMINDO", "AUTOMOTIVE", "PABRIK", "INDUSTRI", "SEMEN", "CHEMICAL", "MINING", "TAMBANG", "KONVEKSI", "STEEL", "PLASTIC", "KIMIA", "PRODUKSI"]
    if any(m in industry_upper for m in ["MANUFACTURING", "TEXTILE", "GARMENT", "AUTOMOTIVE", "CHEMICAL"]) or any(m in name_upper for m in manuf_keywords) or org_type_lower == "manufaktur":
        return {
            "estimated_members": 350,
            "employee_size": "201-500",
            "size_status": "estimated",
            "size_source": "baseline_manufacturing"
        }

    # 8. PERUSAHAAN PERSEROAN TERBATAS (PT) STANDARD
    is_pt = bool(re.search(r"\bPT\b|PT\.|\.PT|,PT|\(PT\)", name_upper))
    if is_pt:
        # Jika priority tier HOT atau score tinggi, perusahaan menengah-besar
        if (org.opportunity_score or 0) >= 70 or org.priority_tier == "A - HOT":
            return {
                "estimated_members": 150,
                "employee_size": "51-200",
                "size_status": "estimated",
                "size_source": "baseline_corporate_pt_tier_a"
            }
        return {
            "estimated_members": 80,
            "employee_size": "51-200",
            "size_status": "estimated",
            "size_source": "baseline_corporate_pt"
        }

    # 9. CV / UD / TOKO / AGEN / DISTRIBUTOR / UMKM
    is_sme = bool(re.search(r"\bCV\b|CV\.|\.CV|,CV|\(CV\)|\bUD\b|UD\.|\.UD|,UD|\bPD\b", name_upper))
    sme_keywords = ["TOKO", "AGEN", "DISTRIBUTOR", "BENGKEL", "KATERING", "PERCETAKAN", "WARUNG"]
    if is_sme or any(k in name_upper for k in sme_keywords):
        return {
            "estimated_members": 25,
            "employee_size": "11-50",
            "size_status": "estimated",
            "size_source": "baseline_sme_cv"
        }

    # 10. DEFAULT OTHER / GENERAL CORPORATE
    if (org.opportunity_score or 0) >= 60:
        return {
            "estimated_members": 60,
            "employee_size": "51-200",
            "size_status": "estimated",
            "size_source": "baseline_general_priority"
        }

    return {
        "estimated_members": 30,
        "employee_size": "11-50",
        "size_status": "estimated",
        "size_source": "baseline_general"
    }


def populate_baseline_estimates(limit: Optional[int] = None, overwrite_estimated: bool = True) -> Dict[str, Any]:
    """Mengisi baseline estimasi untuk organisasi yang belum memiliki estimasi atau masih berstatus 'estimated'.
    PENTING: Tidak pernah menimpa organisasi yang sudah berstatus 'actual'!
    """
    query = Organization.query

    if not overwrite_estimated:
        # Hanya organisasi yang estimated_members masih NULL
        query = query.filter(Organization.estimated_members.is_(None))
    else:
        # Organisasi yang belum actual (NULL atau 'estimated')
        query = query.filter(db.or_(Organization.size_status.is_(None), Organization.size_status != "actual"))

    if limit:
        query = query.limit(limit)

    total_candidates = query.count()
    logger.info(f"Memulai inisialisasi baseline size untuk {total_candidates} organisasi...")

    updated_count = 0
    batch_size = 500
    last_id = 0

    while True:
        subquery = Organization.query.filter(Organization.id > last_id)
        if not overwrite_estimated:
            subquery = subquery.filter(Organization.estimated_members.is_(None))
        else:
            subquery = subquery.filter(db.or_(Organization.size_status.is_(None), Organization.size_status != "actual"))

        orgs = subquery.order_by(Organization.id.asc()).limit(batch_size).all()
        if not orgs:
            break

        for org in orgs:
            last_id = org.id
            if org.size_status == "actual":
                continue

            baseline = calculate_baseline_estimate(org)
            org.estimated_members = baseline["estimated_members"]
            org.employee_size = baseline["employee_size"]
            org.size_status = "estimated"
            org.size_source = baseline["size_source"]
            updated_count += 1

            if limit and updated_count >= limit:
                break

        db.session.commit()
        logger.info(f"Baseline progress: {updated_count}/{total_candidates} diproses...")

        if limit and updated_count >= limit:
            break

    return {
        "total_candidates": total_candidates,
        "updated_count": updated_count,
        "status": "success"
    }
