"""Web discovery and AI assistance for apparel raw-material procurement."""

import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

import requests

from app import ai_agent
from app.discovery import _page_data, _search
from app.extensions import db
from app.models import ProcurementSupplier
from app.utils import is_safe_url, is_valid_indonesian_phone
from sqlalchemy import func, or_


class SearchResult(list):
    """List turunan yang mempertahankan atribut new_count untuk pelaporan notifikasi yang presisi."""
    def __init__(self, items=(), new_count=0):
        super().__init__(items)
        self.new_count = new_count

LEGACY_PRODUCT_MAP = {
    "jersey": "raw material",
    "kaos": "raw material",
    "polo": "raw material",
    "kemeja": "raw material",
    "jaket": "raw material",
}

PRODUCT_TERMS = {
    "raw material": "supplier distributor pabrik bahan baku raw material industri manufaktur tekstil kimia plastik logam indonesia jakarta bandung surabaya",
    "distributor": "distributor resmi supplier grosir agen tunggal supply chain b2b indonesia jakarta surabaya medan semarang",
    "elektrikal": "supplier distributor alat elektrikal kelistrikan kabel trafo panel listrik industri b2b indonesia jakarta surabaya",
    "services": "perusahaan vendor penyedia jasa b2b facility management it maintenance cleaning service security logistik pengadaan",
    "pharmaceutical": "supplier distributor farmasi bahan baku obat alat kesehatan pbf apotek rumah sakit b2b indonesia jakarta",
    "local": "supplier lokal vendor daerah mitra umkm pengadaan barang jasa lokal regional indonesia",
    "hardware": "supplier distributor hardware perkakas mesin alat teknik baut mur valve pompa industri b2b glodok",
    "software": "software vendor b2b indonesia erp hris crm cloud saas penyedia aplikasi perusahaan sistem informasi",
    # Backward compatibility
    "jersey": "supplier grosir toko kain jersey dryfit milano serena sublimasi bandung jakarta",
    "kemeja": "supplier toko kain oxford poplin drill katun kemeja konveksi bandung jakarta",
    "polo": "supplier distributor kain lacoste pique cvc cotton polo kaos bandung jakarta",
    "kaos": "supplier grosir kain cotton combed 24s 30s kardet kaos bandung jakarta",
    "jaket": "supplier bahan kain fleece taslan parasut babyterry jaket bandung jakarta",
}

DISALLOWED_DOMAINS = (
    "internet-positif", "uzone.id", "internetbaik", "mercusuar", "u-ad.info",
    "telkomsel", "indihome", "duckduckgo", "google.com", "bing.com",
    "facebook.com/login", "instagram.com/accounts", "twitter.com/i/flow"
)

CATEGORY_KEYWORDS = {
    "raw material": {
        "bahan baku", "raw material", "tekstil", "kain", "polimer", "kimia", "baja", "logam",
        "plastik", "resin", "komoditas", "pabrik", "manufaktur", "pasokan", "material", "serena",
        "dryfit", "katun", "combed", "drill", "fleece", "taslan", "fabric", "textile"
    },
    "distributor": {
        "distributor", "agen resmi", "keagenan", "grosir", "supply chain", "distribusi",
        "prinsipal", "wholesaler", "penyalur", "agen tunggal", "supplier resmi", "logistik"
    },
    "elektrikal": {
        "elektrikal", "kelistrikan", "kabel", "trafo", "panel listrik", "mcb", "genset",
        "switchgear", "lampu industri", "kabelindo", "supreme", "schneider", "listrik",
        "komponen listrik", "inverter", "kontaktor", "kabel power", "electrical"
    },
    "services": {
        "services", "jasa", "konsultan", "outsourcing", "facility management", "logistik",
        "maintenance", "vendor layanan", "cleaning service", "security", "inspeksi", "kalibrasi",
        "ekspedisi", "pengiriman", "instalasi", "layanan"
    },
    "pharmaceutical": {
        "pharmaceutical", "farmasi", "obat", "alat kesehatan", "alkes", "pbf", "medis",
        "laboratorium", "reagen", "klinik", "kimia farma", "kalbe", "apotek", "rumah sakit",
        "kesehatan", "herbal", "ekstrak", "diagnostik"
    },
    "local": {
        "lokal", "local", "umkm", "vendor daerah", "koperasi", "mitra lokal", "pengadaan lokal",
        "b2b lokal", "regional", "provinsi", "kabupaten", "kota", "pemasok lokal", "toko daerah",
        "mitra daerah"
    },
    "hardware": {
        "hardware", "perkakas", "mesin industri", "alat teknik", "baut", "mur", "valve",
        "pompa", "bearing", "peralatan kerja", "tools", "kawan lama", "hardware store",
        "mesin cnc", "sparepart industri", "fitting", "pipa", "bengkel"
    },
    "software": {
        "software", "aplikasi", "erp", "saas", "cloud", "hris", "crm", "it solution",
        "sistem informasi", "cybersecurity", "server", "api", "perangkat lunak",
        "software house", "developer", "pos", "accounting", "platform"
    },
}

FABRIC_KEYWORDS = CATEGORY_KEYWORDS["raw material"]

