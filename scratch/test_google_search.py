import os
import urllib.request
import json
from dotenv import load_dotenv

load_dotenv()
key = os.environ.get('GOOGLE_SEARCH_API_KEY')
cx = os.environ.get('GOOGLE_SEARCH_ENGINE_ID')

url = f"https://www.googleapis.com/customsearch/v1?key={key}&cx={cx}&q=supplier+kain+bandung"
try:
    with urllib.request.urlopen(url) as resp:
        res = json.loads(resp.read().decode('utf-8'))
        items = res.get('items', [])
        print("Google Custom Search Status: SUCCESS!")
        print("Total items:", len(items))
        for it in items[:3]:
            print("-", it.get('title'), "|", it.get('link'))
except urllib.error.HTTPError as e:
    print("HTTP Error:", e.code, e.read().decode('utf-8'))
except Exception as e:
    print("Error:", e)

