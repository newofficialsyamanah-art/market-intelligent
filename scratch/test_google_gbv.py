import requests
from bs4 import BeautifulSoup
from urllib.parse import quote_plus, parse_qs, urlparse

url = "https://www.google.com/search?q=" + quote_plus("jadwal pameran expo indonesia 2026 2027") + "&gbv=1&hl=id"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

r = requests.get(url, headers=headers, timeout=5)
print("Google gbv=1 Status:", r.status_code)
soup = BeautifulSoup(r.text, "html.parser")

results = []
for a in soup.find_all("a", href=True):
    href = a['href']
    if "/url?q=" in href:
        clean_url = parse_qs(urlparse(href).query).get("q", [""])[0]
        if clean_url.startswith("http") and "google.com" not in clean_url:
            # find title / heading
            title = a.get_text(strip=True)
            if title and len(title) > 3:
                # find snippet parent
                parent = a.find_parent("div")
                snippet = ""
                if parent:
                    snippet = parent.get_text(strip=True)
                results.append({"title": title, "url": clean_url, "snippet": snippet})

print("Found via Google gbv=1:", len(results))
for r in results[:5]:
    print("Title:", r["title"][:60])
    print("URL:", r["url"])
    print("-" * 30)
