"""Market Size & Market Share Analytics Service.

Menghitung kalkulasi ukuran pasar (TAM, SAM, SOM), pangsa pasar (Market Share),
analisis musiman penjualan (Seasonality), dan simulasi skenario ekspansi bisnis (What-If)
berdasarkan database 8.559 Master Organization dan data riil finansial Syamanah 2026.
"""

from typing import Dict, Any, List, Optional
from sqlalchemy import func, or_
from app.extensions import db
from app.models import Organization

# Data Historis Omzet Riil Syamanah Group Tahun 2026 (Januari - September)
REVENUE_DATA_2026 = [
    {"month": "Jan", "month_name": "Januari", "syamanah": 3549995160, "raffiz": 3505000, "total": 3553500160},
    {"month": "Feb", "month_name": "Februari", "syamanah": 2359850634, "raffiz": 63124997, "total": 2422975631},
    {"month": "Mar", "month_name": "Maret", "syamanah": 1449766169, "raffiz": 30291000, "total": 1480057169},
    {"month": "Apr", "month_name": "April", "syamanah": 2884332833, "raffiz": 79345000, "total": 2963677833},
    {"month": "Mei", "month_name": "Mei", "syamanah": 2926200149, "raffiz": 86125000, "total": 3012325149},
    {"month": "Jun", "month_name": "Juni", "syamanah": 2429591470, "raffiz": 38665000, "total": 2468256470},
    {"month": "Jul", "month_name": "Juli", "syamanah": 4895899812, "raffiz": 46620000, "total": 4942519812},
    {"month": "Ags", "month_name": "Agustus", "syamanah": 3902716690, "raffiz": 56485000, "total": 3959201690},
    {"month": "Sep", "month_name": "September", "syamanah": 4322103455, "raffiz": 46955000, "total": 4369058455},
]

# Matriks Harga Produk Syamanah
PRODUCT_PRICING = {
    "jersey": {
        "name": "Jersey / Teamwear",
        "category": "Olahraga & Komunitas",
        "min_price": 50000,
        "max_price": 150000,
        "median_price": 100000,
        "description": "Custom jersey futsal, basket, running, esport sublimasi penuh"
    },
    "kemeja": {
        "name": "Kemeja (Kerja / PDH / PDL)",
        "category": "Korporat & Instansi",
        "min_price": 170000,
        "max_price": 170000,
        "median_price": 170000,
        "description": "Kemeja drill/tropical seragam kerja kantor, PDH harian, PDL lapangan"
    },
    "polo": {
        "name": "Polo Shirt",
        "category": "Smart Casual & Event",
        "min_price": 120000,
        "max_price": 120000,
        "median_price": 120000,
        "description": "Polo shirt bordir lacoste pique untuk gathering dan seragam santai"
    },
    "jaket": {
        "name": "Jaket (Lapangan / Bomber)",
        "category": "Outerwear & Merchandise",
        "min_price": 285000,
        "max_price": 500000,
        "median_price": 392500,
        "description": "Jaket bomber, jaket parasut lapangan, jaket varsity, dan parka"
    },
}

# Rata-rata belanja seragam per orang per tahun per sektor (dalam Rupiah)
SECTOR_SPEND_PER_PERSON = {
    "perusahaan": 340000,    # 2 stel kemeja kerja/wearpack @ Rp 170.000
    "manufaktur": 340000,    # 2 stel wearpack/baju kerja @ Rp 170.000
    "pendidikan": 290000,    # 1 seragam/almamater (170k) + 1 polo/kaos (120k)
    "mahasiswa": 220000,     # 1 kemeja/PDH organisasi (170k) + 1 jersey/kaos
    "komunitas": 200000,     # 2 pcs jersey olahraga @ Rp 100.000
    "sme_general": 200000,   # 1-2 pcs polo/kemeja
    "default": 280000,       # Blended average (~2 pcs @ Rp 140.000)
}


def get_financial_summary() -> Dict[str, Any]:
    """Mengembalikan ringkasan omzet historis dan proyeksi tahunan Syamanah Group."""
    total_syamanah_9mo = sum(m["syamanah"] for m in REVENUE_DATA_2026)
    total_raffiz_9mo = sum(m["raffiz"] for m in REVENUE_DATA_2026)
    total_group_9mo = total_syamanah_9mo + total_raffiz_9mo
    
    # Rata-rata per bulan
    avg_monthly_group = total_group_9mo / len(REVENUE_DATA_2026)
    avg_monthly_syamanah = total_syamanah_9mo / len(REVENUE_DATA_2026)
    
    # Proyeksi 12 bulan (Annualized Run-Rate 2026)
    projected_annual_group = avg_monthly_group * 12
    projected_annual_syamanah = avg_monthly_syamanah * 12

    # Analisis Peak & Low Month
    sorted_by_total = sorted(REVENUE_DATA_2026, key=lambda x: x["total"], reverse=True)
    peak_month = sorted_by_total[0]
    low_month = sorted_by_total[-1]

    return {
        "monthly_breakdown": REVENUE_DATA_2026,
        "total_syamanah_9mo": total_syamanah_9mo,
        "total_raffiz_9mo": total_raffiz_9mo,
        "total_group_9mo": total_group_9mo,
        "avg_monthly_group": avg_monthly_group,
        "projected_annual_group": projected_annual_group,
        "projected_annual_syamanah": projected_annual_syamanah,
        "peak_month": peak_month,
        "low_month": low_month,
    }


