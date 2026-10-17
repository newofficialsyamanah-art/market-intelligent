import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app, db
from app.models import Event
from app.services.event_intelligence import normalize_event_name
from collections import defaultdict

app = create_app()
with app.app_context():
    events = Event.query.all()
    grouped = defaultdict(list)
    for e in events:
        norm = normalize_event_name(e.name)
        grouped[norm].append(e)

    dups = {k: v for k, v in grouped.items() if len(v) > 1 and k != ''}
    print(f"Total normalized name groups with duplicates: {len(dups)}")
    for k, v in list(dups.items())[:15]:
        print(f"\nGroup '{k}': {len(v)} events")
        for e in v:
            print(f"  ID {e.id}: {e.name} | Web: {e.clean_website} | IG: {e.instagram_url} | Src: {e.clean_source_url}")