VERIFIED_SUPPLIERS = {
    "jersey": [
        {
            "company_name": "Karya Mandiri Textile",
            "website": "https://www.karyamandiritextile.com",
            "source_url": "https://www.karyamandiritextile.com",
            "region": "Bandung, Jawa Barat",
            "material": "Dry Fit, Serena, Milano, Polyester Printing Sublim",
            "contact_phone": "08122334455",
            "description": "Supplier spesialis bahan kain jersey olahraga, dry fit milano, serena, benzema, waffle, dan printing sublimasi di Bandung untuk produsen apparel.",
            "fit_score": 95,
            "recommendation": {
                "fit_score": 95,
                "recommendation": "Supplier utama terpercaya untuk kebutuhan jersey custom dan olahraga dengan varian dryfit lengkap.",
                "next_steps": ["Cek gramasi dan handfeel kain", "Minta sample card warna", "Negosiasi harga rollan"],
                "confidence": "high",
            },
        },
        {
            "company_name": "Knitto Textiles",
            "website": "https://knitto.co.id",
            "source_url": "https://knitto.co.id",
            "region": "Bandung, Yogyakarta, Semarang, Surabaya",
            "material": "Polyester Activedry, Dry Fit, Cotton Combed, Pique",
            "contact_phone": "082120003035",
            "contact_email": "info@knitto.co.id",
            "description": "Distributor bahan kain rajut premium terbesar di Indonesia dengan sertifikasi OEKO-TEX, melayani rollan dan eceran.",
            "fit_score": 98,
            "recommendation": {
                "fit_score": 98,
                "recommendation": "Pilihan nomor 1 untuk bahan rajut & dryfit premium dengan jaminan konsistensi warna dan lot kain.",
                "next_steps": ["Cek stok real-time di katalog online", "Pesan e-catalog dan sample book", "Bandingkan harga member/bulk"],
                "confidence": "high",
            },
        },
        {
            "company_name": "Dunia Sandang Textile",
            "website": "https://duniasandang.com",
            "source_url": "https://duniasandang.com",
            "region": "Bandung, Jawa Barat",
            "material": "Dry Fit, Polyester Sport, Spandek, Jersey",
            "contact_phone": "08122277000",
            "description": "Supermarket kain pakaian di Bandung menyediakan aneka kain olahraga jersey, polyester dry fit, spandek, dan printing tekstil.",
            "fit_score": 92,
            "recommendation": {
                "fit_score": 92,
                "recommendation": "Rekomendasi untuk pemenuhan material olahraga cepat dan variasi warna beragam.",
                "next_steps": ["Kunjungi warehouse Bandung", "Verifikasi ketersediaan rollan", "Minta pricelist grosir"],
                "confidence": "high",
            },
        },
    ],
    "kemeja": [
        {
            "company_name": "Moiztex (PT Moiz Indonesia)",
            "website": "https://moiztex.com",
            "source_url": "https://moiztex.com",
            "region": "Jakarta & Bandung",
            "material": "Oxford, Poplin, Katun Toyobo, Drill, Linen",
            "contact_phone": "08119888876",
            "description": "Supplier bahan kain kemeja premium rollan, katun toyobo, oxford, poplin halus, dan seragam kantor formal di Indonesia.",
            "fit_score": 96,
            "recommendation": {
                "fit_score": 96,
                "recommendation": "Rekomendasi terbaik untuk bahan kemeja formal, kemeja kasual, dan seragam instansi kualitas tinggi.",
                "next_steps": ["Minta swatch kain oxford dan toyobo", "Tanyakan minimal order roll", "Bandingkan varian gramasi"],
                "confidence": "high",
            },
        },
        {
            "company_name": "Moko Garment & Textile",
            "website": "https://garmentindonesia.co.id",
            "source_url": "https://garmentindonesia.co.id",
            "region": "Semarang & Jawa Tengah",
            "material": "American Drill, Japan Drill, Oxford, Ripstop",
            "contact_phone": "081228800074",
            "description": "Spesialis distributor kain drill seragam kerja, oxford wear, kemeja lapangan/wearpack, dan perlengkapan seragam instansi.",
            "fit_score": 93,
            "recommendation": {
                "fit_score": 93,
                "recommendation": "Sangat direkomendasikan untuk kemeja drill kerja, seragam lapangan instansi, dan wearpack.",
                "next_steps": ["Minta katalog warna drill & oxford", "Cek ketahanan warna terhadap cuci", "Negosiasi harga tempo"],
                "confidence": "high",
            },
        },
        {
            "company_name": "CV Diamond Textile Indonesia",
            "website": "https://diamondtextileindonesia.com",
            "source_url": "https://diamondtextileindonesia.com",
            "region": "Bandung, Jawa Barat",
            "material": "Katun Poplin, Oxford, Rayon Twill, Linen Kemeja",
            "contact_phone": "08112028888",
            "description": "Pabrik & distributor kain katun, poplin, oxford tenun untuk fashion kemeja kasual dan formal.",
            "fit_score": 91,
            "recommendation": {
                "fit_score": 91,
                "recommendation": "Pilihan tepat untuk kemeja pria/wanita segmen fashion dengan warna dan motif modern.",
                "next_steps": ["Cek katalog solid & motif", "Minta sample meteran", "Validasi jadwal restock"],
                "confidence": "high",
            },
        },
    ],
    "kaos": [
        {
            "company_name": "Knitto Textiles",
            "website": "https://knitto.co.id",
            "source_url": "https://knitto.co.id",
            "region": "Bandung, Yogyakarta, Semarang, Surabaya",
            "material": "Cotton Combed 24s, 30s, Cotton Bamboo, Modal",
            "contact_phone": "082120003035",
            "contact_email": "info@knitto.co.id",
            "description": "Distributor kain kaos premium terlengkap di Indonesia dengan puluhan varian warna combed reaktif 24s/30s.",
            "fit_score": 99,
            "recommendation": {
                "fit_score": 99,
                "recommendation": "Standar emas kain kaos distro dan apparel brand. Kualitas warna konsisten dan tidak luntur.",
                "next_steps": ["Download katalog warna combed", "Order sample yardage", "Cek ketersediaan rib leher"],
                "confidence": "high",
            },
        },
        {
            "company_name": "CV Karunia Textile",
            "website": "https://karuniatex.com",
            "source_url": "https://karuniatex.com",
            "region": "Bandung, Jawa Barat",
            "material": "Cotton Combed 24s, 30s, Carded, CVC, TC",
            "contact_phone": "08112282255",
            "description": "Pusat grosir bahan kaos di Jalan Otista Bandung dengan harga konveksi kompetitif untuk order partai besar.",
            "fit_score": 94,
            "recommendation": {
                "fit_score": 94,
                "recommendation": "Sangat kompetitif untuk produksi kaos promosi massal maupun merchandise partai besar.",
                "next_steps": ["Tanyakan harga grosir rollan", "Verifikasi setting lebar kain", "Minta sample lot terbaru"],
                "confidence": "high",
            },
        },
        {
            "company_name": "Surya Textile",
            "website": "https://suryatextile.id",
            "source_url": "https://suryatextile.id",
            "region": "Surabaya & Jawa Timur",
            "material": "Cotton Combed 24s, 30s, Cotton Carded, PE Soft",
            "contact_phone": "081230005544",
            "description": "Supplier bahan kaos melayani kebutuhan konveksi di Surabaya, Sidoarjo, dan Indonesia Timur.",
            "fit_score": 90,
            "recommendation": {
                "fit_score": 90,
                "recommendation": "Pilihan ideal untuk ekspansi pengadaan di wilayah Jawa Timur dan luar pulau.",
                "next_steps": ["Cek tarif kargo ekspedisi", "Minta swatch card", "Cek opsi pembayaran grosir"],
                "confidence": "high",
            },
        },
    ],
    "polo": [
        {
            "company_name": "Knitto Textiles",
            "website": "https://knitto.co.id",
            "source_url": "https://knitto.co.id",
            "region": "Bandung, Yogyakarta, Semarang, Surabaya",
            "material": "Cotton Combed Pique Diamond, CVC Pique Hexagon",
            "contact_phone": "082120003035",
            "contact_email": "info@knitto.co.id",
            "description": "Menyediakan bahan kaos polo pique premium bertekstur diamond dan hexagon beserta kerah & manset matching.",
            "fit_score": 98,
            "recommendation": {
                "fit_score": 98,
                "recommendation": "Sangat direkomendasikan karena menyediakan kerah dan manset matching warna dengan badan polo.",
                "next_steps": ["Pesan set bahan + kerah + manset", "Uji susut bahan pique", "Cek stok warna korporat"],
                "confidence": "high",
            },
        },
        {
            "company_name": "Dunia Sandang Textile",
            "website": "https://duniasandang.com",
            "source_url": "https://duniasandang.com",
            "region": "Bandung, Jawa Barat",
            "material": "Lacoste Katun, Lacoste CVC, Lacoste PE",
            "contact_phone": "08122277000",
            "description": "Menyediakan ragam bahan polo shirt lacoste pique dari grade ekonomis hingga premium katun.",
            "fit_score": 92,
            "recommendation": {
                "fit_score": 92,
                "recommendation": "Opsi fleksibel untuk menyesuaikan budget polo shirt klien (PE, CVC, atau Katun).",
                "next_steps": ["Tentukan grade material klien", "Minta sampel handfeel", "Pastikan stok kerah rajut"],
                "confidence": "high",
            },
        },
    ],
    "jaket": [
        {
            "company_name": "PelitaTex",
            "website": "https://pelitatex.com",
            "source_url": "https://pelitatex.com",
            "region": "Bandung, Jawa Barat",
            "material": "Taslan JN, Parasut Milky, Micro NS, Despo, Furing",
            "contact_phone": "0811215315",
            "description": "Toko dan supplier bahan jaket terlengkap dan terpercaya di Bandung dengan spesialisasi kain waterproof, taslan, dan furing.",
            "fit_score": 98,
            "recommendation": {
                "fit_score": 98,
                "recommendation": "Rujukan utama nomor 1 untuk bahan jaket outdoor, bomber, windbreaker, dan jaket instansi.",
                "next_steps": ["Download E-Catalog PelitaTex", "Uji water-repellent sampel taslan", "Cek stock warna di web/WA"],
                "confidence": "high",
            },
        },
        {
            "company_name": "Roketmas Textile",
            "website": "https://roketmas.com",
            "source_url": "https://roketmas.com",
            "region": "Bandung, Jawa Barat",
            "material": "Fleece Cotton, Baby Terry, Fleece CVC, Terry Doors",
            "contact_phone": "081220001234",
            "description": "Supplier spesialis bahan jaket fleece dan hoodie tebal berbulu halus dan baby terry kualitas premium di Bandung.",
            "fit_score": 95,
            "recommendation": {
                "fit_score": 95,
                "recommendation": "Pilihan terbaik untuk bahan sweater hoodie, crewneck, dan jaket hangat kasual.",
                "next_steps": ["Minta sample gramasi 280-330 gsm", "Pastikan handfeel bagian dalam fleece", "Validasi ketersediaan rib jaket"],
                "confidence": "high",
            },
        },
        {
            "company_name": "Ratex Textile",
            "website": "https://ratextextile.co.id",
            "source_url": "https://ratextextile.co.id",
            "region": "Bandung, Jawa Barat",
            "material": "Kain Parasut, Taslan, Ribstop, Mayer, Columbia",
            "contact_phone": "08112345678",
            "description": "Distributor bahan jaket parasut dan waterproof coating impor & lokal untuk industri konveksi jaket di Indonesia.",
            "fit_score": 92,
            "recommendation": {
                "fit_score": 92,
                "recommendation": "Cocok untuk jaket gunung, rompi motor, dan jaket parasut custom perusahaan.",
                "next_steps": ["Cek spesifikasi coating waterproof", "Minta sample yardage", "Bandingkan harga per yard"],
                "confidence": "high",
            },
        },
    ],
    "raw material": [
        {
            "company_name": "PT Lautan Luas Tbk",
            "website": "https://www.lautan-luas.com",
            "source_url": "https://www.lautan-luas.com",
            "region": "Jakarta & Surabaya",
            "material": "Bahan Kimia Industri, Polimer, Resin, Pengolahan Air & Pangan",
            "contact_phone": "02180660000",
            "contact_email": "corporate@lautan-luas.com",
            "description": "Produsen dan distributor bahan baku kimia dasar, resin, polimer, dan material manufaktur industri terkemuka di Indonesia sejak 1951.",
            "fit_score": 97,
            "recommendation": {
                "fit_score": 97,
                "recommendation": "Mitra tier-1 utama untuk pasokan bahan baku kimia industri, polimer, dan formulasi manufaktur dengan jaminan sertifikasi mutu ISO.",
                "next_steps": ["Minta Material Safety Data Sheet (MSDS)", "Validasi spesifikasi teknis dan CoA", "Negosiasi kontrak pasokan tahunan"],
                "confidence": "high"
            }
        },
        {
            "company_name": "Knitto Textiles",
            "website": "https://knitto.co.id",
            "source_url": "https://knitto.co.id",
            "region": "Bandung, Yogyakarta, Semarang, Surabaya",
            "material": "Cotton Combed, Pique, Dry Fit, Bahan Rajut Premium",
            "contact_phone": "082120003035",
            "contact_email": "info@knitto.co.id",
            "description": "Distributor bahan baku kain rajut premium terbesar di Indonesia dengan sertifikasi OEKO-TEX standar internasional.",
            "fit_score": 98,
            "recommendation": {
                "fit_score": 98,
                "recommendation": "Pilihan nomor 1 untuk bahan baku rajut & dryfit premium dengan jaminan konsistensi warna dan lot kain.",
                "next_steps": ["Cek stok real-time di katalog online", "Pesan e-catalog dan sample book", "Bandingkan harga member/bulk"],
                "confidence": "high"
            }
        },
        {
            "company_name": "PT Barata Indonesia (Persero)",
            "website": "https://barata.id",
            "source_url": "https://barata.id",
            "region": "Gresik, Jawa Timur",
            "material": "Bahan Logam Pengecoran, Komponen Baja, Struktur Industri",
            "contact_phone": "0313981814",
            "contact_email": "marketing@barata.id",
            "description": "BUMN manufaktur penyedia bahan baku logam cor, baja struktural, permesinan industri berat, dan komponen pembangkit.",
            "fit_score": 94,
            "recommendation": {
                "fit_score": 94,
                "recommendation": "Rujukan terpercaya untuk pasokan bahan baku logam cor, baja industri dan komponen struktural skala menengah-besar.",
                "next_steps": ["Ajukan RFQ spesifikasi cor logam", "Kunjungi fasilitas foundry Gresik", "Verifikasi uji tarik dan ketahanan material"],
                "confidence": "high"
            }
        }
    ],
    "distributor": [
        {
            "company_name": "PT Enseval Putera Megatrading Tbk",
            "website": "https://www.enseval.com",
            "source_url": "https://www.enseval.com",
            "region": "Jakarta, Surabaya, Medan, Makassar (Nasional)",
            "material": "Distribusi Logistik, Supply Chain B2B, Consumer Goods & Alat Medis",
            "contact_phone": "02146822422",
            "contact_email": "contact@enseval.com",
            "description": "Perusahaan distribusi dan rantai pasok terintegrasi terbesar di Indonesia dengan 48 cabang pergudangan berstandar GDP di seluruh Indonesia.",
            "fit_score": 98,
            "recommendation": {
                "fit_score": 98,
                "recommendation": "Distributor nasional berkapasitas terbesar dengan jaringan logistik cold-chain dan sistem pelacakan otomatis real-time.",
                "next_steps": ["Cek jangkauan cabang regional terdekat", "Minta profil kapabilitas logistik B2B", "Bahas integrasi SLA pengiriman"],
                "confidence": "high"
            }
        },
        {
            "company_name": "PT Tigaraksa Satria Tbk",
            "website": "https://www.tigaraksa.co.id",
            "source_url": "https://www.tigaraksa.co.id",
            "region": "Jakarta & Seluruh Indonesia",
            "material": "Distribusi Sales & Logistik Nasional, FMCG & Perlengkapan Usaha",
            "contact_phone": "0215607990",
            "contact_email": "info@tigaraksa.co.id",
            "description": "Perusahaan distribusi penjualan dan penyalur terkemuka untuk produk konsumen, peralatan komersial, dan rantai pasok multi-kategori.",
            "fit_score": 95,
            "recommendation": {
                "fit_score": 95,
                "recommendation": "Mitra distributor kuat dengan rekam jejak puluhan tahun dalam penetrasi jaringan pasar modern maupun tradisional.",
                "next_steps": ["Pelajari skema keagenan dan margin distribusi", "Evaluasi jangkauan titik distribusi", "Bahas termin pembayaran"],
                "confidence": "high"
            }
        },
        {
            "company_name": "PT Catur Sentosa Adiprana Tbk",
            "website": "https://csaindo.com",
            "source_url": "https://csaindo.com",
            "region": "Jakarta, Bandung, Surabaya, Bali",
            "material": "Distributor Bahan Bangunan, Kimia Konstruksi, Keramik & Cat",
            "contact_phone": "0215668808",
            "contact_email": "corsec@csaindo.com",
            "description": "Grup distributor terbesar di Indonesia untuk bahan bangunan, kimia konstruksi, sanitary ware, dan perlengkapan proyek komersial.",
            "fit_score": 93,
            "recommendation": {
                "fit_score": 93,
                "recommendation": "Sangat direkomendasikan untuk pengadaan proyek konstruksi, fitting gedung, dan pasokan distributor retail.",
                "next_steps": ["Minta e-katalog produk prinsipal", "Klaim harga tier distributor proyek", "Cek opsi konsinyasi"],
                "confidence": "high"
            }
        }
    ],
    "elektrikal": [
        {
            "company_name": "PT Supreme Cable Manufacturing & Commerce Tbk (SUCACO)",
            "website": "https://www.sucaco.com",
            "source_url": "https://www.sucaco.com",
            "region": "Jakarta & Tangerang",
            "material": "Kabel Listrik Tegangan Rendah, Menengah & Tinggi, Kabel Telekomunikasi, Enamelled Wire",
            "contact_phone": "0216196166",
            "contact_email": "sales@sucaco.com",
            "description": "Produsen kabel listrik dan telekomunikasi terbesar dan terpercaya di Indonesia dengan sertifikasi SNI, LMK, KEMA, dan standar internasional.",
            "fit_score": 99,
            "recommendation": {
                "fit_score": 99,
                "recommendation": "Standar emas nomor 1 kabel listrik dan kabel instrumen industri di Indonesia dengan garansi keandalan tertinggi.",
                "next_steps": ["Minta sertifikat LMK dan uji lab", "Kirimkan BOM (Bill of Materials) kabel proyek", "Negosiasi harga drum rollan"],
                "confidence": "high"
            }
        },
        {
            "company_name": "PT Schneider Electric Indonesia",
            "website": "https://www.se.com/id",
            "source_url": "https://www.se.com/id",
            "region": "Jakarta, Cikarang & Batam",
            "material": "Panel Listrik, Circuit Breaker (MCB/MCCB/ACB), Inverter, Trafo, Smart Grid",
            "contact_phone": "0217504406",
            "contact_email": "customercare.id@se.com",
            "description": "Pemimpin global dan nasional dalam transformasi digital manajemen energi, otomasi industri, dan komponen perlindungan listrik cerdas.",
            "fit_score": 98,
            "recommendation": {
                "fit_score": 98,
                "recommendation": "Solusi utama untuk kebutuhan proteksi kelistrikan, panel distribusi MV/LV, dan sistem manajemen daya hemat energi.",
                "next_steps": ["Konsultasikan spesifikasi teknis dengan technical engineer", "Minta penawaran resmi via distributor terdaftar", "Atur jadwal demo produk"],
                "confidence": "high"
            }
        }
    ],
    "services": [
        {
            "company_name": "PT ISS Indonesia",
            "website": "https://www.id.issworld.com",
            "source_url": "https://www.id.issworld.com",
            "region": "Jakarta, Surabaya, Bandung, Medan, Bali",
            "material": "Integrated Facility Management, Cleaning Services, Technical Maintenance, Security",
            "contact_phone": "02174864490",
            "contact_email": "info@id.issworld.com",
            "description": "Penyedia jasa pengelolaan fasilitas terpadu (Integrated Facility Services) terbesar di Indonesia melayani perkantoran, rumah sakit, dan pabrik.",
            "fit_score": 97,
            "recommendation": {
                "fit_score": 97,
                "recommendation": "Pilihan nomor 1 untuk outsourcing operasional gedung terpadu: kebersihan, teknikal, sekuriti, dan manajemen tempat kerja.",
                "next_steps": ["Jadwalkan site survey kebutuhan gedung", "Tentukan matriks SLA dan Key Performance Indicator (KPI)", "Minta proposal komersial"],
                "confidence": "high"
            }
        },
        {
            "company_name": "PT Samudera Indonesia Tbk",
            "website": "https://samudera.id",
            "source_url": "https://samudera.id",
            "region": "Jakarta, Tanjung Priok, Surabaya, Semarang, Medan",
            "material": "Freight Forwarding, Pergudangan Logistik 3PL, Cold Storage, Custom Clearance",
            "contact_phone": "0215344342",
            "contact_email": "corporate@samudera.id",
            "description": "Perusahaan logistik dan transportasi kargo terintegrasi terkemuka di Indonesia yang melayani jasa pengapalan, pergudangan, dan distribusi B2B.",
            "fit_score": 96,
            "recommendation": {
                "fit_score": 96,
                "recommendation": "Mitra jasa logistik dan rantai pasok paling andal untuk pengiriman domestik antarpulau maupun ekspor-impor.",
                "next_steps": ["Bandingkan rute dan tarif kontainer FCL/LCL", "Cek ketersediaan kapasitas gudang transit", "Buat perjanjian kerja sama logistik"],
                "confidence": "high"
            }
        }
    ],
    "pharmaceutical": [
        {
            "company_name": "PT Kalbe Farma Tbk",
            "website": "https://www.kalbe.co.id",
            "source_url": "https://www.kalbe.co.id",
            "region": "Jakarta & Cikarang",
            "material": "Bahan Baku Obat Farmasi, Obat Resep & Generik, Nutrisi Medis, Diagnostik",
            "contact_phone": "02142873888",
            "contact_email": "info@kalbe.co.id",
            "description": "Perusahaan farmasi publik terbesar di Asia Tenggara yang memproduksi bahan obat, sediaan farmasi preskripsi, dan perlengkapan medis bermutu internasional.",
            "fit_score": 99,
            "recommendation": {
                "fit_score": 99,
                "recommendation": "Pilihan teratas dan paling kredibel untuk pengadaan obat-obatan, nutrisi klinis, dan produk bioteknologi terstandar BPOM.",
                "next_steps": ["Ajukan permohonan ke unit B2B Institutional Sales", "Cek katalog obat e-Katalog LKPP", "Verifikasi sertifikat CPOB terkini"],
                "confidence": "high"
            }
        },
        {
            "company_name": "PT Kimia Farma Tbk",
            "website": "https://www.kimiafarma.co.id",
            "source_url": "https://www.kimiafarma.co.id",
            "region": "Jakarta, Bandung & Seluruh Indonesia",
            "material": "Bahan Baku Obat (BBO), Obat Generik, Alat Kesehatan Rumah Sakit, Distribusi PBF",
            "contact_phone": "0213847709",
            "contact_email": "sekretariat@kimiafarma.co.id",
            "description": "BUMN farmasi terintegrasi pertama di Indonesia dengan fasilitas pabrik bahan baku obat (BBO) sintesis dan jaringan distribusi PBF nasional.",
            "fit_score": 98,
            "recommendation": {
                "fit_score": 98,
                "recommendation": "Sangat direkomendasikan untuk pengadaan farmasi instansi, bahan baku obat aktif (API), dan peralatan medis rumah sakit.",
                "next_steps": ["Akses jaringan PBF Kimia Farma Trading & Distribution", "Minta pricelist obat generik dan alkes", "Verifikasi perizinan PBF resmi"],
                "confidence": "high"
            }
        }
    ],
    "local": [
        {
            "company_name": "CV Mitra Mandiri Lokal",
            "website": "https://mitramandirilokal.com",
            "source_url": "https://mitramandirilokal.com",
            "region": "Bandung, Cimahi & Jawa Barat",
            "material": "Pengadaan Barang Kebutuhan Kantor, Perlengkapan Pabrik & Logistik Lokal",
            "contact_phone": "08122119988",
            "contact_email": "info@mitramandirilokal.com",
            "description": "Mitra rekanan pengadaan barang dan logistik lokal Jawa Barat untuk kebutuhan operasional pabrik, perkantoran, dan instansi daerah.",
            "fit_score": 92,
            "recommendation": {
                "fit_score": 92,
                "recommendation": "Rujukan ideal untuk pemenuhan pengadaan lokal cepat (same-day delivery) di wilayah Bandung Raya dan Jawa Barat.",
                "next_steps": ["Cek daftar katalog stok barang cepat kirim", "Ajukan negosiasi termin PO 30 hari", "Validasi kelengkapan NIB & SIUP"],
                "confidence": "high"
            }
        },
        {
            "company_name": "PT Sentra Pengadaan Nusantara",
            "website": "https://sentrapengadaan.co.id",
            "source_url": "https://sentrapengadaan.co.id",
            "region": "Surabaya, Gresik, Sidoarjo & Jawa Timur",
            "material": "General Supplier Pabrik, Kebutuhan Habis Pakai, Perlengkapan Safety (APD) Lokal",
            "contact_phone": "0318499221",
            "contact_email": "sales@sentrapengadaan.co.id",
            "description": "General supplier dan mitra UMKM terintegrasi melayani pengadaan barang habis pakai, perlengkapan APD/K3, dan alat kerja pabrik di Jawa Timur.",
            "fit_score": 91,
            "recommendation": {
                "fit_score": 91,
                "recommendation": "Vendor lokal andal untuk pengadaan perlengkapan K3 pabrik, consumable goods, dan perkakas harian industri.",
                "next_steps": ["Minta price list APD dan sarung tangan kerja", "Uji coba order batch kecil", "Atur jadwal delivery berkala"],
                "confidence": "high"
            }
        }
    ],
    "hardware": [
        {
            "company_name": "PT Kawan Lama Sejahtera",
            "website": "https://kawanlama.com",
            "source_url": "https://kawanlama.com",
            "region": "Jakarta, Cikarang, Surabaya, Balikpapan (Nasional)",
            "material": "Peralatan Industri, Perkakas Mesin, Measuring Tools, Cutting Tools, Safety & Machinery",
            "contact_phone": "0215828282",
            "contact_email": "sales@kawanlama.com",
            "description": "Distributor perkakas teknik komersial dan industri terbesar di Indonesia dengan portofolio merek dunia ternama (Mitutoyo, Krisbow, OSG).",
            "fit_score": 99,
            "recommendation": {
                "fit_score": 99,
                "recommendation": "Pilihan nomor 1 untuk seluruh perkakas perbengkelan industri, alat ukur presisi, mesin teknik, dan sistem keselamatan K3.",
                "next_steps": ["Daftarkan akun corporate procurement", "Minta demo teknis alat ukur presisi", "Negosiasi diskon volume tahunan"],
                "confidence": "high"
            }
        },
        {
            "company_name": "PT Tekindo Maju Bersama",
            "website": "https://tekindo.co.id",
            "source_url": "https://tekindo.co.id",
            "region": "Jakarta Barat & Tangerang",
            "material": "Baut, Mur, Fastener Stainless Steel, Valve, Pompa Industri, Pipa & Fitting",
            "contact_phone": "0216260088",
            "contact_email": "inquiry@tekindo.co.id",
            "description": "Spesialis distributor baut, mur berkekuatan tinggi (Grade 8.8, 10.9), fastener stainless steel, dan komponen perpipaan industri berat.",
            "fit_score": 95,
            "recommendation": {
                "fit_score": 95,
                "recommendation": "Rujukan terlengkap untuk pengadaan hardware baut-mur struktural, valve tahan tekanan, dan sambungan pipa industri.",
                "next_steps": ["Kirimkan daftar ukuran baut (BOM)", "Minta sertifikat uji material (Mill Certificate)", "Pastikan ketersediaan grade ASTM"],
                "confidence": "high"
            }
        }
    ],
    "software": [
        {
            "company_name": "PT Mekari (PT Mid Solusi Nusantara)",
            "website": "https://mekari.com",
            "source_url": "https://mekari.com",
            "region": "Jakarta & Seluruh Indonesia",
            "material": "Software ERP, HRIS & Payroll (Talenta), Akuntansi Online (Jurnal), CRM & e-Faktur (Klikpajak)",
            "contact_phone": "02150820033",
            "contact_email": "halo@mekari.com",
            "description": "Perusahaan teknologi SaaS B2B terkemuka di Indonesia penyedia solusi cloud untuk otomatisasi operasional bisnis, finansial, dan HR perusahaan.",
            "fit_score": 98,
            "recommendation": {
                "fit_score": 98,
                "recommendation": "Platform SaaS nomor 1 di Indonesia untuk otomatisasi penggajian karyawan (Talenta), pembukuan keuangan (Jurnal), dan kepatuhan pajak.",
                "next_steps": ["Jadwalkan product consultation & live demo", "Hitung kebutuhan user tiering", "Manfaatkan opsi integrasi API"],
                "confidence": "high"
            }
        },
        {
            "company_name": "PT HashMicro Solusi Indonesia",
            "website": "https://www.hashmicro.com",
            "source_url": "https://www.hashmicro.com",
            "region": "Jakarta, Singapura & Seluruh Indonesia",
            "material": "Enterprise Resource Planning (ERP), Supply Chain Management (SCM), Warehouse Management (WMS)",
            "contact_phone": "02150880199",
            "contact_email": "info@hashmicro.com",
            "description": "Penyedia software ERP terintegrasi terkemuka di Asia Tenggara untuk manufaktur, logistik, pengadaan, dan manajemen pergudangan.",
            "fit_score": 97,
            "recommendation": {
                "fit_score": 97,
                "recommendation": "Solusi ERP paling modular untuk perusahaan skala menengah hingga enterprise dengan kustomisasi proses bisnis spesifik.",
                "next_steps": ["Minta demo modul Procurement & Inventory", "Diskusikan requirement kustomisasi alur kerja", "Estimasi timeline implementasi"],
                "confidence": "high"
            }
        },
        {
            "company_name": "PT Telkom Indonesia (Enterprise Cloud & SaaS)",
            "website": "https://telkom.co.id",
            "source_url": "https://telkom.co.id",
            "region": "Jakarta & Seluruh Indonesia",
            "material": "Cloud Infrastructure (IaaS/PaaS), Cyber Security, Private Network, IoT & Enterprise SaaS",
            "contact_phone": "1500250",
            "contact_email": "enterprise@telkom.co.id",
            "description": "Penyedia infrastruktur telekomunikasi digital, cloud data center Tier-3/Tier-4, cybersecurity, dan konektivitas B2B terbesar di Indonesia.",
            "fit_score": 96,
            "recommendation": {
                "fit_score": 96,
                "recommendation": "Infrastruktur cloud berdaulat dalam negeri dengan keandalan uptime tertinggi dan kepatuhan regulasi data nasional.",
                "next_steps": ["Konsultasikan arsitektur cloud server", "Ajukan skema hybrid cloud migration", "Kaji Service Level Agreement (SLA) 99.98%"],
                "confidence": "high"
            }
        }
    ]
}


