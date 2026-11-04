import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app import create_app
from app.models import Event

app = create_app()
with app.app_context():
    total = Event.query.count()
    tavily_count = Event.query.filter(Event.source_url == 'tavily_event_discovery').count()
    http_count = Event.query.filter(Event.source_url.like('http%')).count()
    null_count = Event.query.filter(Event.source_url.is_(None)).count()
    other_count = total - tavily_count - http_count - null_count

    print(f"Total Events: {total}")
    print(f" - With real URL (http%): {http_count}")
    print(f" - Pure AI generated ('tavily_event_discovery'): {tavily_count}")
    print(f" - Null source_url: {null_count}")
    print(f" - Other source_url: {other_count}")

    # Inspect other source_urls
    if other_count > 0:
        others = Event.query.filter(~Event.source_url.like('http%'), Event.source_url != 'tavily_event_discovery', Event.source_url.isnot(None)).limit(10).all()
        print("\nSample other sources:")
        for o in others:
            print(f"   {o.source_url}")

