import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app, db
from app.models import User, Event

app = create_app()
app.config['WTF_CSRF_ENABLED'] = False

with app.app_context():
    # 1. DB Integrity Check
    total_events = Event.query.count()
    fake_events = Event.query.filter(
        db.or_(
            Event.source_url == 'tavily_event_discovery',
            Event.source_url == 'ai_event_discovery',
            Event.source_url.is_(None),
            ~Event.source_url.like('http%')
        )
    ).count()
    print("1. DATABASE INTEGRITY CHECK:")
    print(f"   Total Events: {total_events}")
    print(f"   Fake/Invalid Events: {fake_events}")
    assert fake_events == 0, f"Found {fake_events} fake events still in DB!"
    print("   -> PASSED: All events in DB have verified http/https sources.")

    # 2. Test Client Web Routes
    user = User.query.filter_by(role="marketing").first() or User.query.first()
    client = app.test_client()
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user.id)
        sess['_fresh'] = True

    print("\n2. WEB ROUTE TESTS:")
    # Index
    r1 = client.get('/events/')
    print(f"   GET /events/: {r1.status_code}")
    assert r1.status_code == 200
    html1 = r1.get_data(as_text=True)
    assert "Tahun 2027" in html1, "Year 2027 option missing from index.html"
    assert "modalDiscoverEvents" in html1, "modalDiscoverEvents missing"

    # Year 2027 Filter
    r2 = client.get('/events/?year=2027')
    print(f"   GET /events/?year=2027: {r2.status_code}")
    assert r2.status_code == 200

    # Year 2026 Filter
    r3 = client.get('/events/?year=2026')
    print(f"   GET /events/?year=2026: {r3.status_code}")
    assert r3.status_code == 200

    # Calendar
    r4 = client.get('/events/calendar')
    print(f"   GET /events/calendar: {r4.status_code}")
    assert r4.status_code == 200

    # Calendar API
    r5 = client.get('/events/api/calendar')
    print(f"   GET /events/api/calendar: {r5.status_code}")
    assert r5.status_code == 200
    cal_data = r5.get_json()
    print(f"   Calendar API events returned: {len(cal_data)}")

    # Marketing Targets
    r6 = client.get('/marketing/targets')
    print(f"   GET /marketing/targets: {r6.status_code}")
    assert r6.status_code == 200
    print("   -> PASSED: All web routes render cleanly without error.")

    # 3. Live Google Discovery Test for 2027
    print("\n3. LIVE GOOGLE DISCOVERY TEST (Tahun 2027):")
    r7 = client.post('/events/discover', data={
        "query": "pameran maritim logistik",
        "city": "Jakarta",
        "province": "DKI Jakarta",
        "year": "2027",
        "limit": 3
    }, follow_redirects=True)
    print(f"   POST /events/discover Status: {r7.status_code}")
    assert r7.status_code == 200
    html7 = r7.get_data(as_text=True)
    assert "Discovery Event" in html7 or "selesai" in html7 or "faktual" in html7 or "alert" in html7
    print("   -> PASSED: Live discovery executed cleanly!")

    print("\n=== ALL SYSTEM TESTS COMPLETED SUCCESSFULLY ===")

