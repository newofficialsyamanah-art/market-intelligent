import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app, db
from app.models import Event
import json

# Kamus pemetaan data resmi event nasional Indonesia
EVENT_ENRICHMENT_CATALOG = [
    {
        "keywords": ["jakarta fashion week", "jfw"],
        "website": "https://jakartafashionweek.co.id",
        "instagram": "https://www.instagram.com/jfwofficial",
        "source_url": "https://jakartafashionweek.co.id"
    },
    {
        "keywords": ["pet expo", "iipe"],
        "website": "https://iipe.co.id",
        "instagram": "https://www.instagram.com/iipe.id",
        "source_url": "https://iipe.co.id"
    },
    {
        "keywords": ["furniture & woodworking", "ifmac"],
        "website": "https://ifmac.net",
        "instagram": "https://www.instagram.com/ifmacwoodmac",
        "source_url": "https://ifmac.net"
    },
    {
        "keywords": ["food & beverage expo", "jifbe", "sial interfood"],
        "website": "https://sialinterfood.com",
        "instagram": "https://www.instagram.com/sialinterfood",
        "source_url": "https://sialinterfood.com"
    },
    {
        "keywords": ["automotive aftermarket", "inapa"],
        "website": "https://inapa-indonesia.net",
        "instagram": "https://www.instagram.com/inapaindonesia",
        "source_url": "https://inapa-indonesia.net"
    },
    {
        "keywords": ["jatim expo"],
        "website": "https://jatimexpo.id",
        "instagram": "https://www.instagram.com/jatimexpo",
        "source_url": "https://jatimexpo.id"
    },
    {
        "keywords": ["giias", "gaikindo"],
        "website": "https://indonesiaautoshow.com",
        "instagram": "https://www.instagram.com/giias_id",
        "source_url": "https://indonesiaautoshow.com"
    },
    {
        "keywords": ["indobuildtech"],
        "website": "https://indobuildtech.com",
        "instagram": "https://www.instagram.com/indobuildtech",
        "source_url": "https://indobuildtech.com"
    },
    {
        "keywords": ["apparel production expo", "iape"],
        "website": "https://apparelexpo.id",
        "instagram": "https://www.instagram.com/apparelexpo",
        "source_url": "https://apparelexpo.id"
    },
    {
        "keywords": ["ifbc", "info franchise"],
        "website": "https://infofranchiseexpo.com",
        "instagram": "https://www.instagram.com/infofranchiseexpo",
        "source_url": "https://infofranchiseexpo.com"
    },
    {
        "keywords": ["surabaya printing expo"],
        "website": "https://surabayaprintingexpo.com",
        "instagram": "https://www.instagram.com/kristamedia",
        "source_url": "https://surabayaprintingexpo.com"
    },
    {
        "keywords": ["eastfood indonesia", "east food"],
        "website": "https://eastfoodindonesia.com",
        "instagram": "https://www.instagram.com/kristamedia",
        "source_url": "https://eastfoodindonesia.com"
    },
    {
        "keywords": ["allpack", "all pack"],
        "website": "https://allpack-indonesia.com",
        "instagram": "https://www.instagram.com/allpack_indonesia",
        "source_url": "https://allpack-indonesia.com"
    },
    {
        "keywords": ["palmoil", "palmex"],
        "website": "https://palmoilexpo.com",
        "instagram": "https://www.instagram.com/palmoilexpo",
        "source_url": "https://palmoilexpo.com"
    },
    {
        "keywords": ["surabaya marathon"],
        "website": "https://surabayamarathon.com",
        "instagram": "https://www.instagram.com/surabayamarathon",
        "source_url": "https://kalenderlari.com/events/surabaya-marathon-2026"
    },
    {
        "keywords": ["borobudur marathon"],
        "website": "https://borobudurmarathon.com",
        "instagram": "https://www.instagram.com/borobudur.marathon",
        "source_url": "https://borobudurmarathon.com"
    },
    {
        "keywords": ["makassar half marathon"],
        "website": "https://makassarhalfmarathon.com",
        "instagram": "https://www.instagram.com/makassarhalfmarathon",
        "source_url": "https://makassarhalfmarathon.com"
    },
    {
        "keywords": ["futsal nation cup", "futsal series"],
        "website": "https://futsalseries.com",
        "instagram": "https://www.instagram.com/futsalseriesid",
        "source_url": "https://futsalseries.com"
    },
    {
        "keywords": ["axis nation cup"],
        "website": "https://axis.co.id/anc",
        "instagram": "https://www.instagram.com/axis_id",
        "source_url": "https://axis.co.id"
    },
    {
        "keywords": ["bca expo"],
        "website": "https://expo.bca.co.id",
        "instagram": "https://www.instagram.com/goodlifebca",
        "source_url": "https://expo.bca.co.id"
    },
    {
        "keywords": ["kadin sumsel expo"],
        "website": "https://kadin.id",
        "instagram": "https://www.instagram.com/kadin.indonesia.official",
        "source_url": "https://kadin.id/acara/kadin-sumsel-expo-2026-dan-ifbex/"
    },
    {
        "keywords": ["balikpapan expo"],
        "website": "https://balikpapanexpo.com",
        "instagram": "https://www.instagram.com/balikpapanexpo",
        "source_url": "https://balikpapanexpo.com"
    },
    {
        "keywords": ["pontianak expo"],
        "website": "https://pontianakexpo.com",
        "instagram": "https://www.instagram.com/pontianakexpo",
        "source_url": "https://pontianakexpo.com"
    },
    {
        "keywords": ["sriwijaya expo"],
        "website": "https://palembang.go.id",
        "instagram": "https://www.instagram.com/pariwisata.palembang",
        "source_url": "https://palembang.go.id"
    },
    {
        "keywords": ["energy & power expo", "jiepe", "power expo"],
        "website": "https://electricindonesia.com",
        "instagram": "https://www.instagram.com/electric_indonesia",
        "source_url": "https://electricindonesia.com"
    },
    {
        "keywords": ["beauty & cosmetics", "cosmobeaute"],
        "website": "https://cosmobeauteindonesia.com",
        "instagram": "https://www.instagram.com/cosmobeauteindonesia",
        "source_url": "https://cosmobeauteindonesia.com"
    },
    {
        "keywords": ["travel expo", "jite"],
        "website": "https://astindo-travel-fair.com",
        "instagram": "https://www.instagram.com/astindotravelfair",
        "source_url": "https://astindo-travel-fair.com"
    },
    {
        "keywords": ["mining indonesia"],
        "website": "https://miningindonesia.com",
        "instagram": "https://www.instagram.com/miningindonesia_official",
        "source_url": "https://miningindonesia.com"
    },
    {
        "keywords": ["kalimantan marine expo"],
        "website": "https://kalimantanmarine.com",
        "instagram": "https://www.instagram.com/kalimantanmarine",
        "source_url": "https://kalimantanmarine.com"
    },
    {
        "keywords": ["iims", "indonesia international motor show"],
        "website": "https://indonesiamotorshow.com",
        "instagram": "https://www.instagram.com/iims_id",
        "source_url": "https://indonesiamotorshow.com"
    }
]

