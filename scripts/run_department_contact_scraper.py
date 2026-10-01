"""CLI Runner for Department Contact Scraping Pipeline.

Eksekusi scraping nomor Purchasing, Procurement, HR, Panitia Event, dan Narahubung Komunitas.
Usage:
    python scripts/run_department_contact_scraper.py [--limit 100] [--types Perusahaan,community] [--force]
"""

import os
import sys
import argparse
import time
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app, db
from app.models import Organization, Event, Prospect
from app.services.department_contact_scraper import run_full_department_scraping_batch, DepartmentContactScraperService

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

def main():
    parser = argparse.ArgumentParser(description="Scrape nomor purchasing, procurement, dan HR untuk perusahaan, event, dan komunitas.")
    parser.add_argument("--limit", type=int, default=None, help="Batas jumlah organisasi yang diproses (default: semua)")
    parser.add_argument("--types", type=str, default=None, help="Daftar tipe organisasi dipisahkan koma (contoh: Perusahaan,community,student_organization)")
    parser.add_argument("--force", action="store_true", help="Paksa pengayaan ulang meskipun sudah memiliki kontak departemen")
    args = parser.parse_args()

    app = create_app()

    print("================================================================================")
    print("[*] MEMULAI SCRAPING KONTAK DEPARTEMEN: PURCHASING, PROCUREMENT, HR, EVENT, KOMUNITAS")
    print("================================================================================")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Limit Orgs: {args.limit or 'SEMUA'}")
    print(f"Filter Tipe: {args.types or 'SEMUA'}")
    print(f"Force Mode: {args.force}")
    print("--------------------------------------------------------------------------------\n")

    org_types = [t.strip() for t in args.types.split(",")] if args.types else None

    with app.app_context():
        res = run_full_department_scraping_batch(limit_orgs=args.limit, org_types=org_types, sync_prospects=True, force=args.force)

        print("\n================================================================================")
        print("[OK] HASIL EKSEKUSI PIPELINE SCRAPING KONTAK SPESIFIK DEPARTEMEN")
        print("================================================================================")
        print(f"[*] Waktu Eksekusi              : {res['elapsed_seconds']} detik")
        print(f"[*] Event Diproses / Diperkaya : {res['events_processed']} / {res['events_enriched']}")
        print(f"[*] Organisasi Diproses        : {res['orgs_processed']}")
        print(f"[*] Organisasi Berhasil Kontak  : {res['orgs_enriched']}")
        print(f"[+] Kontak Purchasing Ditemukan : {res['purchasing_contacts_found']}")
        print(f"[+] Kontak Procurement Ditemukan: {res['procurement_contacts_found']}")
        print(f"[+] Kontak HR / HRD Ditemukan   : {res['hr_contacts_found']}")
        print(f"[+] Kontak Panitia Event        : {res['panitia_event_found']}")
        print(f"[+] Narahubung Komunitas        : {res['community_pic_found']}")
        print(f"[*] Total Prospects Tersinkron  : {res['prospects_synced']}")
        print("================================================================================\n")

        # Tampilkan beberapa sampel data hasil pengayaan
        sample_orgs = Organization.query.filter(Organization.department_contacts_json.isnot(None)).limit(5).all()
        print("[*] CONTOH HASIL KONTAK DEPARTEMEN PERUSAHAAN:")
        for o in sample_orgs:
            contacts = o.get_department_contacts()
            print(f"\n[CORP] {o.name} ({o.organization_type}) - Wilayah: {o.city or '-'}, {o.province or '-'}")
            for dept, c in contacts.items():
                wa_badge = " [WhatsApp OK]" if c.get("is_whatsapp") else " [PSTN/Telepon Kantor]"
                print(f"   * {dept.upper():14}: {c.get('phone', '-')} {wa_badge} | {c.get('name', '-')} | {c.get('email', '-')}")

        sample_events = Event.query.filter(Event.department_contacts_json.isnot(None)).limit(3).all()
        print("\n[*] CONTOH HASIL KONTAK PANITIA / SPONSORSHIP EVENT:")
        for ev in sample_events:
            contacts = ev.get_department_contacts()
            print(f"\n[EVENT] {ev.name} (Penyelenggara: {ev.organizer})")
            for dept, c in contacts.items():
                wa_badge = " [WhatsApp OK]" if c.get("is_whatsapp") else " [PSTN]"
                print(f"   * {dept.upper():14}: {c.get('phone', '-')} {wa_badge} | {c.get('name', '-')} | {c.get('email', '-')}")

if __name__ == "__main__":
    main()
