import primp
from bs4 import BeautifulSoup
from urllib.parse import quote_plus, parse_qs, urlparse

client = primp.Client(impersonate="chrome")
url = "https://www.google.co.id/search?q=" + quote_plus("jadwal pameran expo 2026 2027 indonesia") + "&hl=id"

r = client.get(url)
print("Primp Google status:", r.status_code)
print("Primp Google HTML length:", len(r.text))
soup = BeautifulSoup(r.text, "html.parser")
h3s = soup.find_all("h3")
print("Found h3 tags:", len(h3s))
for h in h3s[:5]:
    print(" - H3:", h.get_text(strip=True))

links = []
for a in soup.find_all("a", href=True):
    href = a['href']
    if "/url?q=" in href:
        clean = parse_qs(urlparse(href).query).get("q", [""])[0]
        if clean.startswith("http") and "google.com" not in clean:
            links.append((a.get_text(strip=True)[:40], clean))
    elif href.startswith("http") and "google.com" not in href:
        links.append((a.get_text(strip=True)[:40], href))

print("Found real links:", len(links))
for l in links[:5]:
    print("  ->", l[0], "|", l[1])
