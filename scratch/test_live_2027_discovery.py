import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app, db
from app.models import Event
from app.services.event_intelligence import EventIntelligenceService

app = create_app()
with app.app_context():
    print("=== TESTING REAL EVENT DISCOVERY TAHUN 2027 VIA GOOGLE ===")
    
    # Run discovery for 2027
    res = EventIntelligenceService.discover_events(
        query="pameran industri expo",
        city="Surabaya",
        province="Jawa Timur",
        year="2027",
        limit=5
    )
    
    print("\nDiscovery Result:")
    print(f"Total Processed: {res.get('total_processed')}")
    print(f"Created (New): {res.get('created')}")
    print(f"Updated: {res.get('updated')}")
    print(f"Message: {res.get('message', 'Sukses')}")
    
    for it in res.get("items", []):
        print(f" - [{it['id']}] {it['name']} (Baru: {it['is_new']}, Rel: {it['relevance_score']})")

    # Inspect events in DB
    ev2027 = Event.query.filter(Event.name.like("%2027%")).all()
    print(f"\nTotal Events 2027 in DB: {len(ev2027)}")
    for e in ev2027:
        print(f"  * {e.name} | Year: {e.event_year} | Source: {e.source_url[:60]}")
