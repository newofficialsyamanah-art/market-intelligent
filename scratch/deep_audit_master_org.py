import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + "/.."))

from app import create_app, db
from app.models import Organization
import json

app = create_app()

with app.app_context():
    total = Organization.query.count()
    print(f"Total Organizations in DB: {total}")

    # 1. Organizations whose name is a URL
    url_names = Organization.query.filter(Organization.name.like('http%')).all()
    print(f"1. URL as Organization Name: {len(url_names)}")
    for o in url_names[:5]:
        print(f"   ID {o.id}: {o.name} (Source: {o.source_type})")

    # 2. Dynamic AI Discovery orgs
    ai_discovery = Organization.query.filter_by(source_type='dynamic_ai_discovery').all()
    print(f"2. Dynamic AI Discovery Orgs: {len(ai_discovery)}")

    # 3. Social JSON with generic/junk patterns
    junk_social_patterns = [
        "/popular", "/explore", "facebook.com/", "facebook.com/sharer", 
        "linkedin.com/feed", "linkedin.com/share", "twitter.com/share",
        "help.instagram.com", "instagram.com/accounts", "\ufffd", "propertygenie"
    ]
    
    junk_social_orgs = []
    orgs_with_social = Organization.query.filter(Organization.social_json.isnot(None), Organization.social_json != '{}', Organization.social_json != '').all()
    for o in orgs_with_social:
        raw = o.social_json
        for pat in junk_social_patterns:
            if pat in raw.lower() or raw.strip() in ['{"facebook": "https://www.facebook.com/"}', '{"facebook": "http://www.facebook.com/"}']:
                junk_social_orgs.append((o.id, o.name, raw))
                break

    print(f"3. Orgs with Junk/Generic Social Media: {len(junk_social_orgs)}")
    for item in junk_social_orgs[:10]:
        print(f"   ID {item[0]} | {item[1]} | Social: {item[2]}")

    # 4. Check Pan Brothers & Salt n Pepper context
    pb = Organization.query.filter(Organization.name.ilike('%pan brothers%')).first()
    if pb:
        print(f"4. Pan Brothers in DB: ID {pb.id} | Name: {pb.name} | Web: {pb.clean_website_url} | Social: {pb.social_json}")
    else:
        print("4. Pan Brothers not in Master DB (only in benchmark)")
