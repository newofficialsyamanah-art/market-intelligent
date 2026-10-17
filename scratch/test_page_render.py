import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + "/.."))

from app import create_app, db
from app.models import User, Organization

app = create_app()

with app.app_context():
    # Temukan user untuk login
    user = User.query.filter_by(role="business_analyst").first()
    if not user:
        user = User.query.first()
    print(f"Testing with user: {user.email if user else 'None'} (Role: {user.role if user else 'None'})")


    client = app.test_client()
    with client.session_transaction() as sess:
        if user:
            sess['_user_id'] = str(user.id)
            sess['_fresh'] = True

    # 1. Test explorer
    resp_explorer = client.get('/market-analysis/explorer')
    print(f"Explorer Status: {resp_explorer.status_code}")
    assert resp_explorer.status_code == 200, f"Explorer failed with status {resp_explorer.status_code}"

    # 2. Test marketing targets
    resp_targets = client.get('/marketing/targets')
    print(f"Marketing Targets Status: {resp_targets.status_code}")
    assert resp_targets.status_code == 200, f"Targets failed with status {resp_targets.status_code}"

    # 3. Test marketing segments
    resp_segments = client.get('/marketing/segments?preset=corporate_uniform')
    print(f"Marketing Segments Status: {resp_segments.status_code}")
    assert resp_segments.status_code == 200, f"Segments failed with status {resp_segments.status_code}"


    # 4. Test org detail for several organizations
    sample_orgs = Organization.query.filter(Organization.social_json.isnot(None)).filter(Organization.social_json != '{}').limit(3).all()
    no_social_org = Organization.query.filter(Organization.social_json.is_(None)).first()
    if no_social_org:
        sample_orgs.append(no_social_org)

    for org in sample_orgs:
        resp_detail = client.get(f'/market-analysis/organization/{org.id}')
        print(f"Org #{org.id} ({org.name[:25]}...): Status {resp_detail.status_code}")
        assert resp_detail.status_code == 200, f"Org detail #{org.id} failed with status {resp_detail.status_code}"
        
        html = resp_detail.get_data(as_text=True)
        if org.clean_website_url:
            assert org.clean_website_url in html, f"Clean website URL missing from HTML for org {org.id}"
            print(f"  Verified clean website URL rendered: {org.clean_website_url}")
        else:
            assert "Belum terdata" in html, f"'Belum terdata' badge expected for org {org.id}"
            print(f"  Verified 'Belum terdata' rendered for missing website/social")

    print("\nALL PAGE RENDERING & VALIDATION TESTS PASSED SUCCESSFULLY!")