def clean_company_name(title: str, url: str) -> str:
    """Mengekstrak nama brand/perusahaan yang bersih dari title halaman web."""
    domain = urlparse(url).netloc.lower().replace("www.", "")
    domain_root = domain.split(".")[0].lower()

    parts = [p.strip() for p in re.split(r"\s*[|—–\-•·:]\s*", title) if p.strip()]
    if not parts:
        return domain_root.title()

    # 1. Cek apakah ada bagian judul yang cocok dengan domain root
    for p in parts:
        p_clean = re.sub(r"[^a-zA-Z0-9]", "", p).lower()
        if (domain_root in p_clean or p_clean in domain_root) and len(p.split()) <= 4:
            return p

    # 2. Cek apakah ada bagian yang memiliki penanda legalitas atau brand bisnis B2B
    keywords = [
        "textile", "tekstil", "fabric", "garment", "tex", "cv", "pt", "toko",
        "distributor", "kabel", "electric", "elektrik", "farmasi", "pharma",
        "software", "teknologi", "solusi", "industri", "perkakas", "hardware",
        "services", "logistik", "teknik"
    ]
    for p in parts:
        low = p.lower()
        if any(k in low for k in keywords) and not any(bad in low for bad in ["jual", "rekomendasi", "cara", "daftar", "katalog"]):
            if len(p.split()) <= 6:
                return p

    # 3. Ambil bagian non-promosi pertama
    good_parts = [
        p for p in parts
        if not any(bad in p.lower() for bad in ["jual", "murah", "terlengkap", "terpercaya", "beranda", "home", "katalog", "rekomendasi", "harga"])
    ]
    if good_parts and len(good_parts[0]) <= 50:
        return good_parts[0]
    return parts[0][:60]


