import os
import sys
sys.path.insert(0, os.path.abspath("."))
import requests
import json
from dotenv import load_dotenv

load_dotenv()
google_api_key = os.getenv("GOOGLE_SEARCH_API_KEY")
google_cx = os.getenv("GOOGLE_SEARCH_ENGINE_ID")

print("Google CSE configured:", bool(google_api_key and google_cx))

queries = [
    'site:instagram.com "2027" (event OR pameran OR festival OR expo OR marathon)',
    'site:facebook.com "2027" (event OR pameran OR festival OR expo)',
]

# 1. Test Google CSE
if google_api_key and google_cx:
    for q in queries:
        print(f"\n[Google CSE] Query: {q}")
        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            "key": google_api_key,
            "cx": google_cx,
            "q": q,
            "num": 5
        }
        try:
            r = requests.get(url, params=params, timeout=8)
            print("Status code:", r.status_code)
            if r.status_code == 200:
                data = r.json()
                items = data.get("items", [])
                print(f"Found {len(items)} items:")
                for it in items:
                    print(f" - {it.get('title')}")
                    print(f"   URL: {it.get('link')}")
                    print(f"   Snippet: {it.get('snippet', '')[:120]}")
            else:
                print("Error:", r.text[:200])
        except Exception as e:
            print("Google CSE exception:", e)

# 2. Test Bing search fallback
from app.discovery import _bing_search_fallback
for q in queries:
    print(f"\n[Bing] Query: {q}")
    links = _bing_search_fallback(q)
    print(f"Bing found {len(links)} links:")
    for l in links[:5]:
        print(" -", l)
