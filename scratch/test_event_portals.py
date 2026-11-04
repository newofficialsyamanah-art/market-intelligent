import requests
from bs4 import BeautifulSoup

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

targets = [
    ("JadwalEvent.web.id", "https://jadwalevent.web.id/"),
    ("ICE BSD Calendar", "https://ice-indonesia.com/calendar-of-events/"),
    ("JIExpo Kemayoran", "https://jiexpo.com/events/"),
    ("Grand City Surabaya", "https://grandcitysurabaya.com/events/"),
]

for name, url in targets:
    try:
        r = requests.get(url, headers=headers, timeout=6)
        print(f"[{name}] Status: {r.status_code}, Length: {len(r.text)}")
    except Exception as e:
        print(f"[{name}] Error: {e}")