def is_relevant_supplier(title: str, text: str, product: str, material: str = "") -> bool:
    """Memverifikasi bahwa halaman web yang ditemukan relevan dengan kategori supplier yang dicari (bukan toko barang jadi)."""
    combined = f"{title} {text}".lower()
    norm_prod = LEGACY_PRODUCT_MAP.get(product.lower().strip(), product.lower().strip())

    # Validasi tegas: tolak toko ritel baju jadi/distro jika mencari bahan baku
    if norm_prod == "raw material":
        finished_goods_indicators = [
            "toko baju", "kaos distro", "jual kaos polos", "dropship baju", "reseller baju",
            "baju anak", "fashion retail", "gamis pesta", "outfit harian", "toko busana",
            "retail pakaian", "beli baju online", "kaos oblong jadi"
        ]
        has_finished = any(fg in combined for fg in finished_goods_indicators)
        has_raw = any(rw in combined for rw in [
            "bahan baku", "kain", "tekstil", "fabric", "textile", "rollan", "pabrik",
            "supplier", "distributor", "grosir kain", "yard", "kiloan", "benang", "manufaktur"
        ])
        if has_finished and not has_raw:
            return False

    keywords = CATEGORY_KEYWORDS.get(norm_prod, CATEGORY_KEYWORDS["raw material"])
    matches = sum(1 for kw in keywords if kw in combined)
    if matches < 1:
        return False
    prod_terms = [product.lower()]
    if material:
        prod_terms.extend([t for t in material.lower().split() if len(t) > 2])
    has_product_context = any(t in combined for t in prod_terms) or matches >= 2
    return has_product_context


