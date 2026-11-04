from googlesearch import _req
from bs4 import BeautifulSoup

resp = _req("pameran expo 2026 2027 indonesia", 10, "id", 0, None, 5, "active", None, "ID")
print("Response status:", resp.status_code, "Length:", len(resp.text))
soup = BeautifulSoup(resp.text, "html.parser")
with open("scratch/req_google.html", "w", encoding="utf-8") as f:
    f.write(resp.text)

print("Title tags in req_google:", len(soup.find_all("h3")))
for h in soup.find_all("h3")[:5]:
    print(" - H3:", h.get_text(strip=True))

links = []
for a in soup.find_all("a", href=True):
    h = a['href']
    if "/url?q=" in h or (h.startswith("http") and "google.com" not in h):
        links.append((a.get_text(strip=True)[:40], h[:80]))
print("Found links in req_google:", len(links))
for l in links[:5]:
    print("  ->", l[0], "|", l[1])
