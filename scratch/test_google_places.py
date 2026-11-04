import os
import urllib.request
import json
from dotenv import load_dotenv

load_dotenv()
key = os.environ.get('GOOGLE_SEARCH_API_KEY')
print("Testing Google key:", key[:10] if key else "None")

# Test 1: Google Places Text Search (Legacy)
url_legacy = f"https://maps.googleapis.com/maps/api/place/textsearch/json?query=supplier+kain+bandung&key={key}"
try:
    with urllib.request.urlopen(url_legacy) as resp:
        res = json.loads(resp.read().decode('utf-8'))
        print("Legacy Places Status:", res.get('status'))
        if res.get('error_message'):
            print("Legacy Error:", res.get('error_message'))
        else:
            print("Legacy Results Found:", len(res.get('results', [])))
            for r in res.get('results', [])[:3]:
                print(f" - {r.get('name')} | {r.get('formatted_address')}")
except Exception as e:
    print("Legacy Request Error:", e)

# Test 2: Google Places API (New) Text Search
url_new = "https://places.googleapis.com/v1/places:searchText"
req_new = urllib.request.Request(
    url_new,
    data=json.dumps({"textQuery": "supplier kain bandung"}).encode('utf-8'),
    headers={
        "Content-Type": "application/json",
        "X-Goog-Api-Key": key or "",
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.nationalPhoneNumber,places.websiteUri,places.rating,places.userRatingCount,places.location"
    }
)
try:
    with urllib.request.urlopen(req_new) as resp:
        res_new = json.loads(resp.read().decode('utf-8'))
        places = res_new.get('places', [])
        print("\nNew Places API Status: SUCCESS!")
        print("New Places Found:", len(places))
        for p in places[:3]:
            print(f" - {p.get('displayName', {}).get('text')} | {p.get('formattedAddress')} | Telp: {p.get('nationalPhoneNumber')}")
except urllib.error.HTTPError as e:
    print("\nNew Places API HTTP Error:", e.code, e.read().decode('utf-8'))
except Exception as e:
    print("\nNew Places Request Error:", e)

