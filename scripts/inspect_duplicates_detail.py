import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import create_app, db
from app.models import RawData, Organization, Prospect, DuplicateCandidate, EventParticipant
from sqlalchemy import text

app = create_app()
with app.app_context():
    print("=== RawData Records ===")
    raws = RawData.query.all()
    for r in raws:
        print(f"ID={r.id}, source_id={r.source_id}, original_name={r.original_name}, status={r.status}, created={r.created_at}")

    print("\n=== 4 Duplicate Organizations ===")
    names = ['unimed futsal squad', 'usu futsal team', 'politeknik negeri medan futsal', 'medan futsal club']
    for n in names:
        print(f"\nOrg Duplikat: {n}")
        orgs = Organization.query.filter_by(normalized_name=n).all()
        for o in orgs:
            # Cek apakah direferensikan di prospects, event_participants, duplicate_candidates
            p_cnt = Prospect.query.filter_by(organization_id=o.id).count()
            ep_cnt = EventParticipant.query.filter_by(organization_id=o.id).count()
            dc_cnt = DuplicateCandidate.query.filter_by(organization_id=o.id).count()
            print(f"  ID={o.id}, name='{o.name}', source_type='{o.source_type}', created={o.created_at} | refs: prospects={p_cnt}, participants={ep_cnt}, dup_cands={dc_cnt}")

    print("\n=== Foreign Key Check on Prospects ===")
    # Check if any table references prospects table
    inspector = db.inspect(db.engine)
    for table_name in inspector.get_table_names():
        fks = inspector.get_foreign_keys(table_name)
        for fk in fks:
            if fk.get('referred_table') == 'prospects':
                print(f"Table '{table_name}' has FK to prospects: {fk}")

    print("\n=== Prospect Duplicate Distribution by RawData ===")
    res = db.session.execute(text("""
        SELECT raw_data_id, COUNT(*) 
        FROM prospects 
        GROUP BY raw_data_id
    """)).fetchall()
    for row in res:
        print(f"  raw_data_id={row[0]}: {row[1]} prospects")
