import requests
from bs4 import BeautifulSoup
from urllib.parse import quote_plus, parse_qs, urlparse

# Test 1: Google with mobile user-agent
url = "https://www.google.com/search?q=" + quote_plus("jadwal pameran expo 2026 2027 indonesia")
headers_mobile = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "id-ID,id;q=0.9"
}
try:
    r = requests.get(url, headers=headers_mobile, timeout=5)
    print("Google Mobile Status:", r.status_code)
    soup = BeautifulSoup(r.text, "html.parser")
    links = []
    for a in soup.find_all("a", href=True):
        href = a['href']
        if "/url?q=" in href:
            clean = parse_qs(urlparse(href).query).get("q", [""])[0]
            if clean.startswith("http") and "google.com" not in clean:
                links.append((a.get_text(strip=True)[:40], clean))
    print("Google Mobile Links:", len(links))
    for l in links[:3]:
        print("  -", l[0], "->", l[1])
except Exception as e:
    print("Google Mobile Error:", e)

# Test 2: Bing
try:
    r_bing = requests.get("https://www.bing.com/search?q=" + quote_plus("jadwal pameran expo 2026 2027 indonesia"), headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}, timeout=5)
    print("\nBing Status:", r_bing.status_code)
    soup_bing = BeautifulSoup(r_bing.text, "html.parser")
    bing_items = []
    for li in soup_bing.select("li.b_algo"):
        h2 = li.select_one("h2")
        p = li.select_one("div.b_caption p, p")
        a = li.select_one("h2 a")
        if h2 and a:
            bing_items.append({
                "title": h2.get_text(strip=True),
                "url": a.get("href", ""),
                "content": p.get_text(strip=True) if p else ""
            })
    print("Bing Items:", len(bing_items))
    for b in bing_items[:3]:
        print("  -", b["title"], "->", b["url"])
        print("    Snippet:", b["content"][:80])
except Exception as e:
    print("Bing Error:", e)

# Test 3: DuckDuckGo HTML
try:
    r_ddg = requests.post("https://html.duckduckgo.com/html/", data={"q": "jadwal pameran expo 2026 2027 indonesia"}, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}, timeout=5)
    print("\nDDG HTML Status:", r_ddg.status_code)
    soup_ddg = BeautifulSoup(r_ddg.text, "html.parser")
    ddg_items = []
    for res in soup_ddg.select(".result"):
        t = res.select_one(".result__title")
        s = res.select_one(".result__snippet")
        u = res.select_one(".result__url")
        if t:
            ddg_items.append({"title": t.get_text(strip=True), "content": s.get_text(strip=True) if s else ""})
    print("DDG Items:", len(ddg_items))
    for d in ddg_items[:3]:
        print("  -", d["title"])
except Exception as e:
    print("DDG Error:", e)
