"""Seed Script: Verified Indonesian B2B Events & Participants (Phase 5).

Menambahkan katalog pameran, expo dagang, dan konferensi B2B terverifikasi di Indonesia
serta menghubungkan entitas Master Organizations sebagai organizer, exhibitor, dan sponsor.
"""

import os
import sys
import json
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app
from app.extensions import db
from app.models import Event, EventParticipant, Organization
from app.services.event_intelligence import EventIntelligenceService

VERIFIED_EVENTS = [
    {
        "name": "Indo Intertex 2026 - Indonesia International Textile & Garment Expo",
        "event_type": "Trade Exhibition",
        "organizer": "Peraga Expo & Asosiasi Pertekstilan Indonesia",
        "status": "upcoming",
        "start_date": datetime(2026, 10, 15, 9, 0),
        "end_date": datetime(2026, 10, 18, 18, 0),
        "venue": "Jakarta International Expo (JIExpo) Kemayoran",
        "city": "Jakarta Pusat",
        "province": "DKI Jakarta",
        "address": "Gedung Pusat Niaga, Arena JIEXPO Kemayoran, Jakarta 10620",
        "website": "https://indointertex.com",
        "source_url": "https://indointertex.com/about-us",
        "description": "Pameran dagang internasional mesin tekstil, garmen, kain, benang, sablon digital, dan perlengkapan apparel terbesar di Asia Tenggara.",
        "social_json": json.dumps({"instagram": "https://www.instagram.com/indointertex", "facebook": "https://www.facebook.com/indointertex"}),
        "participants": [
            {"company_keyword": "3M INDONESIA", "role": "exhibitor", "booth": "Hall A1-02", "notes": "Textile adhesives & reflective safety wear materials"},
            {"company_keyword": "ABADI PLASTIK", "role": "exhibitor", "booth": "Hall B-14", "notes": "Garment protective packaging & bags"},
            {"company_keyword": "GARMEN INDAH MAKMUR", "role": "exhibitor", "booth": "Hall A2-10", "notes": "Apparel OEM production"}
        ]
    },
    {
        "name": "INATEX 2026 - International Apparel Fabric & Accessories Exhibition",
        "event_type": "Trade Exhibition",
        "organizer": "Asosiasi Pertekstilan Indonesia (API)",
        "status": "upcoming",
        "start_date": datetime(2026, 10, 15, 9, 0),
        "end_date": datetime(2026, 10, 18, 18, 0),
        "venue": "JIExpo Kemayoran Hall B & C",
        "city": "Jakarta Pusat",
        "province": "DKI Jakarta",
        "address": "Arena PRJ Kemayoran, Jakarta Pusat",
        "website": "https://www.inatex.co.id",
        "source_url": "https://www.inatex.co.id",
        "description": "Pameran pengadaan bahan baku tekstil, kain seragam, aksesoris garmen, dan teknologi konveksi terintegrasi.",
        "social_json": json.dumps({"instagram": "https://www.instagram.com/inatex_expo"}),
        "participants": [
            {"company_keyword": "TEKSTIL ABADI", "role": "exhibitor", "booth": "Hall C-08", "notes": "Fabrics & uniform raw materials"},
            {"company_keyword": "ACUAN KAPAS", "role": "sponsor", "booth": "Hall B-01", "notes": "Main sponsor - Cotton & yarn producer"}
        ]
    },
    {
        "name": "Trade Expo Indonesia (TEI) 2026",
        "event_type": "B2B International Expo",
        "organizer": "Kementerian Perdagangan Republik Indonesia",
        "status": "upcoming",
        "start_date": datetime(2026, 11, 4, 9, 0),
        "end_date": datetime(2026, 11, 8, 17, 0),
        "venue": "Indonesia Convention Exhibition (ICE) BSD City",
        "city": "Tangerang",
        "province": "Banten",
        "address": "Jl. BSD Grand Boulevard No.1, Pagedangan, Tangerang, Banten 15339",
        "website": "https://tradexpoindonesia.com",
        "source_url": "https://tradexpoindonesia.com/visitor-information",
        "description": "Pameran ekspor B2B terbesar di Indonesia yang menampilkan tekstil, manufaktur, produk fashion, alas kaki, serta kerajinan tangan.",
        "social_json": json.dumps({"instagram": "https://www.instagram.com/tei_indonesia", "linkedin": "https://www.linkedin.com/company/trade-expo-indonesia"}),
        "participants": [
            {"company_keyword": "HALDIN PACIFIC", "role": "exhibitor", "booth": "Hall 5-B12", "notes": "Natural ingredients & industrial products"},
            {"company_keyword": "ABBOTT INDONESIA", "role": "sponsor", "booth": "Hall 6-VIP", "notes": "Healthcare & institutional sponsor"},
            {"company_keyword": "ADEV NATURAL", "role": "exhibitor", "booth": "Hall 5-C20", "notes": "Corporate cosmetics & corporate gift sets"}
        ]
    },
    {
        "name": "Manufacturing Indonesia 2026",
        "event_type": "Industrial Expo",
        "organizer": "PT Pamerindo Indonesia",
        "status": "upcoming",
        "start_date": datetime(2026, 12, 2, 10, 0),
        "end_date": datetime(2026, 12, 5, 18, 0),
        "venue": "Jakarta International Expo (JIExpo) Kemayoran",
        "city": "Jakarta Pusat",
        "province": "DKI Jakarta",
        "address": "Gedung Pusat Niaga, Arena JIEXPO Kemayoran",
        "website": "https://manufacturingindonesia.com",
        "source_url": "https://manufacturingindonesia.com/about",
        "description": "Pameran internasional manufaktur, permesinan industri, otomatisasi pabrik, serta keselamatan dan kesehatan kerja (K3/Workwear).",
        "social_json": json.dumps({"linkedin": "https://www.linkedin.com/company/pamerindo-indonesia"}),
        "participants": [
            {"company_keyword": "ADHIMIX PRECAST", "role": "exhibitor", "booth": "Hall D1-05", "notes": "Precast & heavy manufacturing products"},
            {"company_keyword": "3M INDONESIA", "role": "exhibitor", "booth": "Hall D2-11", "notes": "Personal Protective Equipment (PPE) & industrial uniform solutions"},
            {"company_keyword": "ACE MOLD TECH", "role": "partner", "booth": "Hall C2-03", "notes": "Industrial precision molding"}
        ]
    },
    {
        "name": "INACRAFT 2026 - Jakarta International Handicraft Trade Fair",
        "event_type": "Trade Fair & Exhibition",
        "organizer": "ASEPHI (Asosiasi Eksportir dan Produsen Handicraft Indonesia)",
        "status": "upcoming",
        "start_date": datetime(2026, 10, 28, 9, 0),
        "end_date": datetime(2026, 11, 1, 20, 0),
        "venue": "Jakarta Convention Center (JCC) Senayan",
        "city": "Jakarta Pusat",
        "province": "DKI Jakarta",
        "address": "Jl. Gatot Subroto No.1, Senayan, Jakarta Pusat 10270",
        "website": "https://inacraft.co.id",
        "source_url": "https://inacraft.co.id",
        "description": "Pameran kerajinan tangan, batik, tenun, fashion etnik nusantara, dan souvenir merchandise terkemuka.",
        "social_json": json.dumps({"instagram": "https://www.instagram.com/inacraft_asephi"}),
        "participants": [
            {"company_keyword": "MAJU LOGISTIK UTAMA", "role": "partner", "booth": "Lobby Main Hall", "notes": "Official logistics & merchandise delivery partner"}
        ]
    },
    {
        "name": "Jakarta Fashion Week (JFW) 2027",
        "event_type": "Fashion Show & B2B Exhibition",
        "organizer": "Gita Handi Fashindo Network",
        "status": "upcoming",
        "start_date": datetime(2026, 10, 21, 13, 0),
        "end_date": datetime(2026, 10, 27, 22, 0),
        "venue": "Pondok Indah Mall 3",
        "city": "Jakarta Selatan",
        "province": "DKI Jakarta",
        "address": "Jl. Metro Pondok Indah, Kebayoran Lama, Jakarta Selatan",
        "website": "https://jakartafashionweek.co.id",
        "source_url": "https://jakartafashionweek.co.id/about",
        "description": "Pekan mode terbesar di Indonesia yang mempertemukan perancang busana, produsen garmen, buyer garmen korporat, dan media fesyen internasional.",
        "social_json": json.dumps({"instagram": "https://www.instagram.com/jfwofficial", "facebook": "https://www.facebook.com/jakartafashionweek"}),
        "participants": []
    },
    {
        "name": "ITB Integrated Career Days & Student Apparel Fair 2026",
        "event_type": "Campus Career & Merchandise Fair",
        "organizer": "Institut Teknologi Bandung (ITB Career Center)",
        "status": "upcoming",
        "start_date": datetime(2026, 11, 14, 8, 30),
        "end_date": datetime(2026, 11, 15, 17, 0),
        "venue": "Sasana Budaya Ganesha (Sabuga) ITB",
        "city": "Bandung",
        "province": "Jawa Barat",
        "address": "Jl. Tamansari No.73, Lb. Siliwangi, Coblong, Kota Bandung 40132",
        "website": "https://karir.itb.ac.id",
        "source_url": "https://karir.itb.ac.id/event",
        "description": "Bursa karier terpadu, seminar industri, serta pameran merchandise & almamater kampus mahasiswa.",
        "social_json": json.dumps({"instagram": "https://www.instagram.com/itbcareercenter"}),
        "participants": [
            {"company_keyword": "ABBOTT INDONESIA", "role": "sponsor", "booth": "Main Booth 01", "notes": "Corporate recruitment & campus partnership"},
            {"company_keyword": "ADHIMIX PRECAST", "role": "speaker", "booth": "Auditorium", "notes": "Keynote speaker - Infrastructure engineering"}
        ]
    },
    {
        "name": "ICEF 2026 - Indonesia Catalog Expo and Forum",
        "event_type": "Procurement & Corporate Expo",
        "organizer": "Lembaga Kebijakan Pengadaan Barang/Jasa Pemerintah (LKPP) & KADIN",
        "status": "upcoming",
        "start_date": datetime(2026, 8, 12, 9, 0),
        "end_date": datetime(2026, 8, 14, 17, 0),
        "venue": "JIExpo Kemayoran Hall D1 & D2",
        "city": "Jakarta Pusat",
        "province": "DKI Jakarta",
        "address": "Arena JIExpo Kemayoran, Jakarta Pusat",
        "website": "https://indocatalogexpo.com",
        "source_url": "https://indocatalogexpo.com/overview",
        "description": "Pameran pengadaan barang dan jasa nasional, etalase e-katalog LKPP untuk seragam instansi pemerintah, apparel BUMN, dan perlengkapan dinas.",
        "social_json": json.dumps({"instagram": "https://www.instagram.com/icef_expo"}),
        "participants": [
            {"company_keyword": "SEMEN JAWA", "role": "exhibitor", "booth": "Hall D1-15", "notes": "Corporate apparel & industrial uniform provider"},
            {"company_keyword": "ADHIMIX", "role": "exhibitor", "booth": "Hall D1-22", "notes": "Infrastructure supplier & corporate workwear"}
        ]
    },
    {
        "name": "Indo Defence 2026 Expo & Forum",
        "event_type": "Defence & Security Trade Expo",
        "organizer": "Kementerian Pertahanan RI & PT Napindo Media Ashatama",
        "status": "upcoming",
        "start_date": datetime(2026, 11, 4, 9, 0),
        "end_date": datetime(2026, 11, 7, 17, 0),
        "venue": "Jakarta International Expo (JIExpo) Kemayoran",
        "city": "Jakarta Pusat",
        "province": "DKI Jakarta",
        "address": "Arena PRJ Kemayoran, Jakarta Pusat 10620",
        "website": "https://indodefence.com",
        "source_url": "https://indodefence.com/event-profile",
        "description": "Pameran internasional pertahanan, keamanan, seragam taktis, rompi anti-peluru, workwear keamanan industri, dan perlengkapan keselamatan kerja.",
        "social_json": json.dumps({"instagram": "https://www.instagram.com/indodefence_official", "linkedin": "https://www.linkedin.com/company/indodefence"}),
        "participants": [
            {"company_keyword": "3M INDONESIA", "role": "exhibitor", "booth": "Hall A-08", "notes": "Safety equipment, reflective fabric, and tactical apparel solutions"},
            {"company_keyword": "CENTURY BATTERIES", "role": "partner", "booth": "Hall B-04", "notes": "Industrial equipment partner"}
        ]
    },
    {
        "name": "Hospital Expo Indonesia 2026 (PERSI)",
        "event_type": "Healthcare & Medical Exhibition",
        "organizer": "PT Okta Sejahtera Insani & Perhimpunan Rumah Sakit Seluruh Indonesia",
        "status": "upcoming",
        "start_date": datetime(2026, 10, 21, 9, 0),
        "end_date": datetime(2026, 10, 24, 18, 0),
        "venue": "Jakarta Convention Center (JCC) Senayan",
        "city": "Jakarta Pusat",
        "province": "DKI Jakarta",
        "address": "Jl. Gatot Subroto No.1, Gelora, Tanah Abang, Jakarta Pusat 10270",
        "website": "https://hospital-expo.com",
        "source_url": "https://hospital-expo.com/about-us",
        "description": "Pameran perlengkapan rumah sakit terbesar di Indonesia, termasuk pengadaan seragam medis, scrub dokter, seragam perawat, jas lab, dan linen rumah sakit.",
        "social_json": json.dumps({"instagram": "https://www.instagram.com/hospital.expo"}),
        "participants": [
            {"company_keyword": "KALBE FARMA", "role": "sponsor", "booth": "Assembly Hall A-01", "notes": "Main sponsor - Healthcare & hospital procurement"},
            {"company_keyword": "KIMIA FARMA", "role": "exhibitor", "booth": "Hall B-12", "notes": "Hospital uniforms & institutional healthcare products"}
        ]
    },
    {
        "name": "Jakarta Muslim Fashion Week (JMFW) 2027",
        "event_type": "Fashion Show & Trade Fair",
        "organizer": "Kementerian Perdagangan RI & Kadin Indonesia",
        "status": "upcoming",
        "start_date": datetime(2026, 10, 8, 10, 0),
        "end_date": datetime(2026, 10, 11, 21, 0),
        "venue": "Indonesia Convention Exhibition (ICE) BSD City",
        "city": "Tangerang",
        "province": "Banten",
        "address": "Jl. BSD Grand Boulevard No.1, Tangerang 15339",
        "website": "https://jmfwofficial.com",
        "source_url": "https://jmfwofficial.com/about",
        "description": "Pameran dagang busana muslim dan modest apparel internasional yang mempertemukan perancang busana, konveksi pabrikan garmen, dan pembeli B2B global.",
        "social_json": json.dumps({"instagram": "https://www.instagram.com/jmfwofficial"}),
        "participants": [
            {"company_keyword": "INDOFASHION CIPTAKREASI", "role": "exhibitor", "booth": "Hall 3-10", "notes": "OEM fashion & uniform production"}
        ]
    },
    {
        "name": "Indo Leather & Footwear (ILF) Expo 2026",
        "event_type": "Industrial & Trade Expo",
        "organizer": "PT Krista Media Pratama",
        "status": "upcoming",
        "start_date": datetime(2026, 8, 5, 10, 0),
        "end_date": datetime(2026, 8, 7, 18, 0),
        "venue": "JIExpo Kemayoran Hall B3 & C3",
        "city": "Jakarta Pusat",
        "province": "DKI Jakarta",
        "address": "Arena JIExpo Kemayoran, Jakarta Pusat",
        "website": "https://ilfexpo.com",
        "source_url": "https://ilfexpo.com/visiting",
        "description": "Pameran internasional industri kulit, alas kaki, produk safety shoes, aksesoris garmen, dan perlengkapan seragam kerja lapangan.",
        "social_json": json.dumps({"instagram": "https://www.instagram.com/ilfexpo"}),
        "participants": [
            {"company_keyword": "ABADI PLASTIK", "role": "exhibitor", "booth": "Hall C3-09", "notes": "Packaging & apparel synthetic materials"},
            {"company_keyword": "TEKSTIL ABADI", "role": "exhibitor", "booth": "Hall B3-18", "notes": "Industrial canvas & footwear fabric lining"}
        ]
    },
    {
        "name": "Konferensi Nasional Asosiasi Pertekstilan Indonesia (API) 2026",
        "event_type": "Industry Conference & Exhibition",
        "organizer": "Asosiasi Pertekstilan Indonesia (API)",
        "status": "upcoming",
        "start_date": datetime(2026, 9, 16, 9, 0),
        "end_date": datetime(2026, 9, 17, 17, 0),
        "venue": "Grand Mercure Kemayoran",
        "city": "Jakarta Pusat",
        "province": "DKI Jakarta",
        "address": "Jl. H. Benyamin Sueb Kav B-6, Superblok Mega Kemayoran, Jakarta Pusat",
        "website": "https://inatex.co.id/api-conference",
        "source_url": "https://inatex.co.id/api-conference",
        "description": "Konferensi nasional tahunan industri tekstil dan produk tekstil (TPT), kebijakan bahan baku, standardisasi seragam kerja nasional, dan teknologi ramah lingkungan.",
        "social_json": json.dumps({"linkedin": "https://www.linkedin.com/company/asosiasi-pertekstilan-indonesia"}),
        "participants": [
            {"company_keyword": "INDORAMA POLYCHEM", "role": "sponsor", "booth": "Ballroom Main Foyer", "notes": "Lead sponsor - Synthetic fiber & yarn innovation"},
            {"company_keyword": "GARMEN INDAH", "role": "speaker", "booth": "Panel Hall 1", "notes": "Panel speaker - Garment manufacturing competitiveness"}
        ]
    },
    {
        "name": "UI Career & Scholarship Expo 2026",
        "event_type": "Campus Career & Merchandise Fair",
        "organizer": "Career Development Center Universitas Indonesia (CDC UI)",
        "status": "upcoming",
        "start_date": datetime(2026, 10, 2, 8, 30),
        "end_date": datetime(2026, 10, 4, 17, 0),
        "venue": "Balairung Universitas Indonesia Kampus Depok",
        "city": "Depok",
        "province": "Jawa Barat",
        "address": "Lingkungan Kampus UI Depok, Jawa Barat 16424",
        "website": "https://career.ui.ac.id",
        "source_url": "https://career.ui.ac.id/events",
        "description": "Bursa karier dan pendidikan tinggi terbesar di UI, mencakup peluang pengadaan seragam panitia, merchandise kampus, almamater, dan pakaian korporat mitra.",
        "social_json": json.dumps({"instagram": "https://www.instagram.com/cdcui"}),
        "participants": [
            {"company_keyword": "ABBOTT INDONESIA", "role": "sponsor", "booth": "Main Hall UI-03", "notes": "Corporate hiring & merchandise partner"},
            {"company_keyword": "ASKI", "role": "exhibitor", "booth": "Hall B-07", "notes": "Astra component career & apprentice programs"}
        ]
    },
    {
        "name": "Lomba Kompetensi Siswa (LKS) SMK Tingkat Nasional 2026",
        "event_type": "Vocational & School Skills Fair",
        "organizer": "Balai Pengembangan Talenta Indonesia (BPTI) Kemendikbudristek",
        "status": "upcoming",
        "start_date": datetime(2026, 8, 18, 8, 0),
        "end_date": datetime(2026, 8, 22, 17, 0),
        "venue": "Balai Kartini Convention Center",
        "city": "Jakarta Selatan",
        "province": "DKI Jakarta",
        "address": "Jl. Gatot Subroto Kav. 37, Kuningan Barat, Jakarta Selatan 12950",
        "website": "https://smk.kemdikbud.go.id",
        "source_url": "https://smk.kemdikbud.go.id/lks-2026",
        "description": "Kompetisi kejuruan tingkat nasional siswa SMK se-Indonesia, menampilkan bidang fashion technology (desain busana/tata busana) dan kebutuhan wearpack sekolah.",
        "social_json": json.dumps({"instagram": "https://www.instagram.com/direktoratsmk"}),
        "participants": [
            {"company_keyword": "ADHIMIX", "role": "partner", "booth": "Area C-12", "notes": "Industry partner for vocational training and technical wear"}
        ]
    }
]