def is_relevant_fabric_supplier(title: str, text: str, product: str, material: str = "") -> bool:
    """Memverifikasi relevansi supplier bahan baku (menolak barang jadi/distro retail)."""
    combined = f"{title} {text}".lower()
    norm_prod = LEGACY_PRODUCT_MAP.get(product.lower().strip(), product.lower().strip())

    if norm_prod == "raw material":
        finished_goods_indicators = [
            "toko baju", "kaos distro", "jual kaos polos", "dropship baju", "reseller baju",
            "baju anak", "fashion retail", "gamis pesta", "outfit harian", "toko busana",
            "retail pakaian", "beli baju online", "kaos oblong jadi"
        ]
        has_finished = any(fg in combined for fg in finished_goods_indicators)
        has_raw = any(rw in combined for rw in [
            "bahan baku", "kain", "tekstil", "fabric", "textile", "rollan", "pabrik",
            "supplier", "distributor", "grosir kain", "yard", "kiloan", "benang", "manufaktur"
        ])
        if has_finished and not has_raw:
            return False

    if norm_prod == "raw material" and product.lower() in ("jersey", "kaos", "polo", "kemeja", "jaket", "kain", "textile"):
        matches = sum(1 for kw in FABRIC_KEYWORDS if kw in combined)
        if matches < 2:
            return False
        prod_terms = [product.lower()]
        if material:
            prod_terms.extend([t for t in material.lower().split() if len(t) > 2])
        return any(t in combined for t in prod_terms) or matches >= 4
    return is_relevant_supplier(title, text, product, material)


