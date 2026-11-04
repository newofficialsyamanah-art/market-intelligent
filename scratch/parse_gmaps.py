import re
import json

with open("scratch/gmaps_resp.html", "r", encoding="utf-8") as f:
    html = f.read()

# Check for window.APP_INITIALIZATION_STATE
match = re.search(r'window\.APP_INITIALIZATION_STATE\s*=\s*(.*?);window\.', html, re.DOTALL)
if match:
    print("Found window.APP_INITIALIZATION_STATE!")
    raw_json = match.group(1)
    print("Length of raw_json:", len(raw_json))
    try:
        data = json.loads(raw_json)
        print("Successfully parsed APP_INITIALIZATION_STATE JSON!")
    except Exception as e:
        print("JSON parse error:", e)

# Also check for other patterns like /maps/place/
places = re.findall(r'https?://(?:www\.)?google\.com/maps/place/([^/]+)/@([0-9\.\,\-]+)', html)
print("Found place URLs:", len(places))
for p in places[:5]:
    print("Place:", p[0], "Coords:", p[1])

