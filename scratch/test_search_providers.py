import requests
from bs4 import BeautifulSoup
from urllib.parse import quote_plus, parse_qs, urlparse

def test_bing(query):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    url = f"https://www.bing.com/search?q={quote_plus(query)}&setlang=id&cc=ID"
    r = requests.get(url, headers=headers, timeout=5)
    soup = BeautifulSoup(r.text, "html.parser")
    items = []
    for li in soup.select("li.b_algo"):
        h2 = li.select_one("h2")
        a = li.select_one("h2 a")
        p = li.select_one("div.b_caption p, p")
        if h2 and a:
            href = a.get("href", "")
            items.append({
                "title": h2.get_text(strip=True),
                "url": href,
                "content": p.get_text(strip=True) if p else ""
            })
    return items

def test_ddg_lite(query):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    }
    try:
        r = requests.post("https://lite.duckduckgo.com/lite/", data={"q": query}, headers=headers, timeout=5, verify=False)
        soup = BeautifulSoup(r.text, "html.parser")
        items = []
        for tr in soup.select("tr"):
            link = tr.select_one("a.result-link")
            snippet = tr.select_one("td.result-snippet")
            if link:
                items.append({
                    "title": link.get_text(strip=True),
                    "url": link.get("href", ""),
                    "content": snippet.get_text(strip=True) if snippet else ""
                })
        return items
    except Exception as e:
        return [f"Error: {e}"]

query = "jadwal pameran expo 2026 2027 indonesia"
print("Testing Bing for:", query)
b_res = test_bing(query)
print("Bing found:", len(b_res))
for b in b_res[:3]:
    print(" - Title:", b['title'])
    print("   URL:", b['url'])
    print("   Snippet:", b['content'][:100])

print("\nTesting DDG Lite for:", query)
d_res = test_ddg_lite(query)
print("DDG Lite found:", len(d_res))
for d in d_res[:3]:
    if isinstance(d, dict):
        print(" - Title:", d['title'])
        print("   URL:", d['url'])
