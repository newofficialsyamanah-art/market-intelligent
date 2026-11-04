import requests
from bs4 import BeautifulSoup

portals = [
    ("JIExpo", "https://jiexpo.com/events/"),
    ("SerbaEvent", "https://serbaevent.net/"),
    ("DutaEvent", "https://dutaevent.com/"),
    ("EventKampus", "https://eventkampus.com/"),
]

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

for name, url in portals:
    try:
        r = requests.get(url, headers=headers, timeout=6)
        print(f"[{name}] Status: {r.status_code}, Length: {len(r.text)}")
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            titles = [t.get_text(strip=True) for t in soup.find_all(["h2", "h3", "h4"]) if len(t.get_text(strip=True)) > 5]
            print(f"  Sample titles ({len(titles)} found):", titles[:3])
    except Exception as e:
        print(f"[{name}] Error: {e}")