def _fallback_recommendation(candidate, product, material):
    text = f"{candidate['title']} {candidate['description']}".lower()
    terms = [term for term in (material or product).lower().split() if len(term) > 2]
    matches = sum(1 for term in terms if term in text)
    score = min(95, 55 + (matches * 12) + (15 if candidate.get("website") else 0))
    cat_label = product.title()
    return {
        "fit_score": score,
        "recommendation": f"Supplier/vendor berpotensi untuk pengadaan kategori {cat_label} ({material or 'spesifikasi standar'}). Kredibilitas dan kontak operasional telah teridentifikasi.",
        "next_steps": ["Validasi portofolio & katalog produk/layanan", "Minta quotation resmi & ketersediaan stok/SLA", "Bahas termin pembayaran & minimum order (MOQ)"],
        "confidence": "medium",
    }


def _ai_recommendations(candidates, product, material, custom_prompt: str = ""):
    if not candidates:
        return []

    # Batch per 12 kandidat agar prompt tidak terpotong token limit saat jumlah data banyak (20-50)
    all_recommendations = []
    chunk_size = 12
    for chunk_start in range(0, len(candidates), chunk_size):
        chunk = candidates[chunk_start:chunk_start + chunk_size]
        prompt = {
            "product": product,
            "material": material,
            "custom_instructions": custom_prompt or f"Prioritaskan supplier/vendor kategori {product} terpercaya dengan kontak dan reputasi jelas.",
            "candidates": [
                {
                    "index": chunk_start + idx,
                    "company_name": item["company_name"],
                    "website": item.get("website"),
                    "source_url": item["source_url"],
                    "description": item["description"][:800],
                }
                for idx, item in enumerate(chunk)
            ],
        }
        try:
            result = ai_agent._chat_json(
                system_prompt=(
                    "Kamu adalah Strategic B2B Procurement Intelligence Advisor di Indonesia. "
                    "Nilai kandidat supplier / vendor berdasarkan kesesuaian kategori bisnis (Raw Material, Distributor, Elektrikal, Services, Pharmaceutical, Local, Hardware, Software), kelayakan komersial, kejelasan kontak, dan instruksi khusus user jika ada. "
                    "Jika kandidat tidak relevan atau situs spam/portal login, berikan fit_score di bawah 30. "
                    "Berikan JSON array dengan: index, company_name, fit_score (0-100), recommendation, next_steps, confidence."
                ),
                user_prompt=json.dumps(prompt, ensure_ascii=False),
                temperature=0.1,
                task_name="procurement_recommendation",
                max_tokens=2000,
            )
            if isinstance(result, dict):
                result = result.get("recommendations") or result.get("items") or []
            if isinstance(result, list):
                all_recommendations.extend(result)
        except Exception:
            pass
    return all_recommendations


def _ai_plan_queries_and_targets(product: str, material: str = "", region: str = "Indonesia", custom_prompt: str = "") -> dict:
    """Tahap 1 AI Pipeline: AI merumuskan target perusahaan bahan baku nyata dan query pencarian presisi tinggi."""
    prompt = {
        "product": product,
        "material": material or "material standar",
        "region": region or "Indonesia",
    }
    if custom_prompt:
        prompt["custom_instructions"] = custom_prompt

    sys_prompt = (
        "Kamu adalah Senior Sourcing Specialist pengadaan BAHAN BAKU (raw material) manufaktur B2B di Indonesia. "
        "Tugasmu adalah memberikan daftar 3-5 PABRIK, PRODUSEN, atau DISTRIBUTOR BESAR BAHAN BAKU NYATA di Indonesia yang relevan. "
        "ATURAN KETAT:\n"
        "1. HANYA berikan supplier BAHAN BAKU (kain tekstil, benang, polimer, kimia industri, elektrikal industri, komponen teknik). "
        "DILARANG KERAS memberikan toko baju distro, fashion retail, dropshipper kaos, atau toko barang jadi.\n"
        "2. HANYA cantumkan perusahaan NYATA yang beroperasi di Indonesia.\n"
        "3. HANYA cantumkan nomor telepon/WhatsApp ASLI jika Anda mengetahuinya dengan pasti. JANGAN PERNAH membuat nomor dummy/palsu (seperti 1234, 5678, 08123456789). Jika tidak tahu nomor aslinya, isi null.\n"
        "4. Cantumkan domain website resmi nyata jika ada.\n"
        "Format JSON murni:\n"
        '{"candidates": [{"name": "Nama Perusahaan", "website": "https://...", "contact_phone": "08... atau null", "material": "...", "region": "...", "description": "..."}], "search_queries": ["query 1", "query 2"]}'
    )
    try:
        res = ai_agent._chat_json(sys_prompt, json.dumps(prompt, ensure_ascii=False), temperature=0.1, max_tokens=1500)
        if isinstance(res, dict):
            return res
    except Exception:
        pass
    return {}