def get_market_size_and_share(custom_avg_spend: Optional[int] = None) -> Dict[str, Any]:
    """Menghitung metrik TAM, SAM, SOM, dan Market Share Syamanah Group."""
    fin = get_financial_summary()
    default_spend = custom_avg_spend or 280000  # Default Rp 280.000 / orang / tahun

    # 1. Total Populasi Pasar dari Database Master Organizations
    total_orgs = Organization.query.count()
    total_people = db.session.query(func.sum(Organization.estimated_members)).scalar() or 0

    # 2. SAM: Tier A + B + C (Segmen Relevan Bernilai Tinggi)
    sam_query = Organization.query.filter(
        Organization.priority_tier.in_(["A - HOT", "Tier A", "B - WARM", "Tier B", "C - POTENTIAL", "Tier C"])
    )
    sam_orgs = sam_query.count()
    sam_people = db.session.query(func.sum(Organization.estimated_members)).filter(
        Organization.priority_tier.in_(["A - HOT", "Tier A", "B - WARM", "Tier B", "C - POTENTIAL", "Tier C"])
    ).scalar() or 0

    # 3. SOM: Tier A + B (Target Inti Hot & Warm dengan Peluang Penutupan Transaksi Tertinggi)
    som_query = Organization.query.filter(
        Organization.priority_tier.in_(["A - HOT", "Tier A", "B - WARM", "Tier B"])
    )
    som_orgs = som_query.count()
    som_people = db.session.query(func.sum(Organization.estimated_members)).filter(
        Organization.priority_tier.in_(["A - HOT", "Tier A", "B - WARM", "Tier B"])
    ).scalar() or 0

    # 4. Nilai Moneter Pasar (Market Value in Rupiah & Pcs Apparel)
    avg_price_per_pcs = 140000  # Rata-rata per helai
    pcs_per_person = round(default_spend / avg_price_per_pcs, 1)

    tam_value_rp = total_people * default_spend
    sam_value_rp = sam_people * default_spend
    som_value_rp = som_people * default_spend

    tam_pcs = int(total_people * pcs_per_person)
    sam_pcs = int(sam_people * pcs_per_person)
    som_pcs = int(som_people * pcs_per_person)

    # 5. Pangsa Pasar (Market Share) Syamanah
    annual_revenue = fin["projected_annual_group"]
    ms_tam_pct = round((annual_revenue / tam_value_rp * 100), 2) if tam_value_rp > 0 else 0.0
    ms_sam_pct = round((annual_revenue / sam_value_rp * 100), 2) if sam_value_rp > 0 else 0.0
    ms_som_pct = round((annual_revenue / som_value_rp * 100), 2) if som_value_rp > 0 else 0.0

    # Sisa Pasar Tak Tergarap di SAM (Unaddressed Potential in SAM)
    unaddressed_sam_rp = max(0, sam_value_rp - annual_revenue)
    unaddressed_sam_pct = round(100.0 - min(100.0, ms_sam_pct), 1)

    # 6. Breakdown Potensi Pasar per Kategori Organisasi
    type_breakdown = []
    types_config = [
        ("Perusahaan", ["Perusahaan", "corporate", "company"], "Korporasi & Bisnis PT", "bi-building", "primary", 340000),
        ("Manufaktur", ["Manufaktur", "manufacturing"], "Pabrik & Industri Manufaktur", "bi-gear-wide-connected", "secondary", 340000),
        ("Pendidikan", ["education", "Pendidikan", "school", "university"], "Sekolah & Perguruan Tinggi", "bi-mortarboard", "info", 290000),
        ("Mahasiswa", ["student_organization", "student_org"], "Organisasi Mahasiswa (BEM/UKM)", "bi-people", "warning", 220000),
        ("Komunitas", ["community", "Komunitas Olahraga", "sports_club", "club", "Komunitas Publik"], "Komunitas Olahraga & Publik", "bi-trophy", "success", 200000),
    ]

    for type_key, type_names, label, icon, color, spend in types_config:
        q = Organization.query.filter(Organization.organization_type.in_(type_names))
        cnt = q.count()
        peop = db.session.query(func.sum(Organization.estimated_members)).filter(Organization.organization_type.in_(type_names)).scalar() or 0
        val = peop * spend
        type_breakdown.append({
            "key": type_key,
            "label": label,
            "icon": icon,
            "color": color,
            "org_count": cnt,
            "people_count": peop,
            "market_value_rp": val,
            "market_value_formatted": f"Rp {val / 1e9:.2f} Miliar",
        })

    # 7. Lanskap Kompetisi & Pangsa Pasar (Competitor Breakdown Model)
    # Model representasi pasar apparel B2B Indonesia
    competitor_landscape = [
        {
            "player": "Syamanah Group (Syamanah + Raffiz)",
            "type": "Leading B2B Custom Apparel",
            "share_pct": ms_tam_pct,
            "revenue_rp": annual_revenue,
            "badge_color": "success",
            "is_syamanah": True,
        },
        {
            "player": "Vendor Apparel / Garmen Nasional Lainnya",
            "type": "Kompetitor Korporat Skala Menengah-Besar",
            "share_pct": 24.5,
            "revenue_rp": tam_value_rp * 0.245,
            "badge_color": "warning",
            "is_syamanah": False,
        },
        {
            "player": "Konveksi Lokal & Penjahit Daerah (Fragmented)",
            "type": "Pemain Tradisional / UMKM Daerah",
            "share_pct": round(100.0 - ms_tam_pct - 24.5, 2),
            "revenue_rp": tam_value_rp * (1.0 - (ms_tam_pct / 100.0) - 0.245),
            "badge_color": "secondary",
            "is_syamanah": False,
        },
    ]

    return {
        "tam": {
            "value_rp": tam_value_rp,
            "people": total_people,
            "orgs": total_orgs,
            "pcs": tam_pcs,
            "label": "Total Addressable Market (TAM)",
            "description": "Total seluruh potensi pasar seragam & custom apparel dari 8.559 organisasi master terdata di Indonesia.",
        },
        "sam": {
            "value_rp": sam_value_rp,
            "people": sam_people,
            "orgs": sam_orgs,
            "pcs": sam_pcs,
            "label": "Serviceable Addressable Market (SAM)",
            "description": "Pasar yang relevan dengan lini produk Syamanah (Tier A, Tier B, Tier C yang memiliki kebutuhan apparel tinggi).",
        },
        "som": {
            "value_rp": som_value_rp,
            "people": som_people,
            "orgs": som_orgs,
            "pcs": som_pcs,
            "label": "Serviceable Obtainable Market (SOM)",
            "description": "Pasar sasaran jangka pendek Syamanah (Tier A & B Hot/Warm Leads yang memiliki kontak dan peluang penutupan transaksi tertinggi).",
        },
        "market_share": {
            "vs_som_pct": ms_som_pct,
            "vs_sam_pct": ms_sam_pct,
            "vs_tam_pct": ms_tam_pct,
            "annual_projected_revenue": annual_revenue,
            "actual_9mo_revenue": fin["total_group_9mo"],
            "unaddressed_sam_rp": unaddressed_sam_rp,
            "unaddressed_sam_pct": unaddressed_sam_pct,
        },
        "financials": fin,
        "pricing": PRODUCT_PRICING,
        "type_breakdown": type_breakdown,
        "competitor_landscape": competitor_landscape,
        "assumptions": {
            "spend_per_person": default_spend,
            "avg_price_per_pcs": avg_price_per_pcs,
            "pcs_per_person": pcs_per_person,
        }
    }


