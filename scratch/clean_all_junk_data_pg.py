import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + "/.."))

from app import create_app, db
from app.models import Organization, Prospect
import json

app = create_app()

with app.app_context():
    print("=== STARTING COMPREHENSIVE DB CLEANUP ===")
    
    # 1. Hapus 53 record sampah yang namanya diawali 'http'
    bad_url_named = Organization.query.filter(Organization.name.like('http%')).all()
    print(f"1. Menemukan {len(bad_url_named)} organisasi yang namanya berupa URL:")
    deleted_count = 0
    for o in bad_url_named:
        # Hapus prospect legacy terkait jika ada
        Prospect.query.filter_by(organization_id=o.id).delete()
        db.session.delete(o)
        deleted_count += 1
    db.session.commit()
    print(f"   -> Berhasil menghapus {deleted_count} entitas sampah bertitel URL!")

    # 2. Bersihkan social_json dari dynamic_ai_discovery (karena hasil tebakan generator AI)
    ai_orgs = Organization.query.filter_by(source_type='dynamic_ai_discovery').all()
    print(f"2. Memeriksa {len(ai_orgs)} organisasi dynamic_ai_discovery:")
    ai_cleaned = 0
    for o in ai_orgs:
        if o.social_json and o.social_json != "{}":
            o.social_json = "{}"
            ai_cleaned += 1
    db.session.commit()
    print(f"   -> Berhasil menetralkan {ai_cleaned} akun medsos generatif AI agar tidak ada link fiktif!")

    # 3. Sanitasi seluruh social_json di seluruh database
    all_orgs = Organization.query.filter(Organization.social_json.isnot(None), Organization.social_json != "{}", Organization.social_json != "").all()
    print(f"3. Mengaudit {len(all_orgs)} organisasi dengan social_json:")
    
    junk_patterns = [
        "/popular", "/explore", "facebook.com/sharer", "linkedin.com/share",
        "twitter.com/share", "help.instagram.com", "instagram.com/accounts",
        "\ufffd", "propertygenie", "linkedin.com/company/posts", "linkedin.com/feed"
    ]
    
    sanitized_count = 0
    emptied_count = 0

    for o in all_orgs:
        try:
            parsed = json.loads(o.social_json)
            if not isinstance(parsed, dict):
                o.social_json = "{}"
                sanitized_count += 1
                continue
            
            clean_dict = {}
            for k, v in parsed.items():
                if not v or not isinstance(v, str):
                    continue
                v_str = v.strip()
                v_low = v_str.lower()
                
                # Cek jika URL adalah root domain polos (misal https://facebook.com/ atau http://instagram.com)
                if v_low in [
                    "https://www.facebook.com/", "http://www.facebook.com/",
                    "https://facebook.com/", "http://facebook.com/",
                    "https://www.instagram.com/", "http://www.instagram.com/",
                    "https://instagram.com/", "http://instagram.com/",
                    "https://www.linkedin.com/", "http://www.linkedin.com/",
                    "https://linkedin.com/", "http://linkedin.com/"
                ]:
                    continue
                
                # Cek junk patterns
                if any(p in v_low for p in junk_patterns):
                    continue
                
                clean_dict[k] = v_str

            new_json = json.dumps(clean_dict, ensure_ascii=False) if clean_dict else "{}"
            if new_json != o.social_json:
                o.social_json = new_json
                sanitized_count += 1
                if new_json == "{}":
                    emptied_count += 1
        except Exception:
            o.social_json = "{}"
            sanitized_count += 1

    db.session.commit()
    print(f"   -> Berhasil menyanitasi {sanitized_count} organisasi! ({emptied_count} dikosongkan karena hanya berisi link sampah/generic).")

    print("\n=== CLEANUP FINISHED SUCCESSFULLY ===")
