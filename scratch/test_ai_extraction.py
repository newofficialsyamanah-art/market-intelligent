import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import json
from app import create_app
from app.ai_agent import _chat_json
from scratch.test_google_event_fetcher import fetch_google_news_events

app = create_app()
with app.app_context():
    snippets = fetch_google_news_events(query="pameran expo", location="Surabaya", year="2027", limit=5)
    print("Snippets passed to AI:", len(snippets))
    
    prompt = f"""Kamu adalah AI Event Intelligence spesialis penemuan event B2B di Indonesia.
Ekstrak HANYA event/pameran/expo/turnamen yang secara nyata tertulis pada berita berikut.

ATURAN KETAT:
1. DILARANG MENGARANG EVENT! Jika suatu berita hanya tentang penutupan event lama atau bukan tentang event mendatang 2026/2027, JANGAN masukkan.
2. Setiap event yang diekstrak WAJIB memiliki "source_url" yang sama persis dengan URL berita asalnya.
3. Cantumkan tahun 2026 atau 2027 sesuai yang tertulis di teks.

DATA BERITA GOOGLE:
{json.dumps([{'title': s['title'], 'url': s['url'], 'publisher': s['source_publisher'], 'content': s['content']} for s in snippets], ensure_ascii=False, indent=2)}

Kembalikan format HANYA JSON array:
[
  {{
    "name": "Nama Resmi Event (contoh: IndoBuildTech 2027, Indonesia Energy Week 2027)",
    "event_type": "Exhibition / Trade Fair / Sports Tournament / Conference",
    "venue": "Nama Gedung / Tempat jika disebutkan (atau '-' jika tidak)",
    "city": "Kota",
    "province": "Provinsi jika diketahui",
    "organizer": "Nama Penyelenggara / Dinas / Institusi",
    "website": "URL website resmi jika ada, atau kosongkan",
    "source_url": "URL berita asal dari Google",
    "description": "Ringkasan informasi event dan potensi apparel/merchandise",
    "status": "upcoming"
  }}
]
"""
    extracted = _chat_json(
        system_prompt="Kamu adalah AI Event Intelligence Indonesia yang hanya mengekstrak data event faktual dari sumber terpercaya tanpa halusinasi.",
        user_prompt=prompt,
        temperature=0.1
    )
    print("\nEXTRACTED EVENTS FROM REAL GOOGLE NEWS:")
    print(json.dumps(extracted, indent=2))
