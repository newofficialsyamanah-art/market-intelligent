import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app
from app.extensions import db
from app.models import Event, EventParticipant

def purge_fake_events():
    app = create_app()
    with app.app_context():
        print("=" * 60)
        print("MEMULAI PEMBERSIHAN DATA EVENT HALUSINASI / FIKTIF")
        print("=" * 60)

        initial_total = Event.query.count()
        print(f"Total Event Sebelum Pembersihan: {initial_total}")

        # Identifikasi event palsu / buatan AI tanpa URL nyata
        fake_events = Event.query.filter(
            db.or_(
                Event.source_url == 'tavily_event_discovery',
                Event.source_url == 'ai_event_discovery',
                Event.source_url.is_(None),
                ~Event.source_url.like('http%')
            )
        ).all()
        fake_ids = [e.id for e in fake_events]
        print(f"Event fiktif yang teridentifikasi: {len(fake_ids)}")

        if not fake_ids:
            print("Tidak ada event fiktif. Database sudah bersih!")
            return

        # Hapus relasi partisipan jika ada
        deleted_parts = 0
        if fake_ids:
            # Batching to avoid SQL in-clause limits
            chunk_size = 500
            for i in range(0, len(fake_ids), chunk_size):
                chunk = fake_ids[i:i + chunk_size]
                deleted_parts += EventParticipant.query.filter(EventParticipant.event_id.in_(chunk)).delete(synchronize_session=False)
                Event.query.filter(Event.id.in_(chunk)).delete(synchronize_session=False)
                db.session.commit()

        final_total = Event.query.count()
        print(f"Relasi partisipan dibersihkan: {deleted_parts}")
        print(f"Total Event Fiktif Berhasil Dihapus: {len(fake_ids)}")
        print(f"Sisa Event Nyata & Terverifikasi: {final_total}")
        print("=" * 60)

if __name__ == "__main__":
    purge_fake_events()
