with open("scratch/gmaps_resp.html", "r", encoding="utf-8") as f:
    text = f.read()

import re
matches = re.findall(r'window\.([a-zA-Z0-9_]+)\s*=', text)
print("window variables:", matches)

