import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + "/.."))

from app import create_app, db
from app.models import Organization
from collections import Counter
import json
from urllib.parse import urlparse

app = create_app()

with app.app_context():
    orgs = Organization.query.filter(Organization.social_json.isnot(None), Organization.social_json != '{}', Organization.social_json != '').all()
    print(f"Total orgs with social_json: {len(orgs)}")

    ig_handles = Counter()
    ig_to_orgs = {}
    for o in orgs:
        s = o.social_media_dict
        ig = s.get('instagram')
        if ig:
            # extract username
            handle = ig.strip().lower()
            if 'instagram.com/' in handle:
                handle = handle.split('instagram.com/')[-1].split('/')[0].split('?')[0]
            handle = handle.lstrip('@')
            ig_handles[handle] += 1
            if handle not in ig_to_orgs:
                ig_to_orgs[handle] = []
            ig_to_orgs[handle].append((o.id, o.name))

    print(f"Total distinct IG handles: {len(ig_handles)}")
    shared_ig = [(h, count) for h, count in ig_handles.items() if count >= 2]
    print(f"Shared IG handles (>= 2 orgs): {len(shared_ig)}")
    for h, count in sorted(shared_ig, key=lambda x: x[1], reverse=True)[:20]:
        print(f"  @{h}: {count} orgs -> Sample: {[x[1] for x in ig_to_orgs[h][:3]]}")
