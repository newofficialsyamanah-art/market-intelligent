import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app import create_app, db
from sqlalchemy import text

app = create_app()
with app.app_context():
    ai_ids = [r[0] for r in db.session.execute(text("SELECT id FROM organizations WHERE source_type = 'dynamic_ai_discovery'")).fetchall()]
    print('Total AI orgs:', len(ai_ids))
    if ai_ids:
        id_list = ','.join(str(i) for i in ai_ids)
        for tbl, col in [('prospects', 'organization_id'), ('campaign_targets', 'organization_id'), 
                         ('events', 'organizer_id'), ('event_participants', 'organization_id'), 
                         ('duplicate_candidates', 'organization_id')]:
            query = f'SELECT COUNT(*) FROM {tbl} WHERE {col} IN ({id_list})'
            cnt = db.session.execute(text(query)).scalar()
            print(f'{tbl}.{col} count: {cnt}')
