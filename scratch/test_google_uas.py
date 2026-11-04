import requests
from bs4 import BeautifulSoup
from urllib.parse import unquote, parse_qs, urlparse

# Test different User-Agents on Google
uas = [
    # Android Chrome
    "Mozilla/5.0 (Linux; Android 13; SM-S908B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Mobile Safari/537.36",
    # iPad
    "Mozilla/5.0 (iPad; CPU OS 16_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Mobile/15E148 Safari/604.1",
    # Older Firefox
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0",
]

for i, ua in enumerate(uas):
    try:
        r = requests.get(
            "https://www.google.co.id/search?q=pameran+expo+surabaya+2026+2027&hl=id",
            headers={"User-Agent": ua, "Accept-Language": "id-ID,id;q=0.9"},
            timeout=5
        )
        soup = BeautifulSoup(r.text, "html.parser")
        # Check titles
        titles = [t.get_text(strip=True) for t in soup.find_all(["h3", "h4", "div.BNeawe"])]
        links = []
        for a in soup.find_all("a", href=True):
            h = a['href']
            if "/url?q=" in h or (h.startswith("http") and "google" not in h):
                links.append(h)
        print(f"UA #{i} ({ua[:30]}...): Status {r.status_code}, HTML {len(r.text)}, Titles {len(titles)}, Links {len(links)}")
        if titles:
            print("  Sample title:", titles[:3])
    except Exception as e:
        print(f"UA #{i} Error:", e)
