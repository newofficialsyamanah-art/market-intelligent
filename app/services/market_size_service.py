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

# Data Riset Pasar Eksternal E-Commerce Nasional (Berdasarkan Laporan Market Intelligence 17 Halaman)
PDF_BENCHMARK_DATA = {
    "report_period": "30 Hari Terakhir (Februari - Maret 2026)",
    "menswear_macro": {
        "title": "Menswear & Pakaian Pria Nasional",
        "market_size_monthly_rp": 2342900000000,
        "market_size_formatted": "Rp 2.342,9 Miliar (Rp 2,34 Triliun)",
        "annual_projected_rp": 28114800000000,
        "sellers_count": 27526,
        "avg_revenue_per_store": 85100000,
        "fashion_market_share_pct": 9.0,
        "highlight": "Kategori pakaian pria menyumbang 9% dari total belanja fashion di platform digital Indonesia."
    },
    "jersey": {
        "title": "Professional Sports Clothing (Jersey)",
        "market_size_monthly_rp": 51900000000,
        "market_size_formatted": "Rp 51,9 Miliar / bulan",
        "annual_projected_rp": 622800000000,
        "sellers_count": 1999,
        "avg_store_revenue": 25900000,
        "layer_hierarchy": [
            {"layer": "Layer 1", "category": "Sports & Outdoor Apparel", "monthly_rp": 548500000000, "share_pct": 100.0},
            {"layer": "Layer 2", "category": "Sports Clothing (Pakaian Olahraga)", "monthly_rp": 182700000000, "share_pct": 33.3},
            {"layer": "Layer 3", "category": "Professional Sports Clothing (Jersey)", "monthly_rp": 51900000000, "share_pct": 9.46}
        ],
        "top_sellers": [
            {"rank": 1, "shop_name": "SUPER MURAH23", "monthly_rev": 3100000000, "share_pct": 6.0, "volume_pcs": 41900, "avg_price": 74600, "badge": "Volume Leader"},
            {"rank": 2, "shop_name": "SIKOCY OLSHOP", "monthly_rev": 3000000000, "share_pct": 5.8, "volume_pcs": 27600, "avg_price": 108600, "badge": "Mid-Range"},
            {"rank": 3, "shop_name": "Erspo Store (Official)", "monthly_rev": 3000000000, "share_pct": 5.8, "volume_pcs": 11600, "avg_price": 257600, "badge": "Official Timnas"},
            {"rank": 4, "shop_name": "gudangkaos tangerang", "monthly_rev": 2800000000, "share_pct": 5.4, "volume_pcs": 35000, "avg_price": 80000, "badge": "Fast Seller"},
            {"rank": 5, "shop_name": "Kolorzsport", "monthly_rev": 2600000000, "share_pct": 5.0, "volume_pcs": 28000, "avg_price": 92800, "badge": "Sportswear"},
            {"rank": 6, "shop_name": "Top Jersey ID", "monthly_rev": 2100000000, "share_pct": 4.0, "volume_pcs": 21000, "avg_price": 100000, "badge": "Futsal/Bola"},
            {"rank": 7, "shop_name": "Sportivo Apparel", "monthly_rev": 1900000000, "share_pct": 3.7, "volume_pcs": 18000, "avg_price": 105500, "badge": "Jersey Club"},
            {"rank": 8, "shop_name": "Garuda Jersey", "monthly_rev": 1500000000, "share_pct": 2.9, "volume_pcs": 16000, "avg_price": 93750, "badge": "Sublimasi"},
            {"rank": 9, "shop_name": "Champion Sportswear", "monthly_rev": 1300000000, "share_pct": 2.5, "volume_pcs": 14000, "avg_price": 92800, "badge": "Running/Badminton"},
            {"rank": 10, "shop_name": "Prima Jersey", "monthly_rev": 1200000000, "share_pct": 2.3, "volume_pcs": 12000, "avg_price": 100000, "badge": "Komunitas"}
        ],
        "top_10_share_pct": 39.5,
        "price_segments": [
            {"tier": "Budget (< Rp 50.000)", "share_pct": 21.6, "monthly_val": 11200000000, "status": "Jersey Polos / Sablon Standar"},
            {"tier": "Mid-Range (Rp 50.000 - Rp 100.000)", "share_pct": 27.6, "monthly_val": 14300000000, "status": "Jersey Printing Standar"},
            {"tier": "Sweet Spot Premium (Rp 100.000 - Rp 200.000)", "share_pct": 45.07, "monthly_val": 23400000000, "status": "Sublimasi Premium Syamanah (Zona Terbesar)", "is_syamanah": True},
            {"tier": "Luxury / Authentic (> Rp 200.000)", "share_pct": 5.73, "monthly_val": 3000000000, "status": "Authentic Player Issue (Erspo)"}
        ],
        "channels": {
            "video_pct": 49.9,
            "live_pct": 36.8,
            "mall_pct": 13.3,
            "dominant_traffic": "Affiliate Content Creator (68% omzet disumbang oleh video affiliate)"
        },
        "syamanah_benchmark": {
            "monthly_rev_rp": 3240000000,
            "equivalent_rank": "Rank 1 Nasional (Sejajar dengan Super Murah23 & Erspo)",
            "competitive_edge": "Full Custom Design B2B, Bebas Minimal Order Komunitas, Sublimasi Anti Luntur High Durability",
            "price_match": "Rentang Syamanah Rp 50.000 - Rp 150.000 tepat menguasai 72,6% pangsa pasar konsumen (Mid-Range + Sweet Spot Premium)."
        }
    },
    "jaket": {
        "title": "Jackets & Coats (Outerwear Pria & Wanita)",
        "market_size_monthly_rp": 187600000000,
        "market_size_formatted": "Rp 187,6 Miliar / bulan",
        "annual_projected_rp": 2251200000000,
        "sellers_count": 4123,
        "gender_split": [
            {"segment": "Jaket Pria (Men Jackets)", "monthly_rp": 131200000000, "share_pct": 69.9},
            {"segment": "Jaket Wanita (Women Jackets)", "monthly_rp": 56400000000, "share_pct": 30.1}
        ],
        "top_sellers": [
            {"rank": 1, "shop_name": "Dobujack Official", "monthly_rev": 12600000000, "share_pct": 9.6, "avg_price": 285000, "badge": "Market Leader"},
            {"rank": 2, "shop_name": "Screamous Official", "monthly_rev": 4100000000, "share_pct": 3.1, "avg_price": 320000, "badge": "Distro Streetwear"},
            {"rank": 3, "shop_name": "3SECOND Men Official", "monthly_rev": 2000000000, "share_pct": 1.5, "avg_price": 389000, "badge": "Mall Retail Brand"},
            {"rank": 4, "shop_name": "Geoff Max Apparel", "monthly_rev": 1800000000, "share_pct": 1.4, "avg_price": 275000, "badge": "Youth Lifestyle"},
            {"rank": 5, "shop_name": "Roughneck 1991", "monthly_rev": 1600000000, "share_pct": 1.2, "avg_price": 290000, "badge": "Outdoor & Casual"}
        ],
        "sweet_spot": "Rp 200.000 - Rp 400.000 (Menyumbang nilai pasar terbesar Rp 28,2 Miliar)",
        "channels": {
            "video_pct": 55.0,
            "live_pct": 32.0,
            "mall_pct": 13.0,
            "dominant_traffic": "Short Video Showcasing (Bahan anti air / windproof & fitting)"
        },
        "syamanah_benchmark": {
            "pricing_range": "Rp 285.000 - Rp 500.000 (Median Rp 392.500)",
            "positioning": "Premium Institutional Outerwear (Bomber korporat, Jaket Lapangan Tambang/Proyek, Varsity kampus)",
            "competitive_edge": "Material water-repellent kualitas industri, furing quilting adem, bordir komputer presisi instansi."
        }
    },
    "seragam": {
        "title": "Workwear & Uniforms (Seragam Kerja & Sekolah)",
        "market_size_monthly_rp": 19600000000,
        "market_size_formatted": "Rp 19,6 Miliar / bulan",
        "annual_projected_rp": 235200000000,
        "sellers_count": 1692,
        "segments": [
            {"category": "Seragam Kerja Wanita", "monthly_rp": 10900000000, "share_pct": 55.6, "dominant_channel": "Live Streaming (51,4%)"},
            {"category": "Seragam Kerja Pria", "monthly_rp": 7300000000, "share_pct": 37.2, "dominant_channel": "Live & Video (38,0%)"},
            {"category": "Seragam Sekolah Laki-laki", "monthly_rp": 941800000, "share_pct": 4.8, "dominant_channel": "Mall / Katalog (35,1%)"},
            {"category": "Seragam Sekolah Perempuan", "monthly_rp": 443200000, "share_pct": 2.3, "dominant_channel": "Mall / Katalog (34,0%)"}
        ],
        "top_sellers": [
            {"rank": 1, "shop_name": "Home of Stesis (Batik & Blazer)", "monthly_rev": 997000000, "category": "Seragam Kerja Wanita", "badge": "Top Wanita"},
            {"rank": 2, "shop_name": "3RZCollection (PDH/PNS/Medis)", "monthly_rev": 736000000, "category": "Seragam Kerja Pria & Wanita", "badge": "PNS & Medis"},
            {"rank": 3, "shop_name": "Agen Sepatu & Seragam Bandung", "monthly_rev": 408000000, "category": "Seragam Pria & Satpam", "badge": "PDL & Safari"},
            {"rank": 4, "shop_name": "Kemeja Tactical ID", "monthly_rev": 365000000, "category": "Kemeja PDL Lapangan", "badge": "Tactical"},
            {"rank": 5, "shop_name": "Seragam Nusantara", "monthly_rev": 290000000, "category": "Seragam Sekolah & Guru", "badge": "Sekolah"}
        ],
        "sweet_spot": "Rp 140.000 - Rp 220.000 (Kemeja Syamanah di Rp 170.000 tepat di tengah rentang optimal)",
        "channels": {
            "live_pct": 51.4,
            "video_pct": 28.6,
            "mall_pct": 20.0,
            "insight": "Seragam kerja wanita sangat dipengaruhi Live Streaming (fitting detail, jatuh kain, dan tes ukuran badan)."
        },
        "syamanah_benchmark": {
            "monthly_rev_rp": 3240000000,
            "comparison_multiplier": "4,4x lebih besar dari No. 1 Retail Online (Home of Stesis / 3RZCollection)",
            "why_syamanah_wins": "Model Bisnis B2B Institusi vs Retail B2C. Retailer e-commerce melayani eceran 1-2 stel, sedangkan Syamanah melayani kontrak pengadaan ratusan hingga ribuan pcs per PO korporat dengan nilai kontrak Rp 50Jt - Rp 500Jt+ per transaksi."
        }
    }
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
        "benchmarks": PDF_BENCHMARK_DATA,
        "assumptions": {
            "spend_per_person": default_spend,
            "avg_price_per_pcs": avg_price_per_pcs,
            "pcs_per_person": pcs_per_person,
        }
    }


def get_syamanah_benchmark_report() -> Dict[str, Any]:
    """Mengembalikan data komprehensif Market Size & Market Share Versi Syamanah
    yang membandingkan realitas internal finansial & 8.559 organisasi dengan data benchmark nasional PDF.
    """
    data = get_market_size_and_share()
    return {
        **data,
        "report_generated_date": "Oktober 2026",
        "company_name": "Syamanah Group",
        "brands": ["Syamanah Apparel (B2B)", "Raffiz (Retail & Quick Order)"],
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
