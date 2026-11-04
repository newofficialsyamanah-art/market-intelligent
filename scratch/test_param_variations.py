import urllib.request, urllib.parse, json

user_token = 'EAAq1aS1vkgEBS79lu1rtqduNZBDQVEhupApSiL1fLzjeZA4zRFo2lxJAsmKVQ5PVYp2VowXrXEWkEUYWRtHOrZBLRQ7QTz6bAsMkuyjycCTHdjqdpymgwIvYf7VqfpBWLG93UXFC9rzDWtZBoTtUgttBbZCpd8CLL26PDWk3qUWRdTXyarl8TO3U81Y17HQBWpwtwRaUZCq4BK6bgmR75rNoy0QIlWI7C4kDijej0y7jZAZBGUYvgnMIDKaD24yXYlfddZAtphfPWS16j'

tests = [
    {"ad_reached_countries": "['ID']", "ad_type": "ALL", "search_terms": "kain"},
    {"ad_reached_countries": "['ID']", "ad_active_status": "ACTIVE", "search_terms": "kain"},
    {"ad_reached_countries": "['ID']", "search_terms": "kain"},
    {"ad_reached_countries": "['US']", "ad_type": "POLITICAL_AND_ISSUE_ADS", "search_terms": "vote"},
    {"ad_reached_countries": "['ID']", "ad_type": "POLITICAL_AND_ISSUE_ADS", "search_terms": "pemilu"},
    {"ad_reached_countries": "['ID']", "ad_type": "EMPLOYMENT_ADS", "search_terms": "lowongan"},
]

for i, p in enumerate(tests, 1):
    p["access_token"] = user_token
    url = f"https://graph.facebook.com/v19.0/ads_archive?{urllib.parse.urlencode(p)}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req) as r:
            data = json.loads(r.read().decode("utf-8"))
            print(f"Test {i} SUCCESS! Data count: {len(data.get('data', []))}")
    except urllib.error.HTTPError as e:
        err = json.loads(e.read().decode("utf-8"))
        subcode = err.get("error", {}).get("error_subcode")
        msg = err.get("error", {}).get("error_user_msg", err.get("error", {}).get("message"))
        print(f"Test {i} Failed: Code {err.get('error', {}).get('code')} Subcode {subcode} | {msg}")
