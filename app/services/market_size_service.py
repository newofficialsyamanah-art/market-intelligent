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

# Data Riset Lanskap Industri Garmen & Konveksi B2B Kustom Nasional
# Berbasis riset vendor institusional, pengadaan seragam korporat, dan ekosistem B2B custom apparel di Indonesia.
B2B_BENCHMARK_DATA = {
    "report_period": "Lanskap Pasar B2B Kustom & Institusi Nasional 2026",
    "b2b_macro": {
        "title": "Pasar Pengadaan Apparel & Seragam B2B Nasional",
        "market_size_monthly_rp": 385000000000,
        "market_size_formatted": "Rp 385,0 Miliar / bulan (Rp 4,62 Triliun / thn)",
        "annual_projected_rp": 4620000000000,
        "org_clients_count": 8559,
        "avg_spend_per_org": 45000000,
        "highlight": "Pasar B2B didorong oleh kontrak pengadaan kemeja PDH/PDL korporat, seragam pabrik/tambang, almamater kampus, dan jersey kustom komunitas."
    },
    "jersey": {
        "title": "Jersey & Teamwear Kustom B2B (Sublimasi Komunitas, Klub & Korporat)",
        "market_size_monthly_rp": 42500000000,
        "market_size_formatted": "Rp 42,5 Miliar / bulan",
        "annual_projected_rp": 510000000000,
        "b2b_players_count": 850,
        "avg_store_revenue": 50000000,
        "layer_hierarchy": [
            {"layer": "Layer 1", "category": "Pasar Apparel Olahraga & Komunitas B2B", "monthly_rp": 120000000000, "share_pct": 100.0},
            {"layer": "Layer 2", "category": "Kustom Jersey Tim & Organisasi (Made-to-Order)", "monthly_rp": 65000000000, "share_pct": 54.2},
            {"layer": "Layer 3", "category": "Full Sublimation Premium Jersey (Syamanah Core)", "monthly_rp": 42500000000, "share_pct": 35.4}
        ],
        "top_sellers": [
            {
                "rank": 1,
                "shop_name": "Regarsport (PT Regarsport Industri Indonesia)",
                "monthly_rev": 4500000000,
                "share_pct": 10.6,
                "avg_price": 115000,
                "badge": "Pabrik Sublimasi Industri",
                "sales_channels": ["Website Resmi", "Jaringan Agen B2B", "Direct Order"],
                "store_name": "Website Resmi",
                "store_url": "https://regarsport.net/",
                "social_platform": "Instagram",
                "social_handle": "@regarsport",
                "social_url": "https://www.instagram.com/regarsport/",
                "procurement_model": "Jaringan Kemitraan & Agen B2B Se-Indonesia"
            },
            {
                "rank": 2,
                "shop_name": "Narrow Indonesia (Narrow Apparel)",
                "monthly_rev": 2200000000,
                "share_pct": 5.2,
                "avg_price": 135000,
                "badge": "Spesialis Klub & Komunitas",
                "sales_channels": ["Website Portofolio", "WhatsApp Sales", "Instagram"],
                "store_name": "Website Resmi",
                "store_url": "https://narrowindonesia.com/",
                "social_platform": "Instagram",
                "social_handle": "@narrowindonesia",
                "social_url": "https://www.instagram.com/narrowindonesia/",
                "procurement_model": "Direct Order Komunitas & Klub Sepakbola/Futsal"
            },
            {
                "rank": 3,
                "shop_name": "Total Apparel (PT Total Solusi Apparel)",
                "monthly_rev": 1800000000,
                "share_pct": 4.2,
                "avg_price": 125000,
                "badge": "Running & Event Apparel",
                "sales_channels": ["Website Resmi", "Katalog Korporat", "WhatsApp"],
                "store_name": "Website Resmi",
                "store_url": "https://totalapparel.id/",
                "social_platform": "Instagram",
                "social_handle": "@totalapparel.id",
                "social_url": "https://www.instagram.com/totalapparel.id/",
                "procurement_model": "Vendor Event Olahraga, Marathon & Gathering"
            },
            {
                "rank": 4,
                "shop_name": "Vendor Jersey (PT Garuda Promosindo)",
                "monthly_rev": 1400000000,
                "share_pct": 3.3,
                "avg_price": 110000,
                "badge": "Workshop Sublimasi B2B",
                "sales_channels": ["Website Profil", "WhatsApp Tender", "Workshop"],
                "store_name": "Website Resmi",
                "store_url": "https://www.vendorjersey.com/",
                "social_platform": "Instagram",
                "social_handle": "@vendorjersey",
                "social_url": "https://www.instagram.com/vendorjersey/",
                "procurement_model": "Kustom Jersey Printing Instansi & Turnamen"
            },
            {
                "rank": 5,
                "shop_name": "Kostum Bola (CV Multi Kreasi Apparel)",
                "monthly_rev": 1200000000,
                "share_pct": 2.8,
                "avg_price": 115000,
                "badge": "Custom Jersey Tim",
                "sales_channels": ["Website Resmi", "WhatsApp Sales"],
                "store_name": "Website Resmi",
                "store_url": "https://www.kostumbola.com/",
                "social_platform": "Instagram",
                "social_handle": "@kostumbolacom",
                "social_url": "https://www.instagram.com/kostumbolacom/",
                "procurement_model": "Kostum Tim Olahraga Korporat & Kampus"
            }
        ],
        "top_10_share_pct": 32.5,
        "price_segments": [
            {"tier": "Jersey Standar Sablon (< Rp 75.000)", "share_pct": 18.5, "monthly_val": 7860000000, "status": "Bahan Serena/Dryfit Sablon Manual"},
            {"tier": "Sublimasi Printing Standar (Rp 75.000 - Rp 100.000)", "share_pct": 28.5, "monthly_val": 12110000000, "status": "Dryfit Milano/Bintik Sublimasi Separasi"},
            {"tier": "Sweet Spot Premium Syamanah (Rp 100.000 - Rp 150.000)", "share_pct": 42.0, "monthly_val": 17850000000, "status": "Full Custom Sublim Anti-Luntur High Durability", "is_syamanah": True},
            {"tier": "Authentic Pro Team / Export (> Rp 150.000)", "share_pct": 11.0, "monthly_val": 4675000000, "status": "Jersey Player Issue Material Impor"}
        ],
        "channels": {
            "b2b_direct_pct": 52.0,
            "referral_agent_pct": 33.0,
            "tender_event_pct": 15.0,
            "dominant_traffic": "Direct Sales WhatsApp & Portofolio Instagram/Web Institusi"
        },
        "syamanah_benchmark": {
            "monthly_rev_rp": 3240000000,
            "equivalent_rank": "Pemain Papan Atas B2B Sublimasi (Kapital & Fasilitas Mandiri)",
            "competitive_edge": "Full Custom Design B2B Gratis, Bebas Minimal Order Komunitas, Sublimasi Mesin Industri EPSON Anti-Luntur.",
            "price_match": "Rentang harga Syamanah Rp 50.000 - Rp 150.000 menguasai 88,5% kebutuhan tender komunitas dan korporasi."
        }
    },
    "jaket": {
        "title": "Jaket Korporat, Lapangan & Varsity B2B (Institutional Outerwear)",
        "market_size_monthly_rp": 85000000000,
        "market_size_formatted": "Rp 85,0 Miliar / bulan",
        "annual_projected_rp": 1020000000000,
        "b2b_players_count": 620,
        "top_sellers": [
            {
                "rank": 1,
                "shop_name": "Bikin-Baju.com (PT Bandung Garmen Solusindo)",
                "monthly_rev": 3800000000,
                "share_pct": 4.5,
                "avg_price": 275000,
                "badge": "Vendor Jaket Korporat & BUMN",
                "sales_channels": ["Website Profil", "WhatsApp Tender", "Instagram"],
                "store_name": "Website Resmi",
                "store_url": "https://bikin-baju.com/",
                "social_platform": "Instagram",
                "social_handle": "@bikinbajudotcom",
                "social_url": "https://www.instagram.com/bikinbajudotcom/",
                "procurement_model": "Vendor Resmi Pengadaan Jaket Kantor & BUMN"
            },
            {
                "rank": 2,
                "shop_name": "Visi Garment (PT Visi Indotama Sejahtera)",
                "monthly_rev": 2600000000,
                "share_pct": 3.1,
                "avg_price": 285000,
                "badge": "Garmen Korporasi & Komunitas",
                "sales_channels": ["Website Resmi", "Katalog PDF", "WhatsApp"],
                "store_name": "Website Resmi",
                "store_url": "https://visigarment.com/",
                "social_platform": "Instagram",
                "social_handle": "@visigarment",
                "social_url": "https://www.instagram.com/visigarment/",
                "procurement_model": "Konveksi Jaket Komunitas, Perusahaan & Kampus"
            },
            {
                "rank": 3,
                "shop_name": "Harmas Outerwear (PT Harmas Citra Mandiri)",
                "monthly_rev": 2400000000,
                "share_pct": 2.8,
                "avg_price": 320000,
                "badge": "Pabrik Jaket Safety & Tambang",
                "sales_channels": ["Website Korporat", "Proposal Tender", "e-Katalog"],
                "store_name": "Website Resmi",
                "store_url": "https://harmas.co.id/",
                "social_platform": "Instagram",
                "social_handle": "@harmasgarment",
                "social_url": "https://www.instagram.com/harmasgarment/",
                "procurement_model": "Jaket Lapangan Safety, Parka Proyek & SPBU"
            },
            {
                "rank": 4,
                "shop_name": "Karunia Garment (CV Karunia Bersama)",
                "monthly_rev": 1700000000,
                "share_pct": 2.0,
                "avg_price": 260000,
                "badge": "Spesialis Jaket Varsity & Kampus",
                "sales_channels": ["Website Profil", "WhatsApp Sales", "Instagram"],
                "store_name": "Website Resmi",
                "store_url": "https://karuniagarment.com/",
                "social_platform": "Instagram",
                "social_handle": "@karuniagarment",
                "social_url": "https://www.instagram.com/karuniagarment/",
                "procurement_model": "Jaket Almamater, Varsity Angkatan & Jaket Panitia"
            }
        ],
        "sweet_spot": "Rp 250.000 - Rp 450.000 (Jaket Syamanah di Rp 392.500 berada tepat di segmen premium outerwear)",
        "channels": {
            "proposal_tender_pct": 58.0,
            "direct_wa_pct": 32.0,
            "repeat_contract_pct": 10.0,
            "dominant_traffic": "Proposal Penawaran B2B & Sampel Kain Fisik"
        },
        "syamanah_benchmark": {
            "pricing_range": "Rp 285.000 - Rp 500.000 (Median Rp 392.500)",
            "positioning": "Premium Institutional Outerwear (Bomber korporat, Jaket Lapangan Tambang/Proyek, Varsity kampus)",
            "competitive_edge": "Material water-repellent kualitas industri, furing quilting adem, bordir komputer presisi instansi."
        }
    },
    "seragam": {
        "title": "Seragam Kerja Korporat, PDH/PDL & Wearpack Pabrik B2B",
        "market_size_monthly_rp": 120000000000,
        "market_size_formatted": "Rp 120,0 Miliar / bulan",
        "annual_projected_rp": 1440000000000,
        "b2b_players_count": 1250,
        "segments": [
            {"category": "Kemeja Kerja Kantor & PDH Dinas", "monthly_rp": 54000000000, "share_pct": 45.0, "dominant_channel": "Tender & Proposal Perusahaan"},
            {"category": "Wearpack Safety & Baju Kerja Tambang/Pabrik", "monthly_rp": 38400000000, "share_pct": 32.0, "dominant_channel": "Kontrak Tahunan Pengadaan"},
            {"category": "Seragam Sekolah & Almamater Kampus", "monthly_rp": 18000000000, "share_pct": 15.0, "dominant_channel": "Pengadaan Yayasan / Institusi"},
            {"category": "Baju Medis, Scrub & Seragam Faskes", "monthly_rp": 9600000000, "share_pct": 8.0, "dominant_channel": "Pengadaan Rumah Sakit / Klinik"}
        ],
        "top_sellers": [
            {
                "rank": 1,
                "shop_name": "Harmas Garment (PT Harmas Citra Mandiri)",
                "monthly_rev": 4200000000,
                "category": "Seragam Kerja Kantor & Wearpack Tambang",
                "badge": "Pabrik Garmen B2B Terbesar",
                "sales_channels": ["Website Korporat", "e-Katalog", "Proposal Tender"],
                "store_name": "Website Resmi",
                "store_url": "https://harmas.co.id/",
                "social_platform": "Instagram",
                "social_handle": "@harmasgarment",
                "social_url": "https://www.instagram.com/harmasgarment/",
                "procurement_model": "Kontrak Pengadaan Korporat Multinasional & BUMN"
            },
            {
                "rank": 2,
                "shop_name": "Moko Garment (PT Moko Garment Indonesia)",
                "monthly_rev": 3500000000,
                "category": "Kemeja Kerja Pabrik & Safety Wearpack",
                "badge": "Produsen Workwear & Wearpack",
                "sales_channels": ["Website Resmi", "Katalog Online", "WhatsApp"],
                "store_name": "Website Resmi",
                "store_url": "https://moko.co.id/",
                "social_platform": "Instagram",
                "social_handle": "@moko.co.id",
                "social_url": "https://www.instagram.com/moko.co.id/",
                "procurement_model": "Supplier Baju Kerja Tambang, Pabrik & Proyek"
            },
            {
                "rank": 3,
                "shop_name": "Surewi Wardrobe (PT Surewi Multi Kreasi)",
                "monthly_rev": 2900000000,
                "category": "Seragam Korporat, Hotel & Perbankan",
                "badge": "Corporate Uniform Specialist",
                "sales_channels": ["Website Profil", "Katalog Desain", "Direct Sales"],
                "store_name": "Website Resmi",
                "store_url": "https://surewiwardrobe.com/",
                "social_platform": "Instagram",
                "social_handle": "@surewiwardrobe",
                "social_url": "https://www.instagram.com/surewiwardrobe/",
                "procurement_model": "Pengadaan Seragam Korporat & Resepsionis Bank"
            },
            {
                "rank": 4,
                "shop_name": "Rumah Jahit (PT Rumah Jahit Indonesia)",
                "monthly_rev": 2500000000,
                "category": "Seragam Sekolah, Toga & Almamater Kampus",
                "badge": "Spesialis Institusi Pendidikan",
                "sales_channels": ["Website Resmi", "WhatsApp Pengadaan", "Instagram"],
                "store_name": "Website Resmi",
                "store_url": "https://rumahjahit.com/",
                "social_platform": "Instagram",
                "social_handle": "@rumahjahit",
                "social_url": "https://www.instagram.com/rumahjahit/",
                "procurement_model": "Vendor Pengadaan Almamater Kampus & Sekolah"
            }
        ],
        "sweet_spot": "Rp 150.000 - Rp 220.000 (Kemeja PDH Syamanah di Rp 170.000 berada tepat di tengah rentang optimal tender instansi)",
        "channels": {
            "tender_po_pct": 65.0,
            "direct_b2b_pct": 25.0,
            "repeat_annual_pct": 10.0,
            "insight": "Pengadaan seragam korporat ditentukan oleh kecocokan spesifikasi bahan (American Drill, Japan Drill, Tropical), ketepatan deadline produksi massal, dan kredibilitas legalitas perusahaan."
        },
        "syamanah_benchmark": {
            "monthly_rev_rp": 3240000000,
            "comparison_multiplier": "Sejajar dengan Produsen Garmen B2B Papan Atas Nasional",
            "why_syamanah_wins": "Syamanah memegang kendali atas fasilitas konveksi terpadu, kecepatan sampling gratis untuk tender B2B, dan fleksibilitas kuantitas tanpa perantara."
        }
    }
}

# Alias untuk backward compatibility
PDF_BENCHMARK_DATA = B2B_BENCHMARK_DATA


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
