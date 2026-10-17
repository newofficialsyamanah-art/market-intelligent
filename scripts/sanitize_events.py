"""Sanitize and Validate Event Intelligence Data (events table).

1. Menyesuaikan status event: event bertahun <= 2025 diubah dari 'upcoming' menjadi 'completed'.
2. Sanitasi kolom website:
   - Pindahkan link video YouTube ke source_url dan kosongkan website.
   - Pindahkan artikel berita portal (Kompas, Detik, Tribun, dll.) ke source_url dan kosongkan website.
   - Pindahkan link Instagram post/reel ke source_url dan kosongkan website.
   - Pindahkan Instagram profile ke social_json dan kosongkan website.
   - Purge nilai sampah seperti 'TBD', 'N/A', dll.
3. Menghubungkan organizer ke master Organization jika nama cocok.
"""

import os
import sys
import re
import json
from urllib.parse import urlparse

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app, db
from app.models import Event, Organization, EventParticipant

NEWS_PORTAL_DOMAINS = [
    'tribunnews.com', 'detik.com', 'kompas.com', 'merdeka.com', 'okezone.com', 'suara.com', 
    'inews.id', 'autonetmagz.com', 'prokaltim.com', 'batampena.com', 'baritopost.co.id',
    'realitapapua.com', 'jubi.id', 'kaltimfaktual.co', 'espos.id', 'focuskini.id',
    'ogindonesia.com', 'mediaasuransinews.co.id', 'analisadaily.com', 'dandapala.com',
    'min.co.id', 'teraspapua.com', 'bicarasurabaya.com', 'smartfm.sonora.id', 'sudutpandang.id',
    'antaranews.com', 'tempo.co', 'bisnis.com', 'kontan.co.id', 'kumparan.com', 'liputan6.com',
    'nusantaraabadinews.com', 'sindomakassar.com', 'adv.kompas.id'
]

def sanitize():
    app = create_app()
    with app.app_context():
        print("=" * 60)
        print("MEMULAI SANITASI & VALIDASI DATA EVENT")
        print("=" * 60)

        events = Event.query.all()
        print(f"Total Event di Database: {len(events)}")

        status_updated = 0
        junk_web_purged = 0
        web_to_source_count = 0
        ig_profile_moved = 0
        organizers_linked = 0

        # Pre-load organizations for organizer matching
        orgs = Organization.query.all()
        org_lookup = {o.name.lower(): o for o in orgs}

        for ev in events:
            # 1. Koreksi Status Event
            # Jika ada tahun 2024 atau 2025 di nama, atau end_date < 2026, set status = 'completed'
            year_match = re.search(r'\b(201\d|202[0-5])\b', ev.name)
            is_past_date = ev.end_date and ev.end_date.year < 2026
            if (year_match or is_past_date) and ev.status == 'upcoming':
                ev.status = 'completed'
                status_updated += 1

            # 2. Sanitasi Kolom Website
            if ev.website:
                raw_w = ev.website.strip()
                
                # Check junk
                if raw_w.upper() in ['TBD', 'N/A', 'NONE', '-', ''] or len(raw_w) < 4:
                    ev.website = None
                    junk_web_purged += 1
                    continue

                try:
                    parsed = urlparse(raw_w)
                    dom = parsed.netloc.lower()
                except Exception:
                    ev.website = None
                    junk_web_purged += 1
                    continue

                # Cek apakah artikel berita / media
                is_news = any(nd in dom for nd in NEWS_PORTAL_DOMAINS)
                is_video = any(vd in dom for vd in ['youtube.com', 'youtu.be', 'facebook.com'])
                is_ig = 'instagram.com' in dom

                if is_news or is_video:
                    if not ev.source_url or ev.source_url == 'tavily_event_discovery':
                        ev.source_url = raw_w
                    ev.website = None
                    web_to_source_count += 1
                elif is_ig:
                    if '/reel/' in raw_w or '/p/' in raw_w:
                        if not ev.source_url or ev.source_url == 'tavily_event_discovery':
                            ev.source_url = raw_w
                        ev.website = None
                        web_to_source_count += 1
                    else:
                        # Ini adalah profile IG! Pindahkan ke social_json
                        clean_ig = raw_w.split('?')[0].rstrip('/')
                        current_social = {}
                        if ev.social_json:
                            try:
                                current_social = json.loads(ev.social_json)
                                if not isinstance(current_social, dict):
                                    current_social = {}
                            except Exception:
                                current_social = {}
                        current_social['instagram'] = clean_ig
                        ev.social_json = json.dumps(current_social)
                        ev.website = None
                        ig_profile_moved += 1

            # 3. Link Organizer ke Master Organization jika cocok
            if not ev.organizer_id and ev.organizer:
                norm_org = ev.organizer.lower().strip()
                matched_org = None
                for name_key, org in org_lookup.items():
                    if len(norm_org) > 5 and (norm_org == name_key or norm_org in name_key):
                        matched_org = org
                        break
                if matched_org:
                    ev.organizer_id = matched_org.id
                    organizers_linked += 1

        db.session.commit()

        print("-" * 60)
        print("HASIL SANITASI EVENT:")
        print(f"1. Status dikoreksi ke 'completed': {status_updated} event")
        print(f"2. Website junk dibersihkan: {junk_web_purged}")
        print(f"3. URL berita / YouTube / IG Reels dialihkan ke source_url: {web_to_source_count}")
        print(f"4. Akun IG dipindahkan ke social_json: {ig_profile_moved}")
        print(f"5. Penyelenggara dihubungkan ke Organization ID: {organizers_linked}")
        print("-" * 60)
        
        # Cek kondisi akhir
        valid_webs = Event.query.filter(Event.website.isnot(None), Event.website != '').count()
        completed_evs = Event.query.filter(Event.status == 'completed').count()
        upcoming_evs = Event.query.filter(Event.status == 'upcoming').count()
        social_evs = Event.query.filter(Event.social_json.isnot(None), Event.social_json != '').count()
        linked_org_evs = Event.query.filter(Event.organizer_id.isnot(None)).count()
        
        print(f"Kondisi Akhir Database:")
        print(f"- Total Event: {Event.query.count()}")
        print(f"- Status Upcoming: {upcoming_evs}")
        print(f"- Status Completed/Past: {completed_evs}")
        print(f"- Website Resmi Valid: {valid_webs}")
        print(f"- Memiliki Akun Sosial Media Terdata: {social_evs}")
        print(f"- Terhubung ke Master Organization: {linked_org_evs}")
        print(f"- Total Relasi Partisipan (Exhibitor/Sponsor): {EventParticipant.query.count()}")

if __name__ == "__main__":
    sanitize()