def enrich():
    app = create_app()
    with app.app_context():
        print("=" * 60)
        print("MEMULAI ENRICHMENT METADATA WEBSITE & SOSMED EVENT")
        print("=" * 60)

        events = Event.query.all()
        enriched_count = 0

        for ev in events:
            ev_name_low = ev.name.lower()
            for entry in EVENT_ENRICHMENT_CATALOG:
                # Check keywords
                match = any(kw in ev_name_low for kw in entry["keywords"])
                if match:
                    modified = False
                    if not ev.website and entry.get("website"):
                        ev.website = entry["website"]
                        modified = True

                    if entry.get("instagram"):
                        cur_social = {}
                        if ev.social_json:
                            try:
                                cur_social = json.loads(ev.social_json)
                                if not isinstance(cur_social, dict):
                                    cur_social = {}
                            except Exception:
                                cur_social = {}
                        if not cur_social.get("instagram"):
                            cur_social["instagram"] = entry["instagram"]
                            ev.social_json = json.dumps(cur_social)
                            modified = True

                    if not ev.source_url or not ev.source_url.startswith("http"):
                        if entry.get("source_url"):
                            ev.source_url = entry["source_url"]
                            modified = True

                    if modified:
                        enriched_count += 1
                        print(f"[ENRICHED] ID {ev.id}: {ev.name} -> Web: {ev.website} | IG: {entry.get('instagram')}")
                    break

        db.session.commit()
        print("-" * 60)
        print(f"Total event yang berhasil diperkaya (enriched): {enriched_count}")
        print(f"Total event dengan website bersih: {Event.query.filter(Event.website.isnot(None), Event.website != '').count()}")
        print(f"Total event dengan Instagram/Sosmed: {Event.query.filter(Event.social_json.isnot(None), Event.social_json != '').count()}")
        print(f"Total event dengan source_url valid: {Event.query.filter(Event.source_url.like('http%')).count()}")

if __name__ == "__main__":
    enrich()
