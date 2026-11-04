import os
import urllib.request
import json
from dotenv import load_dotenv

load_dotenv()
key = os.environ.get('TAVILY_API_KEY')
print("Tavily key present:", bool(key))

req = urllib.request.Request(
    'https://api.tavily.com/search',
    data=json.dumps({'api_key': key, 'query': 'supplier kain bandung'}).encode('utf-8'),
    headers={'Content-Type': 'application/json'}
)
try:
    with urllib.request.urlopen(req) as resp:
        res = json.loads(resp.read().decode('utf-8'))
        results = res.get('results', [])
        print("Tavily results count:", len(results))
        for r in results[:3]:
            print("-", r.get('title'), "|", r.get('url'))
except urllib.error.HTTPError as e:
    print("HTTP Error:", e.code, e.read().decode('utf-8'))
except Exception as e:
    print("Error:", e)

