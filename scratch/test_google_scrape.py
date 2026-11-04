import requests
from bs4 import BeautifulSoup
from urllib.parse import quote_plus, parse_qs, urlparse, unquote

def search_google(query, num_results=10):
    url = f"https://www.google.com/search?q={quote_plus(query)}&num={num_results}&hl=id&gl=ID"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://www.google.com/",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=5)
        print("Google Status:", resp.status_code)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            results = []
            # Search result containers
            for g in soup.select("div.g, div[data-hveid]"):
                link = g.select_one("a[href]")
                title = g.select_one("h3")
                snippet = g.select_one("div[data-sncf], div.VwiC3b, div[style*='-webkit-line-clamp']")
                
                if link and title:
                    href = link.get("href", "")
                    if href.startswith("/url?q="):
                        href = parse_qs(urlparse(href).query).get("q", [""])[0]
                    if href.startswith("http") and "google.com" not in href:
                        results.append({
                            "title": title.get_text(strip=True),
                            "url": href,
                            "content": snippet.get_text(strip=True) if snippet else ""
                        })
            return results
    except Exception as e:
        print("Google search error:", e)
    return []

res = search_google("jadwal pameran expo 2026 2027 indonesia")
print("Total found:", len(res))
for r in res[:5]:
    print("Title:", r["title"])
    print("URL:", r["url"])
    print("Snippet:", r["content"][:100])
    print("-" * 40)
