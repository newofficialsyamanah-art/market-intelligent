import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + "/.."))
import json
from app import create_app, db

from app.models import Organization

app = create_app()
with app.app_context():
    total_social = Organization.query.filter(Organization.social_json.isnot(None)).filter(Organization.social_json != '{}').count()
    print(f"Total Master Org with social_json: {total_social}")
    
    samples = Organization.query.filter(Organization.social_json.isnot(None)).filter(Organization.social_json != '{}').limit(10).all()
    for o in samples:
        print(f"ID: {o.id} | Name: {o.name}")
        print(f"  Clean Web: {o.clean_website_url}")
        print(f"  Raw Social: {o.social_json}")
        print(f"  Parsed Dict: {o.social_media_dict}")
        print(f"  IG: {o.instagram_url} | FB: {o.facebook_url} | LI: {o.linkedin_url}")
        print("-" * 50)
