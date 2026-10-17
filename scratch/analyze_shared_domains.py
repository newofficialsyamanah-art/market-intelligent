import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + "/.."))

from app import create_app, db
from app.models import Organization
from collections import Counter
from urllib.parse import urlparse

app = create_app()

with app.app_context():
    orgs = Organization.query.filter(Organization.website.isnot(None), Organization.website != '').all()
    print(f"Total orgs with website: {len(orgs)}")

    # Hitung frekuensi domain
    domain_to_orgs = {}
    for o in orgs:
        raw = (o.website or '').strip().lower()
        if not raw: continue
        if not raw.startswith('http'): raw = 'https://' + raw
        try:
            netloc = urlparse(raw).netloc.replace('www.', '')
            if netloc not in domain_to_orgs:
                domain_to_orgs[netloc] = []
            domain_to_orgs[netloc].append(o.id)
        except:
            pass

    # Domain yang di-share oleh >= 2 organisasi
    shared_domains = {d: ids for d, ids in domain_to_orgs.items() if len(ids) >= 2}
    print(f"Total shared/generic domains: {len(shared_domains)}")
    total_affected_orgs = sum(len(ids) for ids in shared_domains.values())
    print(f"Total organizations affected by generic shared domains: {total_affected_orgs}")

    # Tampilkan 25 domain generic teratas
    sorted_shared = sorted(shared_domains.items(), key=lambda x: len(x[1]), reverse=True)
    for d, ids in sorted_shared[:25]:
        print(f"  {d}: {len(ids)} orgs")
