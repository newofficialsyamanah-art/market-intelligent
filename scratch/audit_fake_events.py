import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app import create_app, db
from app.models import Event, EventParticipant

app = create_app()
with app.app_context():
    total_ev = Event.query.count()
    fake_ev = Event.query.filter(
        db.or_(
            Event.source_url == 'tavily_event_discovery',
            Event.source_url == 'ai_event_discovery',
            Event.source_url.is_(None)
        )
    ).all()
    fake_ids = [e.id for e in fake_ev]
    
    total_parts = EventParticipant.query.count()
    fake_parts = EventParticipant.query.filter(EventParticipant.event_id.in_(fake_ids)).count() if fake_ids else 0
    
    print(f"Total Events: {total_ev}")
    print(f"Fake Events to Purge: {len(fake_ev)}")
    print(f"Real Events to Keep: {total_ev - len(fake_ev)}")
    print(f"Total Event Participants: {total_parts}")
    print(f"Participants linked to Fake Events: {fake_parts}")
