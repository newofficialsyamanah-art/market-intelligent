import requests
from bs4 import BeautifulSoup
from urllib.parse import quote_plus

url = f"https://www.google.com/search?q={quote_plus('jadwal pameran expo 2026 2027 indonesia')}&hl=id&gl=ID"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
}
resp = requests.get(url, headers=headers, timeout=5)
print("Status:", resp.status_code)
soup = BeautifulSoup(resp.text, "html.parser")
with open("scratch/google_sample.html", "w", encoding="utf-8") as f:
    f.write(resp.text)

print("Title tags:", [t.get_text() for t in soup.select("h3")][:10])
print("Links with /url?q=:", len([a for a in soup.find_all("a", href=True) if "/url?q=" in a['href'] or a['href'].startswith("http")]))
for a in soup.find_all("a", href=True):
    href = a['href']
    if "http" in href and "google" not in href:
        print(a.get_text(strip=True)[:40], "->", href[:70])
