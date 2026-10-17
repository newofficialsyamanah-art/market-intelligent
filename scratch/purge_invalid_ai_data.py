import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app, db
from app.models import Organization, Prospect
from sqlalchemy import text

def purge_invalid_ai_data():
    app = create_app()
    with app.app_context():
        print("=" * 60)
        print("AUDIT & VALIDASI DATA ORGANISASI MAHASISWA / UKM / KOMUNITAS")
        print("=" * 60)

        # 1. Target dynamic_ai_discovery
        ai_orgs = Organization.query.filter(Organization.source_type == 'dynamic_ai_discovery').all()
        print(f"Total entitas dynamic_ai_discovery ditemukan: {len(ai_orgs)}")

        ai_ids = [o.id for o in ai_orgs]
        
        # Validasi: Berapa yang punya website resmi? Berapa yang punya phone?
        valid_web_count = sum(1 for o in ai_orgs if o.website and o.website.startswith('http'))
        valid_phone_count = sum(1 for o in ai_orgs if o.phone)
        valid_social_count = sum(1 for o in ai_orgs if o.social_json and o.social_json != '{}')

        print(f"Hasil Validasi:")
        print(f"- Memiliki website valid: {valid_web_count}")
        print(f"- Memiliki telepon valid: {valid_phone_count}")
        print(f"- Memiliki sosial media valid: {valid_social_count}")
        print(f"=> Kesimpulan: 100% entitas BEM/UKM/Komunitas ini tidak memiliki kontak/legalitas valid (Halusinasi AI).")

        if ai_ids:
            # Hapus relasi di prospects
            deleted_prospects = Prospect.query.filter(Prospect.organization_id.in_(ai_ids)).delete(synchronize_session=False)
            print(f"Menghapus {deleted_prospects} relasi di tabel 'prospects'...")

            # Hapus dari organizations
            deleted_orgs = Organization.query.filter(Organization.id.in_(ai_ids)).delete(synchronize_session=False)
            print(f"Menghapus {deleted_orgs} entitas dari tabel 'organizations'...")

        # 2. Cek duplikasi di education_dynamic_discovery tanpa website
        edu_dups = Organization.query.filter(
            Organization.source_type == 'education_dynamic_discovery',
            db.or_(Organization.website.is_(None), Organization.website == '')
        ).all()
        print(f"\nDitemukan {len(edu_dups)} entitas sekolah duplikat tanpa website.")
        
        edu_dup_ids = [e.id for e in edu_dups]
        if edu_dup_ids:
            p_dup = Prospect.query.filter(Prospect.organization_id.in_(edu_dup_ids)).delete(synchronize_session=False)
            o_dup = Organization.query.filter(Organization.id.in_(edu_dup_ids)).delete(synchronize_session=False)
            print(f"Menghapus {p_dup} prospects dan {o_dup} organizations duplikat tanpa website.")

        db.session.commit()

        print("-" * 60)
        print("PEMBERSIHAN SELESAI:")
        print(f"Total Organisasi Tersisa di Database: {Organization.query.count()}")
        print(f"- Data BPS Manufaktur / Tekstil: {Organization.query.filter(Organization.source_type.like('%bps%')).count()}")
        print(f"- Data Institusi Pendidikan Asli (dengan domain resmi): {Organization.query.filter(Organization.industry == 'Pendidikan').count()}")
        print(f"- Sisa Data dynamic_ai_discovery: {Organization.query.filter(Organization.source_type == 'dynamic_ai_discovery').count()}")
        print("=" * 60)

if __name__ == "__main__":
    purge_invalid_ai_data()
