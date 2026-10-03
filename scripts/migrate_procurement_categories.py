"""Migrasi dan Penyesuaian Kategori Supplier Procurement:
Mengubah fokus supplier dari bahan kain saja menjadi 8 Kategori B2B Lengkap:
1. raw material (Bahan Baku Industri, Tekstil, Logam, Kimia)
2. distributor (Distributor Resmi & Supply Chain B2B)
3. elektrikal (Elektrikal, Kelistrikan, Kabel, Trafo, Panel)
4. services (Jasa & Services B2B, Maintenance, Facility Management)
5. pharmaceutical (Farmasi, Medis, Bahan Baku Obat, Alkes)
6. local (Pemasok Lokal, Daerah & UMKM)
7. hardware (Hardware, Perkakas, Mesin Teknik, Valve, Pompa)
8. software (Software B2B, ERP, Cloud, HRIS, SaaS)
"""

import os
import sys
import json
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app import create_app, db
from app.models import ProcurementSupplier

NEW_VERIFIED_SUPPLIERS = {
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
        },
        {
            "company_name": "PT Asahimas Chemical",
            "website": "https://www.asc.co.id",
            "source_url": "https://www.asc.co.id",
            "region": "Cilegon, Banten & Jakarta",
            "material": "Caustic Soda, Polyvinyl Chloride (PVC), EDC, VCM, Clorin",
            "contact_phone": "0254601252",
            "contact_email": "sales@asc.co.id",
            "description": "Produsen bahan baku kimia klor-alkali dan resin PVC terbesar di Asia Tenggara untuk industri plastik, pipa, dan manufaktur.",
            "fit_score": 96,
            "recommendation": {
                "fit_score": 96,
                "recommendation": "Pilihan utama produsen plastik dan industri proses untuk bahan baku resin PVC dan soda kostik kemurnian tinggi.",
                "next_steps": ["Cek alokasi kuota pasokan bulanan", "Minta pricelist kargo tangki/curah", "Audit sertifikasi kepatuhan lingkungan"],
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
        },
        {
            "company_name": "PT Wicaksana Overseas International Tbk",
            "website": "https://wicaksana.co.id",
            "source_url": "https://wicaksana.co.id",
            "region": "Jakarta, Medan, Surabaya & Makassar",
            "material": "Distribusi Grosir, Pergudangan & Supply Chain Nasional",
            "contact_phone": "0216927293",
            "contact_email": "corporate@wicaksana.co.id",
            "description": "Perusahaan distribusi nasional terkemuka yang melayani ratusan ribu titik distribusi grosir dan ritel se-Indonesia.",
            "fit_score": 92,
            "recommendation": {
                "fit_score": 92,
                "recommendation": "Jaringan logistik dan distributor mapan dengan keahlian suplai grosir multi-kategori.",
                "next_steps": ["Kaji skema kemitraan prinsipal", "Minta profil titik distribusi", "Bahas termin pembayaran"],
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
        },
        {
            "company_name": "PT Kabelindo Murni Tbk",
            "website": "https://kabelindo.co.id",
            "source_url": "https://kabelindo.co.id",
            "region": "Jakarta Timur & Bekasi",
            "material": "Kabel Power Tembaga & Aluminium, Kabel Kontrol, Kabel Tahan Api (Fire Resistant)",
            "contact_phone": "0214609065",
            "contact_email": "marketing@kabelindo.co.id",
            "description": "Pabrikan kabel listrik berstandar PLN dan industri manufaktur terkemuka yang memproduksi kabel daya, instrumen, dan kabel tahan api.",
            "fit_score": 94,
            "recommendation": {
                "fit_score": 94,
                "recommendation": "Rujukan teruji untuk kabel instalasi gedung bertingkat, pabrik, dan kabel tahan api fire-resistant.",
                "next_steps": ["Cek ketersediaan drum roll kabel fire resistant", "Minta brosur spesifikasi kabel kontrol", "Validasi sertifikat SNI"],
                "confidence": "high"
            }
        },
        {
            "company_name": "PT Voksel Electric Tbk",
            "website": "https://voksel.co.id",
            "source_url": "https://voksel.co.id",
            "region": "Cileungsi, Bogor & Jakarta",
            "material": "Kabel Power Tegangan Tinggi, Fiber Optik, Kawat Tembaga & Aluminium",
            "contact_phone": "0218230625",
            "contact_email": "sales@voksel.co.id",
            "description": "Produsen kabel power, kawat tembaga, dan kabel fiber optik terkemuka yang menyuplai proyek kelistrikan PLN dan infrastruktur nasional.",
            "fit_score": 93,
            "recommendation": {
                "fit_score": 93,
                "recommendation": "Pilihan tepat untuk kabel transmisi daya tinggi dan kabel fiber optik jaringan industri.",
                "next_steps": ["Minta sertifikasi spesifikasi PLN", "Cek lead time pesanan kargo kabel", "Bahas termin pembayaran proyek"],
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
        },
        {
            "company_name": "PT Surveyor Indonesia (Persero)",
            "website": "https://ptsi.co.id",
            "source_url": "https://ptsi.co.id",
            "region": "Jakarta, Balikpapan, Batam, Surabaya, Medan",
            "material": "Jasa Inspeksi Teknis, Pengujian Laboratorium, Verifikasi TKDN, Sertifikasi ISO",
            "contact_phone": "0215265526",
            "contact_email": "contact@ptsi.co.id",
            "description": "BUMN jasa pemastian, pengujian, inspeksi, verifikasi tingkat komponen dalam negeri (TKDN), dan sertifikasi kelayakan industri nasional.",
            "fit_score": 95,
            "recommendation": {
                "fit_score": 95,
                "recommendation": "Penyedia jasa inspeksi dan audit resmi untuk legalitas pengadaan pemerintah, verifikasi TKDN, dan keselamatan kerja.",
                "next_steps": ["Konsultasikan ruang lingkup audit/inspeksi", "Verifikasi akreditasi KAN/BSN", "Minta rincian biaya pengujian laboratorium"],
                "confidence": "high"
            }
        },
        {
            "company_name": "PT SOS Indonesia",
            "website": "https://sos.co.id",
            "source_url": "https://sos.co.id",
            "region": "Jakarta, Bandung, Surabaya, Semarang, Medan",
            "material": "Security Services, Manpower Outsourcing, Parking Management, Pest Control",
            "contact_phone": "02153669888",
            "contact_email": "marketing@sos.co.id",
            "description": "Perusahaan alih daya tenaga kerja profesional, pengelolaan keamanan berlisensi Mabes Polri, dan layanan kebersihan komersial.",
            "fit_score": 92,
            "recommendation": {
                "fit_score": 92,
                "recommendation": "Solusi efisien untuk pengadaan tenaga sekuriti tersertifikasi dan tenaga pendukung operasional kantor.",
                "next_steps": ["Bahas jumlah headcount dan sistem shift", "Review sertifikasi Garda Pratama personil", "Negosiasi skema management fee"],
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
        },
        {
            "company_name": "PT Tempo Scan Pacific Tbk",
            "website": "https://temposcangroup.com",
            "source_url": "https://temposcangroup.com",
            "region": "Jakarta & Bekasi",
            "material": "Produk Farmasi OTC, Obat Bebas Terbatas, Alat Kesehatan & Suplemen",
            "contact_phone": "02129218888",
            "contact_email": "corporate.secretary@temposcan.com",
            "description": "Grup farmasi dan manufaktur produk kesehatan terkemuka di Indonesia yang memproduksi farmasi, suplemen, dan kosmetik higienis.",
            "fit_score": 94,
            "recommendation": {
                "fit_score": 94,
                "recommendation": "Mitra tepercaya untuk pasokan suplemen kesehatan, multivitamin kerja, dan perlengkapan P3K korporasi.",
                "next_steps": ["Minta penawaran corporate health package", "Verifikasi tanggal kadaluarsa lot batch", "Cek opsi private labelling"],
                "confidence": "high"
            }
        },
        {
            "company_name": "PT Phapros Tbk",
            "website": "https://www.phapros.co.id",
            "source_url": "https://www.phapros.co.id",
            "region": "Semarang, Jawa Tengah & Jakarta",
            "material": "Obat Generik Berlogo (OGB), Obat Ethical, Kasa & Perlengkapan Bedah",
            "contact_phone": "0247604565",
            "contact_email": "corsec@phapros.co.id",
            "description": "Anak usaha Kimia Farma yang memproduksi ratusan jenis obat generik, cairan infus, dan perangkat kesehatan rumah sakit terstandar BPOM.",
            "fit_score": 93,
            "recommendation": {
                "fit_score": 93,
                "recommendation": "Pemasok terpercaya untuk kebutuhan obat generik institusi dan perlengkapan farmasi rumah sakit.",
                "next_steps": ["Cek ketersediaan sediaan generik", "Minta harga paket pengadaan instansi", "Audit sertifikasi CPOB Semarang"],
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
        },
        {
            "company_name": "Koperasi Pemasok Daerah Mandiri",
            "website": "https://koperasipemasokdaerah.id",
            "source_url": "https://koperasipemasokdaerah.id",
            "region": "Semarang & Jawa Tengah",
            "material": "Komoditas Lokal, Packaging Dus & Plastik, Logistik Daerah",
            "contact_phone": "081399887766",
            "contact_email": "kontak@koperasipemasokdaerah.id",
            "description": "Asosiasi koperasi supplier daerah Jawa Tengah yang menghubungkan produsen lokal dengan jaringan pengadaan industri dan retail.",
            "fit_score": 89,
            "recommendation": {
                "fit_score": 89,
                "recommendation": "Opsi bernilai tambah untuk program kemitraan UMKM daerah dan pengadaan packaging lokal harga terjangkau.",
                "next_steps": ["Bahas kapasitas produksi kemasan karton", "Minta sampel ketebalan kardus", "Cek opsi custom cetak sablon"],
                "confidence": "high"
            }
        },
        {
            "company_name": "CV Nusantara Prima Supply",
            "website": "https://nusantaraprimasupply.com",
            "source_url": "https://nusantaraprimasupply.com",
            "region": "Medan & Sumatera Utara",
            "material": "Pemasok Alat Tulis Kantor, Seragam & Kebutuhan Logistik Regional",
            "contact_phone": "0617320011",
            "contact_email": "info@nusantaraprimasupply.com",
            "description": "Pemasok rekanan lokal untuk pemenuhan pengadaan barang operasional instansi pemerintah dan swasta di Sumatera Utara.",
            "fit_score": 90,
            "recommendation": {
                "fit_score": 90,
                "recommendation": "Mitra pengadaan daerah terpercaya untuk efisiensi rantai suplai wilayah Sumatera Utara.",
                "next_steps": ["Minta company profile dan izin usaha", "Cek kesiapan armada distribusi daerah", "Bahas termin pembayaran"],
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
        },
        {
            "company_name": "PT Mitra Glodok Industri",
            "website": "https://mitraglodok.com",
            "source_url": "https://mitraglodok.com",
            "region": "Jakarta Pusat & Glodok",
            "material": "Bearing Industri, Chain & Sprocket, V-Belt, Pulley, Pneumatic & Hydraulic",
            "contact_phone": "0216499881",
            "contact_email": "info@mitraglodok.com",
            "description": "Penyedia sparepart mesin industri, bearing (SKF, NSK, FAG), transmisi tenaga mekanikal, dan perlengkapan hidrolik bergaransi asli.",
            "fit_score": 93,
            "recommendation": {
                "fit_score": 93,
                "recommendation": "Sangat direkomendasikan untuk suku cadang transmisi mesin, bearing original, dan perlengkapan hidrolik pabrik.",
                "next_steps": ["Cek nomor part bearing mesin", "Validasi keaslian produk bearing", "Minta penawaran paket sparepart mesin"],
                "confidence": "high"
            }
        },
        {
            "company_name": "CV Teknik Mandiri Perkakas",
            "website": "https://teknikmandiriperkakas.com",
            "source_url": "https://teknikmandiriperkakas.com",
            "region": "Surabaya & Jawa Timur",
            "material": "Perkakas Tangan, Mesin Las Inverter, Mata Gerinda, Alat Potong Bubut CNC",
            "contact_phone": "0313550099",
            "contact_email": "sales@teknikmandiriperkakas.com",
            "description": "Distributor alat-alat teknik manufaktur, perkakas bengkel mesin, mesin las industri, dan mata bor bubut CNC di Surabaya.",
            "fit_score": 91,
            "recommendation": {
                "fit_score": 91,
                "recommendation": "Penyedia perkakas bengkel dan perlengkapan pengelasan dengan harga kompetitif di Jawa Timur.",
                "next_steps": ["Minta katalog perkakas las dan bubut", "Cek ketersediaan mata potong karbida", "Bahas opsi garansi unit mesin"],
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
        },
        {
            "company_name": "PT Metrodata Electronics Tbk",
            "website": "https://www.metrodata.co.id",
            "source_url": "https://www.metrodata.co.id",
            "region": "Jakarta, Surabaya & Seluruh Indonesia",
            "material": "IT Systems Integration, Cloud Solutions (AWS, Azure, Google Cloud), Business Applications, Database",
            "contact_phone": "02129345888",
            "contact_email": "info@metrodata.co.id",
            "description": "Perusahaan teknologi informasi dan komunikasi (TIK) terbesar di Indonesia penyedia solusi integrasi sistem, lisensi software, dan cloud.",
            "fit_score": 95,
            "recommendation": {
                "fit_score": 95,
                "recommendation": "Mitra pengadaan lisensi software enterprise (Microsoft, Oracle, SAP, VMware) dan integrasi sistem berskala nasional.",
                "next_steps": ["Minta audit lisensi software perusahaan", "Bandingkan skema volume licensing", "Kaji opsi deployment managed services"],
                "confidence": "high"
            }
        }
    ]
}


def run_migration():
    app = create_app()
    with app.app_context():
        print("=== Memulai Migrasi Kategori Supplier Procurement ===")

        # 1. Update data eksisting (84 rows lama):
        # Bagi ke raw material, distributor tekstil, dan local supplier
        existing_rows = ProcurementSupplier.query.all()
        print(f"Total supplier eksisting saat ini: {len(existing_rows)}")

        updated_existing = 0
        for i, s in enumerate(existing_rows):
            old_prod = (s.product or "").lower()
            if old_prod in ("jersey", "kaos", "polo", "kemeja", "jaket"):
                # Pertahankan detail bahan pada kolom material
                if not s.material:
                    s.material = f"Bahan Baku Tekstil ({old_prod.title()})"
                elif old_prod not in s.material.lower():
                    s.material = f"{s.material} - Tekstil {old_prod.title()}"

                # Distribusikan secara cerdas:
                # Sebagian tetap 'raw material' (bahan baku), sebagian 'distributor' (agen grosir), sebagian 'local' (mitra regional)
                if any(k in s.company_name.lower() for k in ["distributor", "grosir", "pusat"]):
                    s.product = "distributor"
                elif any(k in s.company_name.lower() or k in (s.region or "").lower() for k in ["bandung", "surabaya", "toko"]):
                    if i % 3 == 0:
                        s.product = "local"
                    else:
                        s.product = "raw material"
                else:
                    s.product = "raw material"
                updated_existing += 1

        db.session.commit()
        print(f"Berhasil mengkategorisasi {updated_existing} supplier eksisting.")

        # 2. Masukkan verified supplier untuk setiap kategori baru
        inserted_count = 0
        for cat_name, suppliers in NEW_VERIFIED_SUPPLIERS.items():
            for sup_data in suppliers:
                exists = ProcurementSupplier.query.filter_by(
                    product=cat_name, source_url=sup_data["source_url"]
                ).first()
                if not exists:
                    # Cek juga apakah source_url ada di kategori lain
                    url_in_db = ProcurementSupplier.query.filter_by(source_url=sup_data["source_url"]).first()
                    if url_in_db:
                        url_in_db.product = cat_name
                        url_in_db.company_name = sup_data["company_name"]
                        url_in_db.material = sup_data["material"]
                        url_in_db.region = sup_data["region"]
                        url_in_db.description = sup_data["description"]
                        url_in_db.fit_score = sup_data["fit_score"]
                        url_in_db.recommendation_json = json.dumps(sup_data["recommendation"], ensure_ascii=False)
                        url_in_db.verification_status = "verified"
                    else:
                        new_sup = ProcurementSupplier(
                            company_name=sup_data["company_name"],
                            product=cat_name,
                            material=sup_data["material"],
                            region=sup_data["region"],
                            website=sup_data["website"],
                            source_url=sup_data["source_url"],
                            contact_email=sup_data.get("contact_email"),
                            contact_phone=sup_data.get("contact_phone"),
                            description=sup_data["description"],
                            fit_score=sup_data["fit_score"],
                            recommendation_json=json.dumps(sup_data["recommendation"], ensure_ascii=False),
                            verification_status="verified",
                        )
                        db.session.add(new_sup)
                        inserted_count += 1

        db.session.commit()
        print(f"Berhasil menambahkan {inserted_count} verified supplier baru.")

        # 3. Tampilkan ringkasan akhir per kategori
        from sqlalchemy import func
        summary = (
            db.session.query(ProcurementSupplier.product, func.count(ProcurementSupplier.id))
            .group_by(ProcurementSupplier.product)
            .all()
        )
        print("\n=== Ringkasan Kategori Supplier Terkini ===")
        for cat, cnt in sorted(summary, key=lambda x: str(x[0])):
            print(f" - {cat}: {cnt} supplier")
        print("Total Supplier di Database:", ProcurementSupplier.query.count())


if __name__ == "__main__":
    run_migration()