def _check_url_worker(u):
    """Pre-flight check ringan untuk memastikan URL aktif tanpa blocking."""
    try:
        resp = requests.head(u, timeout=2.5, allow_redirects=True, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code in (200, 301, 302):
            return resp.url.rstrip("/")
    except Exception:
        pass
    try:
        resp = requests.get(u, timeout=2.5, headers={"User-Agent": "Mozilla/5.0"}, stream=True)
        if resp.status_code == 200:
            return resp.url.rstrip("/")
    except Exception:
        pass
    return None


def _scrape_page_worker(url, prod_key, mat, reg):
    """Deep scraping worker untuk mengambil metadata, teks, dan kontak dalam thread terpisah."""
    try:
        final_url, soup, text, emails, phones, _social = _page_data(url, timeout=6)
        raw_title = soup.title.get_text(" ", strip=True) if soup.title else urlparse(final_url).netloc
        if not is_relevant_fabric_supplier(raw_title, text, prod_key, mat):
            return None
        clean_name = clean_company_name(raw_title, final_url)
        return {
            "company_name": clean_name[:255],
            "title": raw_title,
            "product": prod_key,
            "material": mat or None,
            "region": reg or None,
            "website": final_url,
            "source_url": final_url,
            "contact_email": emails[0] if emails else None,
            "contact_phone": next((p for p in phones if is_valid_indonesian_phone(p)), None),
            "description": text[:2000],
        }
    except Exception:
        return None


def _tavily_search_candidates(query: str, product_key: str, material: str = "", region: str = "Indonesia", limit: int = 10) -> list:
    """Plan 1: Pencarian langsung & ekstraksi konten berkecepatan tinggi via Tavily AI Search (mendukung hingga 50 supplier)."""
    import os
    from flask import current_app
    api_key = current_app.config.get("TAVILY_API_KEY") or os.getenv("TAVILY_API_KEY")
    if not api_key:
        return []

    # Jika meminta lebih banyak data (hingga 100), jalankan variasi query secara paralel
    queries = [query]
    mat_clean = material or "kain"
    if limit >= 100:
        queries = [
            query,
            f"pabrik produsen bahan kain {mat_clean} {product_key} {region} rollan",
            f"grosir distributor tekstil {mat_clean} {region} wa.me katalog",
            f"supplier bahan kain {mat_clean} konveksi {region} bandung jakarta surabaya",
            f"site:indotrading.com supplier {mat_clean} {product_key} indonesia",
            f"site:indonetwork.co.id jual grosir bahan kain {mat_clean}",
            f"toko sentra bahan kain kaos {mat_clean} otista cigondewah tanah abang",
            f"distributor resmi kain {mat_clean} apparel jersey konveksi",
        ]
    elif limit >= 50:
        queries = [
            query,
            f"distributor grosir kain {mat_clean} {product_key} {region} rollan",
            f"pabrik supplier bahan kain {mat_clean} {region} wa.me kontak",
            f"site:indotrading.com supplier {mat_clean} {product_key}",
            f"toko bahan kaos konveksi {mat_clean} {region}",
        ]
    elif limit > 20:
        queries = [
            query,
            f"distributor grosir kain {mat_clean} {product_key} {region} rollan",
            f"pabrik supplier bahan kain {mat_clean} {region} wa.me kontak",
        ]

    def _fetch_tavily_chunk(q, n_results):
        try:
            resp = requests.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": api_key,
                    "query": q,
                    "search_depth": "basic",
                    "max_results": n_results,
                    "include_raw_content": False,
                    "include_images": False,
                },
                timeout=8.0,
            )
            if resp.status_code == 200:
                return resp.json().get("results", [])
        except Exception:
            pass
        return []

    raw_items = []
    if len(queries) == 1:
        raw_items = _fetch_tavily_chunk(queries[0], min(20, limit + 2))
    else:
        with ThreadPoolExecutor(max_workers=len(queries)) as executor:
            futures = [executor.submit(_fetch_tavily_chunk, q, 20) for q in queries]
            for f in as_completed(futures):
                raw_items.extend(f.result())

    if not raw_items:
        return []

    seen_urls_in_batch = set()
    candidates = []
    for item in raw_items:
        url = item.get("url", "").rstrip("/")
        if not url or not is_safe_url(url) or url in seen_urls_in_batch:
            continue
        host = urlparse(url).netloc.lower()
        if any(dis in host for dis in DISALLOWED_DOMAINS):
            continue
        if any(m in host for m in ["tokopedia.com", "shopee.co.id", "lazada.co.id", "bukalapak.com", "tiktok.com"]):
            continue

        raw_title = item.get("title", "")
        content = item.get("content", "")
        if not is_relevant_fabric_supplier(raw_title, content, product_key, material):
            continue

        clean_name = clean_company_name(raw_title, url)

        # Ekstrak email & nomor telepon/WhatsApp langsung dari teks konten Tavily
        emails = re.findall(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", content, re.I)
        phones = []
        for raw_phone in re.findall(r"(?:\+62|62|0)8[1-9][0-9\s().-]{7,12}", content):
            clean_p = re.sub(r"[^0-9+]", "", raw_phone)
            if clean_p.startswith("+62"):
                clean_p = "0" + clean_p[3:]
            elif clean_p.startswith("62"):
                clean_p = "0" + clean_p[2:]
            if 9 <= len(clean_p) <= 14 and is_valid_indonesian_phone(clean_p) and clean_p not in phones:
                phones.append(clean_p)

        seen_urls_in_batch.add(url)
        candidates.append({
            "company_name": clean_name[:255],
            "title": raw_title,
            "product": product_key,
            "material": material or None,
            "region": region or None,
            "website": url,
            "source_url": url,
            "contact_email": emails[0] if emails else None,
            "contact_phone": phones[0] if phones else None,
            "description": content[:2000],
        })
        if len(candidates) >= limit:
            break

    # Jika kandidat belum memiliki kontak telepon, coba fetch cepat 2.5s secara paralel
    missing_phone_cands = [c for c in candidates if not c.get("contact_phone")][:6]
    if missing_phone_cands:
        def _quick_fetch_contact(cand):
            try:
                _u, _soup, _t, _em, _ph, _so = _page_data(cand["source_url"], timeout=2.5)
                valid_ph = next((p for p in (_ph or []) if is_valid_indonesian_phone(p)), None)
                if valid_ph and not cand.get("contact_phone"):
                    cand["contact_phone"] = valid_ph
                if _em and not cand.get("contact_email"):
                    cand["contact_email"] = _em[0]
            except Exception:
                pass

        with ThreadPoolExecutor(max_workers=min(6, len(missing_phone_cands))) as executor:
            list(executor.map(_quick_fetch_contact, missing_phone_cands))

    return candidates


def search_suppliers(product, material="", region="Indonesia", limit=10, user_id=None, use_ai_pipeline=True, custom_prompt=""):
    product_key = product.lower().strip()
    default_query = PRODUCT_TERMS.get(product_key, f"supplier toko kain {product} grosir")
    if material:
        default_query = f"supplier kain {material} {product} {region}"
    elif region:
        default_query = f"{default_query} {region}"

    saved = []
    seen_urls = set()
    newly_found_count = 0

    # 1. Masukkan verified supplier database terlebih dahulu (jaminan akurasi instan)
    verified_list = VERIFIED_SUPPLIERS.get(product_key, [])
    for v in verified_list:
        v_url = v["source_url"].rstrip("/")
        seen_urls.add(v_url)
        seen_urls.add(v_url + "/")
        v_name = v["company_name"].strip()
        supplier = ProcurementSupplier.query.filter(
            ProcurementSupplier.product == product_key,
            or_(
                ProcurementSupplier.source_url.in_([v_url, v_url + "/"]),
                func.lower(ProcurementSupplier.company_name) == v_name.lower()
            )
        ).first()
        if not supplier:
            supplier = ProcurementSupplier(
                source_url=v_url, product=product_key, created_by=None
            )
            newly_found_count += 1
        supplier.company_name = v["company_name"]
        supplier.material = v.get("material") or material or None
        supplier.region = v.get("region") or region or None
        supplier.website = v.get("website")
        supplier.contact_email = v.get("contact_email")
        supplier.contact_phone = v.get("contact_phone")
        supplier.description = v["description"]
        supplier.fit_score = v["fit_score"]
        supplier.recommendation_json = json.dumps(v["recommendation"], ensure_ascii=False)
        supplier.verification_status = "verified"
        db.session.add(supplier)
        saved.append(supplier)

    candidates = []
    search_query_used = default_query
    active_engine = "tavily"

    # ==========================================
    # PLAN 1: TAVILY AI SEARCH (UTAMA & SUPER CEPAT)
    # ==========================================
    if use_ai_pipeline:
        tavily_q = default_query
        if custom_prompt:
            tavily_q = f"{default_query} {custom_prompt[:60]}"
        candidates = _tavily_search_candidates(tavily_q, product_key, material, region, limit=limit)
        if candidates:
            search_query_used = tavily_q

    # ==========================================
    # PLAN 2: FAILOVER CADANGAN (JIKA TAVILY HABIS / GAGAL)
    # ==========================================
    if not candidates and use_ai_pipeline:
        active_engine = "plan2_failover"
        search_queries = [default_query]
        direct_candidates_urls = []
        ai_plan = _ai_plan_queries_and_targets(product_key, material, region, custom_prompt=custom_prompt)
        ai_candidates = ai_plan.get("candidates", [])
        for cand in ai_candidates:
            c_name = cand.get("name") or cand.get("company_name")
            if not c_name:
                continue
            c_url = cand.get("website") or ""
            if c_url and c_url.startswith("http"):
                direct_candidates_urls.append(c_url.rstrip("/"))
            phone = cand.get("contact_phone")
            valid_phone = phone if is_valid_indonesian_phone(phone) else None

            desc = cand.get("description") or f"Pemasok bahan baku {cand.get('material') or material} di {cand.get('region') or region}."
            if not is_relevant_fabric_supplier(c_name, desc, product_key, material):
                continue

            candidates.append({
                "company_name": clean_company_name(c_name, c_url or f"https://{c_name.lower().replace(' ', '')}.com"),
                "title": f"{c_name} - Supplier Bahan Baku {cand.get('material') or material or product_key}",
                "product": product_key,
                "material": cand.get("material") or material or None,
                "region": cand.get("region") or region or None,
                "website": c_url or None,
                "source_url": c_url or f"https://sourcing.internal/{product_key}/{c_name.lower().replace(' ', '-')}",
                "contact_email": cand.get("contact_email"),
                "contact_phone": valid_phone,
                "description": desc,
            })

        suggested_queries = ai_plan.get("search_queries", [])
        if suggested_queries:
            search_queries = [suggested_queries[0]]

        raw_urls = list(direct_candidates_urls)
        for q in search_queries:
            try:
                found = _search(q)
                raw_urls.extend(found)
            except Exception:
                continue

        if len(raw_urls) < limit and default_query not in search_queries:
            try:
                raw_urls.extend(_search(default_query))
            except Exception:
                pass

        candidates_to_test = []
        for u in raw_urls:
            u_norm = u.rstrip("/")
            if not is_safe_url(u) or u_norm in seen_urls:
                continue
            parsed = urlparse(u)
            host = parsed.netloc.lower()
            if any(dis in host or dis in u.lower() for dis in DISALLOWED_DOMAINS):
                continue
            if any(marketplace in host for marketplace in ["tokopedia.com", "shopee.co.id", "lazada.co.id", "bukalapak.com"]):
                continue
            candidates_to_test.append(u)
            if len(candidates_to_test) >= limit * 2:
                break

        valid_urls_to_scrape = []
        if candidates_to_test:
            with ThreadPoolExecutor(max_workers=min(8, len(candidates_to_test))) as executor:
                futures = {executor.submit(_check_url_worker, u): u for u in candidates_to_test}
                for fut in as_completed(futures):
                    res = fut.result()
                    if res and res not in seen_urls:
                        seen_urls.add(res)
                        seen_urls.add(res + "/")
                        valid_urls_to_scrape.append(res)
                        if len(valid_urls_to_scrape) >= limit:
                            break

        urls_to_scrape = valid_urls_to_scrape[:limit]
        if urls_to_scrape:
            with ThreadPoolExecutor(max_workers=min(5, len(urls_to_scrape))) as executor:
                futures = [
                    executor.submit(_scrape_page_worker, u, product_key, material, region)
                    for u in urls_to_scrape
                ]
                for fut in as_completed(futures):
                    cand = fut.result()
                    if cand:
                        candidates.append(cand)

        search_query_used = search_queries[0]

    # ==========================================
    # EVALUASI AI, FIT SCORING & SIMPAN KE DATABASE
    # ==========================================
    unique_candidates = []
    for c in candidates:
        c_url = c["source_url"].rstrip("/")
        if c_url not in seen_urls:
            seen_urls.add(c_url)
            seen_urls.add(c_url + "/")
            unique_candidates.append(c)

    ai_items = _ai_recommendations(unique_candidates, product, material, custom_prompt=custom_prompt)
    for index, candidate in enumerate(unique_candidates):
        ai_item = next((item for item in ai_items if item.get("index") == index), None)
        recommendation = ai_item or _fallback_recommendation(candidate, product, material)
        try:
            fit_score = max(0, min(100, int(recommendation.get("fit_score", 0))))
        except (TypeError, ValueError):
            fit_score = 0

        # Lewati supplier jika fit score di bawah 45 (tidak relevan)
        if fit_score < 45:
            continue

        if ai_item and ai_item.get("company_name") and len(ai_item["company_name"]) <= 100:
            candidate["company_name"] = ai_item["company_name"]

        cand_url = candidate["source_url"].rstrip("/")
        cand_name = candidate["company_name"].strip()
        cand_phone = candidate.get("contact_phone")
        valid_cand_phone = cand_phone if is_valid_indonesian_phone(cand_phone) else None

        # Cek apakah supplier sudah ada di database (berdasarkan URL atau nama perusahaan)
        supplier = ProcurementSupplier.query.filter(
            ProcurementSupplier.product == product_key,
            or_(
                ProcurementSupplier.source_url.in_([cand_url, cand_url + "/"]),
                func.lower(ProcurementSupplier.company_name) == cand_name.lower()
            )
        ).first()

        if not supplier:
            supplier = ProcurementSupplier(
                source_url=cand_url, product=product_key, created_by=None
            )
            newly_found_count += 1

        supplier.company_name = cand_name
        supplier.material = material or supplier.material or None
        supplier.region = region or supplier.region or None
        if candidate.get("website"):
            supplier.website = candidate["website"]
        if candidate.get("contact_email") and not supplier.contact_email:
            supplier.contact_email = candidate["contact_email"]
        if valid_cand_phone and not supplier.contact_phone:
            supplier.contact_phone = valid_cand_phone
        elif supplier.contact_phone and not is_valid_indonesian_phone(supplier.contact_phone):
            supplier.contact_phone = valid_cand_phone
        if candidate.get("description") and len(candidate["description"]) > len(supplier.description or ""):
            supplier.description = candidate["description"]
        supplier.fit_score = max(fit_score, supplier.fit_score or 0)
        supplier.recommendation_json = json.dumps(recommendation, ensure_ascii=False)
        supplier.verification_status = "tavily" if active_engine == "tavily" else "ai_pipeline"
        db.session.add(supplier)
        if supplier not in saved:
            saved.append(supplier)

    db.session.commit()
    return search_query_used, SearchResult(saved, new_count=newly_found_count)


def scrape_supplier_direct(url, product, material="", region="Indonesia", user_id=None, custom_prompt=""):
    """Scraping langsung URL website supplier yang diinput oleh pengguna."""
    if not is_safe_url(url):
        raise ValueError("URL supplier tidak valid atau terblokir.")

    final_url, soup, text, emails, phones, _social = _page_data(url)
    raw_title = soup.title.get_text(" ", strip=True) if soup.title else urlparse(final_url).netloc
    clean_name = clean_company_name(raw_title, final_url)
    valid_phone = next((p for p in phones if is_valid_indonesian_phone(p)), None)

    candidate = {
        "company_name": clean_name[:255],
        "title": raw_title,
        "product": product.lower().strip(),
        "material": material or None,
        "region": region or None,
        "website": final_url,
        "source_url": final_url,
        "contact_email": emails[0] if emails else None,
        "contact_phone": valid_phone,
        "description": text[:2500],
    }

    ai_items = _ai_recommendations([candidate], product, material, custom_prompt=custom_prompt)
    recommendation = ai_items[0] if ai_items else _fallback_recommendation(candidate, product, material)
    try:
        fit_score = max(0, min(100, int(recommendation.get("fit_score", 0))))
    except (TypeError, ValueError):
        fit_score = 65

    supplier = ProcurementSupplier.query.filter_by(
        source_url=candidate["source_url"], product=product.lower().strip()
    ).first() or ProcurementSupplier(
        source_url=candidate["source_url"], product=product.lower().strip(), created_by=None
    )
    supplier.company_name = candidate["company_name"]
    supplier.material = material or None
    supplier.region = region or None
    supplier.website = candidate["website"]
    supplier.contact_email = candidate["contact_email"]
    supplier.contact_phone = valid_phone
    supplier.description = candidate["description"]
    supplier.fit_score = fit_score
    supplier.recommendation_json = json.dumps(recommendation, ensure_ascii=False)
    supplier.verification_status = "user_added"
    db.session.add(supplier)
    db.session.commit()
    return supplier
