import requests
from bs4 import BeautifulSoup
import re

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
r = requests.get("https://jiexpo.com/events/", headers=headers, timeout=6)
soup = BeautifulSoup(r.text, "html.parser")

events = []
# look for event title links or items
for item in soup.find_all(["div", "article"], class_=re.compile(r"event", re.I)):
    title_el = item.find(["h2", "h3", "h4", "a"])
    if title_el:
        t = title_el.get_text(strip=True)
        if len(t) > 5 and t not in events:
            events.append(t)

print("Found JIExpo events:", len(events))
for e in events[:10]:
    print(" -", e)

# Also check raw text for upcoming events
links = [a.get("href") for a in soup.find_all("a", href=True) if "/event/" in a.get("href")]
print("Event links:", set(links))
