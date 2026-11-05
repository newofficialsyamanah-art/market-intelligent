import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("TAVILY_API_KEY")
print("API Key present:", bool(api_key), api_key[:10] if api_key else "")

queries = [
    'site:instagram.com "2027" (event OR pameran OR festival OR expo OR turnamen OR marathon)',
    'site:facebook.com "2027" (event OR pameran OR festival OR expo OR turnamen)',
    'site:instagram.com/reel "2027" (event OR pameran OR konser OR festival)'
]

for q in queries:
    print(f"\n--- Query: {q} ---")
    payload = {
        "api_key": api_key,
        "query": q,
        "search_depth": "advanced",
        "max_results": 7,
        "include_raw_content": False,
        "include_images": False
    }
    try:
        res = requests.post("https://api.tavily.com/search", json=payload, timeout=12)
        print("Status code:", res.status_code)
        if res.status_code == 200:
            data = res.json()
            results = data.get("results", [])
            print(f"Found {len(results)} results:")
            for item in results:
                print(f"- Title: {item.get('title')}")
                print(f"  URL: {item.get('url')}")
                print(f"  Snippet: {item.get('content')[:160]}...")
        else:
            print("Error response:", res.text)
    except Exception as e:
        print("Exception:", e)

