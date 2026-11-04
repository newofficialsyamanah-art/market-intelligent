import requests
from bs4 import BeautifulSoup
from urllib.parse import parse_qs, urlparse
import base64

def search_bing(query, max_results=10):
    url = "https://www.bing.com/search"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    params = {"q": query, "setlang": "id", "cc": "ID"}
    r = requests.get(url, params=params, headers=headers, timeout=6)
    if r.status_code != 200:
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    items = []
    for li in soup.select("li.b_algo"):
        h2 = li.select_one("h2")
        a = li.select_one("h2 a, a[href]")
        p = li.select_one("div.b_caption p, p")
        if not h2 or not a:
            continue
        title = h2.get_text(strip=True)
        raw_href = a.get("href", "")
        # Resolve Bing redirect
        real_url = raw_href
        if "bing.com/ck/a" in raw_href:
            u_param = parse_qs(urlparse(raw_href).query).get("u", [""])[0]
            if u_param.startswith("a1"):
                try:
                    dec = base64.urlsafe_b64decode(u_param[2:] + "===").decode("utf-8", errors="ignore")
                    if dec.startswith("http"):
                        real_url = dec
                except Exception:
                    pass
        content = p.get_text(strip=True) if p else ""
        if real_url.startswith("http") and "bing.com" not in real_url:
            items.append({
                "title": title,
                "url": real_url,
                "content": content
            })
        if len(items) >= max_results:
            break
    return items

queries = [
    "jadwal event pameran expo surabaya 2026 2027",
    "jadwal pameran ji expo kemayoran 2026 2027",
    "kalender event pariwisata jawa timur 2026 2027",
    "turnamen futsal kejuaraan lari marathon 2026 2027 indonesia"
]

for q in queries:
    res = search_bing(q, max_results=3)
    print(f"\nQuery: '{q}' -> Found {len(res)} results:")
    for r in res:
        print("  *", r["title"][:70])
        print("    Link:", r["url"])
        print("    Content:", r["content"][:120])