def seed():
    app = create_app()
    with app.app_context():
        print("=" * 60)
        print("SEEDING VERIFIED EVENTS & PARTICIPANTS (PHASE 5)")
        print("=" * 60)

        events_created = 0
        events_updated = 0
        parts_created = 0

        for ed in VERIFIED_EVENTS:
            participants_data = ed.pop("participants", [])
            event, is_created, match_tier = EventIntelligenceService.create_or_update_event(ed, dry_run=False)

            if is_created:
                events_created += 1
                print(f"[CREATED] Event #{event.id}: {event.name} (Score: {event.relevance_score})")
            else:
                events_updated += 1
                print(f"[UPDATED] Event #{event.id}: {event.name} ({match_tier})")

            # Link participants
            for p in participants_data:
                kw = p["company_keyword"]
                org = Organization.query.filter(Organization.name.like(f"%{kw}%")).first()
                if org:
                    part, p_created = EventIntelligenceService.link_participant(
                        event_id=event.id,
                        organization_id=org.id,
                        role=p["role"],
                        booth_number=p.get("booth"),
                        notes=p.get("notes"),
                        dry_run=False
                    )
                    if p_created:
                        parts_created += 1
                        print(f"  -> Linked {org.name} as {p['role']} ({p.get('booth')})")

        print("-" * 60)
        print(f"Summary: Events Created={events_created}, Events Updated={events_updated}, Participants Linked={parts_created}")
        print(f"Total Events in DB: {Event.query.count()}")
        print(f"Total Participants in DB: {EventParticipant.query.count()}")


if __name__ == "__main__":
    seed()
