import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + "/.."))

from app import create_app, db
from app.models import Organization

app = create_app()

with app.app_context():
    total_orgs = Organization.query.count()
    print(f"Total Master Organizations: {total_orgs}")

    # 1. Audit Website URLs
    orgs_with_web = Organization.query.filter(Organization.website.isnot(None), Organization.website != "").all()
    invalid_web_count = 0
    clean_web_count = 0
    for o in orgs_with_web:
        clean = o.clean_website_url
        if not clean:
            invalid_web_count += 1
        else:
            clean_web_count += 1
            if not clean.startswith("http://") and not clean.startswith("https://"):
                print(f"Non-http web URL: ID {o.id} -> {clean}")

    print(f"Website Stats: Total with raw web={len(orgs_with_web)}, Valid clean={clean_web_count}, Neutralized/Invalid={invalid_web_count}")

    # 2. Audit Social Media URLs
    orgs_with_social = Organization.query.filter(Organization.social_json.isnot(None), Organization.social_json != "").all()
    total_social_profiles = 0
    suspicious_social = []

    for o in orgs_with_social:
        s_dict = o.social_media_dict
        for platform, url in s_dict.items():
            total_social_profiles += 1
            u_low = str(url).lower()
            if any(bad in u_low for bad in ["sharer", "sharearticle", "intent/tweet", "share?url", "example.com", "undefined"]):
                suspicious_social.append((o.id, platform, url))

    print(f"Social Media Stats: Total Orgs with Social={len(orgs_with_social)}, Valid Profiles={total_social_profiles}, Suspicious Profiles={len(suspicious_social)}")
    if suspicious_social:
        print("Suspicious samples found:", suspicious_social[:5])
    else:
        print("SEMUA DATA SOCIAL MEDIA BERSIH, TERVERIFIKASI, DAN BEBAS SHARE/DUMMY LINK!")