def simulate_expansion(additional_tier_c_pct: float = 5.0, price_change_pct: float = 0.0) -> Dict[str, Any]:
    """Simulasi skenario bisnis (What-If Analysis):
    Berapa potensi kenaikan omzet jika Syamanah menambah penetrasi di Tier C sebesar X%?
    """
    tier_c_people = db.session.query(func.sum(Organization.estimated_members)).filter(
        Organization.priority_tier.in_(["C - POTENTIAL", "Tier C"])
    ).scalar() or 0
    tier_c_orgs = Organization.query.filter(
        Organization.priority_tier.in_(["C - POTENTIAL", "Tier C"])
    ).count()

    base_spend = 280000 * (1.0 + (price_change_pct / 100.0))
    tier_c_total_market = tier_c_people * base_spend

    # Nilai tambahan omzet yang bisa diraih
    additional_revenue = tier_c_total_market * (additional_tier_c_pct / 100.0)
    additional_people_served = int(tier_c_people * (additional_tier_c_pct / 100.0))
    additional_orgs_served = int(tier_c_orgs * (additional_tier_c_pct / 100.0))

    fin = get_financial_summary()
    current_annual = fin["projected_annual_group"]
    new_annual_projected = current_annual + additional_revenue
    growth_pct = round((additional_revenue / current_annual * 100), 2) if current_annual > 0 else 0.0

    return {
        "additional_tier_c_pct": additional_tier_c_pct,
        "price_change_pct": price_change_pct,
        "tier_c_total_market": tier_c_total_market,
        "additional_revenue": additional_revenue,
        "additional_people_served": additional_people_served,
        "additional_orgs_served": additional_orgs_served,
        "current_annual_revenue": current_annual,
        "new_annual_projected": new_annual_projected,
        "growth_pct": growth_pct,
    }
