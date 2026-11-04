import requests
from bs4 import BeautifulSoup
from urllib.parse import quote_plus, parse_qs, urlparse

# Test 1: Yahoo Search
try:
    url_yahoo = "https://search.yahoo.com/search?p=" + quote_plus("jadwal pameran expo indonesia 2026 2027")
    r_yahoo = requests.get(url_yahoo, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}, timeout=5)
    print("Yahoo Status:", r_yahoo.status_code)
    soup_y = BeautifulSoup(r_yahoo.text, "html.parser")
    y_items = []
    for li in soup_y.select("ol.searchCenterMiddle li, div.algo"):
        h3 = li.select_one("h3 a")
        p = li.select_one("div.compText p, p")
        if h3:
            y_items.append({"title": h3.get_text(strip=True), "url": h3.get("href"), "content": p.get_text(strip=True) if p else ""})
    print("Yahoo Items:", len(y_items))
    for it in y_items[:3]:
        print("  -", it["title"], "->", it["url"][:60])
except Exception as e:
    print("Yahoo error:", e)

# Test 2: Google with specific headers or Lynx
try:
    url_g = "https://www.google.com/search?q=" + quote_plus("jadwal pameran expo indonesia 2026 2027") + "&hl=en"
    headers_lynx = {
        "User-Agent": "Lynx/2.8.9rel.1 libwww-FM/2.14 SSL-MM/1.4.1 GNUTLS/3.6.13",
        "Accept": "*/*"
    }
    rg = requests.get(url_g, headers=headers_lynx, timeout=5)
    print("Google Lynx Status:", rg.status_code)
    soup_g = BeautifulSoup(rg.text, "html.parser")
    links_g = []
    for a in soup_g.find_all("a", href=True):
        h = a['href']
        if "/url?q=" in h:
            clean = parse_qs(urlparse(h).query).get("q", [""])[0]
            if clean.startswith("http") and "google.com" not in clean:
                links_g.append((a.get_text(strip=True), clean))
    print("Google Lynx Links:", len(links_g))
    for lg in links_g[:3]:
        print("  -", lg[0][:40], "->", lg[1][:60])
except Exception as e:
    print("Google Lynx error:", e)
