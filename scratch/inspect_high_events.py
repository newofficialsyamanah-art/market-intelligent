import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app, db
from app.models import Event

app = create_app()
with app.app_context():
    high_events = Event.query.filter(Event.relevance_score >= 80).all()
    print(f"Total high relevance events: {len(high_events)}")
    has_web_or_src = [e for e in high_events if e.clean_website or e.instagram_url or e.clean_source_url]
    print(f"With info: {len(has_web_or_src)}, Without info: {len(high_events) - len(has_web_or_src)}")

    print("\nEvents WITHOUT info in top score (Sample 30):")
    for e in [ev for ev in high_events if not (ev.clean_website or ev.instagram_url or ev.clean_source_url)][:30]:
        city = e.city or '-'
        print(f"{e.id} | {e.name[:45]:<45} | Score: {e.relevance_score} | City: {city}")
