import requests
import json

searx_instances = [
    "https://searx.be/search",
    "https://search.ononoki.org/search",
    "https://baresearch.org/search",
    "https://searx.tiekoetter.com/search",
]

for inst in searx_instances:
    try:
        r = requests.get(inst, params={"q": "pameran expo indonesia 2026 2027", "format": "json"}, headers={"User-Agent": "Mozilla/5.0"}, timeout=4)
        if r.status_code == 200:
            data = r.json()
            res = data.get("results", [])
            print(f"[{inst}] SUCCESS! Results: {len(res)}")
            for item in res[:3]:
                print("  *", item.get("title"), "->", item.get("url"))
            break
        else:
            print(f"[{inst}] Status {r.status_code}")
    except Exception as e:
        print(f"[{inst}] Error: {e}")
