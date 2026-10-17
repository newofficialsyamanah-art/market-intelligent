import urllib.request, urllib.parse, json

user_token = 'EAAq1aS1vkgEBSq2yW73Gexy3bFD2SThY2LUzPK3bc7wfb8VZAcvtHUohgTWWNfJJUYpfZALUriPnFSyazvfhggUVRitxOrqqxM6yQ08VlXuWy7bNmkgJnLW6EkfqQwdbeDj4DvL7zuggV6ZCIwcCKtGsSiVHxRiqXfxSff7G1qM90jIYHPJ8gZCXAZCageebwRa7ZBAbSPASBOEa795NoRB3KeADJsh60BaViY8SuqS5LBqKyonAQAgR6jrXsNURebcJiwpZAJsZBZBHAK2EZB6rTx'

tests = [
    {"ad_reached_countries": "['ID']", "ad_type": "ALL", "search_terms": "kain"},
    {"ad_reached_countries": "['ID']", "ad_active_status": "ACTIVE", "search_terms": "kain"},
    {"ad_reached_countries": "['ID']", "search_terms": "kain"},
    {"ad_reached_countries": "['US']", "ad_type": "POLITICAL_AND_ISSUE_ADS", "search_terms": "vote"}
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
        print(f"Test {i} Failed: Subcode {subcode} | {msg}")
