"""Menjalankan Discovery Event 2027 menggunakan Fitur Bawaan Aplikasi:
EventIntelligenceService.discover_events()

Fungsi ini secara otomatis:
1. Mencari berita & artikel resmi melalui Google News RSS & Google CSE
2. Membaca cuplikan informasi asli
3. Mengekstrak data event (Nama, Tanggal Presisi, Venue, Penyelenggara, Source URL) via Groq AI
4. Melakukan deduplikasi multi-tier dan menyimpan langsung ke database PostgreSQL
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app
from app.services.event_intelligence import EventIntelligenceService

def run_app_discovery():
    app = create_app()
    with app.app_context():
        print("=== MENJALANKAN DISCOVERY EVENT 2027 VIA FITUR BAWAAN APLIKASI ===")
        
        # Kategori 1: Pameran, Expo B2B, dan Summit 2027
        print("\n[1/2] Mencari pameran dagang, expo B2B, dan konferensi 2027...")
        res_expo = EventIntelligenceService.discover_events(
            query="pameran expo konferensi",
            year="2027",
            limit=15
        )
        print(f"Hasil Expo: Total diproses: {res_expo.get('total_processed', 0)}, Baru: {res_expo.get('created', 0)}, Update: {res_expo.get('updated', 0)}")
        if res_expo.get("message"):
            print(f"Pesan: {res_expo['message']}")

        # Kategori 2: Kejuaraan & Turnamen Olahraga / Marathon 2027
        print("\n[2/2] Mencari kejuaraan olahraga & festival lari marathon 2027...")
        res_sport = EventIntelligenceService.discover_events(
            query="kejuaraan turnamen lari marathon",
            year="2027",
            limit=15
        )
        print(f"Hasil Olahraga: Total diproses: {res_sport.get('total_processed', 0)}, Baru: {res_sport.get('created', 0)}, Update: {res_sport.get('updated', 0)}")
        if res_sport.get("message"):
            print(f"Pesan: {res_sport['message']}")

        print("\n=== PROSES DISCOVERY EVENT SELESAI ===")

if __name__ == "__main__":
    run_app_discovery()

