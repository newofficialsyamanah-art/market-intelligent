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
    print("=== STARTING PURGE OF ALL FAKE & GENERIC DATA IN MASTER ORGANIZATIONS ===")

    # -------------------------------------------------------------
    # 1. PURGE GENERIC & SHARED WEBSITES
    # -------------------------------------------------------------
    orgs_with_web = Organization.query.filter(Organization.website.isnot(None), Organization.website != '').all()
    print(f"Total orgs with website initially: {len(orgs_with_web)}")

    # Hitung frekuensi domain netloc
    domain_to_orgs = {}
    for o in orgs_with_web:
        raw = (o.website or '').strip().lower()
        if not raw: continue
        if not raw.startswith('http'): raw = 'https://' + raw
        try:
            netloc = urlparse(raw).netloc.replace('www.', '')
            if netloc not in domain_to_orgs:
                domain_to_orgs[netloc] = []
            domain_to_orgs[netloc].append(o.id)
        except Exception:
            pass

    # Blacklist domain-domain yang di-share oleh >= 2 organisasi yang tidak masuk akal
    generic_domains_to_null = set()
    for d, ids in domain_to_orgs.items():
        if len(ids) >= 2:
            generic_domains_to_null.add(d)

    # Tambahkan domain broker & spam
    extra_bad_domains = [
        "domainmarket.com", "brandbucket.com", "propertygenie.com.my", 
        "lazada.co.id", "lazada.com", "shopee.co.id", "tokopedia.com",
        "facebook.com", "instagram.com", "linkedin.com", "twitter.com",
        "damart.fr", "enanyang.my", "kotak.bank.in", "pattilabelle.com"
    ]
    for bd in extra_bad_domains:
        generic_domains_to_null.add(bd)

    purged_web_count = 0
    for o in orgs_with_web:
        raw = (o.website or '').strip().lower()
        if not raw: continue
        if not raw.startswith('http'): raw = 'https://' + raw
        try:
            netloc = urlparse(raw).netloc.replace('www.', '')
            if netloc in generic_domains_to_null:
                o.website = None
                o.domain = None
                purged_web_count += 1
        except Exception:
            pass

    db.session.commit()
    print(f"-> Berhasil membersihkan {purged_web_count} website generic/palsu dari Master Organization!")

    # -------------------------------------------------------------
    # 2. PURGE FAKE & SHARED INSTAGRAM / SOCIAL MEDIA
    # -------------------------------------------------------------
    orgs_with_social = Organization.query.filter(Organization.social_json.isnot(None), Organization.social_json != '{}', Organization.social_json != '').all()
    print(f"\nTotal orgs with social_json initially: {len(orgs_with_social)}")

    # Hitung frekuensi handle IG
    ig_handles = Counter()
    for o in orgs_with_social:
        s = o.social_media_dict
        ig = s.get('instagram')
        if ig:
            handle = ig.strip().lower()
            if 'instagram.com/' in handle:
                handle = handle.split('instagram.com/')[-1].split('/')[0].split('?')[0]
            handle = handle.lstrip('@')
            ig_handles[handle] += 1

    shared_ig_handles = {h for h, count in ig_handles.items() if count >= 2}
    extra_bad_ig = {
        "lazada_id", "domainmarketcom", "brandbucket", "global", "popular",
        "explore", "accounts", "posts", "indonesia", "instagram", "facebook"
    }
    all_bad_ig = shared_ig_handles.union(extra_bad_ig)

    purged_ig_count = 0
    empty_social_count = 0

    for o in orgs_with_social:
        try:
            parsed = json.loads(o.social_json)
            if not isinstance(parsed, dict):
                o.social_json = "{}"
                empty_social_count += 1
                continue

            cleaned_dict = {}
            for platform, url in parsed.items():
                if not url or not isinstance(url, str):
                    continue
                u_str = url.strip()
                u_low = u_str.lower()

                # Cek IG
                if platform == "instagram":
                    h = u_low
                    if 'instagram.com/' in h:
                        h = h.split('instagram.com/')[-1].split('/')[0].split('?')[0]
                    h = h.lstrip('@')
                    if h in all_bad_ig:
                        purged_ig_count += 1
                        continue

                # Cek Facebook root / generic
                if platform == "facebook":
                    if u_low in ["https://www.facebook.com/", "https://facebook.com/", "http://www.facebook.com/", "http://facebook.com/"]:
                        continue

                # Cek LinkedIn generic
                if platform == "linkedin":
                    if any(x in u_low for x in ["linkedin.com/feed", "linkedin.com/company/posts", "linkedin.com/share"]):
                        continue

                cleaned_dict[platform] = u_str

            new_json = json.dumps(cleaned_dict, ensure_ascii=False) if cleaned_dict else "{}"
            if new_json != o.social_json:
                o.social_json = new_json
                if new_json == "{}":
                    empty_social_count += 1
        except Exception:
            o.social_json = "{}"
            empty_social_count += 1

    db.session.commit()
    print(f"-> Berhasil membersihkan {purged_ig_count} akun Instagram palsu/shared!")
    print(f"-> Total organisasi yang social_json-nya kini bersih: {empty_social_count} dinetralkan ke 'Belum terdata'.")

    # -------------------------------------------------------------
    # 3. VERIFIKASI SISA DATA
    # -------------------------------------------------------------
    remaining_web = Organization.query.filter(Organization.website.isnot(None), Organization.website != '').count()
    remaining_social = Organization.query.filter(Organization.social_json.isnot(None), Organization.social_json != '{}', Organization.social_json != '').count()
    print(f"\n=== HASIL AKHIR VERIFIKASI DATA MASTER ===")
    print(f"Total Master Organizations: {Organization.query.count()}")
    print(f"Website Unik & Valid Tersisa: {remaining_web}")
    print(f"Social Media Unik & Valid Tersisa: {remaining_social}")
    print("=== SELESAI DENGAN SUKSES ===")
