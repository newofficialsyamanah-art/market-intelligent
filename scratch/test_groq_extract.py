import sys, os
sys.path.insert(0, os.path.abspath('.'))

from app import create_app
from app.services.event_intelligence import fetch_google_news_events
from app.ai_agent import _chat_json
import json

app = create_app()
with app.app_context():
    snippets = fetch_google_news_events(query="teknologi", location="Jakarta", year="2027", limit=10)
    chunk = snippets[:10]
    prompt = f"""Kamu adalah AI Event Intelligence spesialis penemuan event B2B, expo, dan turnamen olahraga di Indonesia.
Berdasarkan data berita & pencarian web Google berikut, ekstrak HANYA daftar event/pameran/expo/turnamen nyata di Indonesia:

DATA BERITA GOOGLE:
{json.dumps([{'title': s.get('title'), 'url': s.get('url'), 'content': (s.get('content') or '')[:450]} for s in chunk], ensure_ascii=False)}

Kriteria:
- Target lokasi: Jakarta
- Kategori / Topik: teknologi
- Target Tahun: 2027

ATURAN KETAT:
1. DILARANG MENGARANG EVENT! Jika suatu berita hanya tentang penutupan event lama atau bukan tentang event mendatang 2026/2027, jangan masukkan.
2. Setiap event yang diekstrak WAJIB memiliki "source_url" yang sama persis dengan URL berita asalnya.
3. Cantumkan tahun 2026 atau 2027 sesuai yang tertulis di teks.

Kembalikan format HANYA JSON array:
[
  {{
    "name": "Nama Resmi Event (contoh: IndoBuildTech 2027, Jatim Fair 2026)",
    "event_type": "Exhibition / Trade Fair / Conference / Sports Tournament / Career Fair",
    "venue": "Nama Gedung / Tempat jika ada",
    "city": "Kota",
    "province": "Provinsi",
    "organizer": "Nama Penyelenggara / EO / Institusi",
    "start_date": "Estimasi tanggal (YYYY-MM-DD atau Bulan Tahun jika ada)",
    "end_date": "Estimasi tanggal selesai jika ada",
    "website": "URL website resmi jika ada",
    "source_url": "URL berita asal dari Google",
    "description": "Deskripsi singkat profil event dan potensi kebutuhan seragam/apparel/merchandise",
    "status": "upcoming"
  }}
]
"""
    raw_data = _chat_json(
        system_prompt="Kamu adalah AI Event Intelligence yang HANYA mengekstrak event faktual dari data berita Google tanpa halusinasi.",
        user_prompt=prompt,
        temperature=0.1
    )
    print("Raw LLM response:")
    print(json.dumps(raw_data, indent=2, ensure_ascii=False))

