import requests
from bs4 import BeautifulSoup
from urllib.parse import unquote, parse_qs, urlparse

url = "https://www.google.com/search"
params = {
    "q": "jadwal pameran expo 2026 2027 indonesia",
    "hl": "id",
    "gl": "id",
    "num": 10
}
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://www.google.com/"
}
cookies = {
    'CONSENT': 'PENDING+987',
    'SOCS': 'CAESHAgBEhIaAB',
}

resp = requests.get(url, params=params, headers=headers, cookies=cookies, timeout=5)
print("Response status:", resp.status_code, "Length:", len(resp.text))
soup = BeautifulSoup(resp.text, "html.parser")
with open("scratch/req_modern.html", "w", encoding="utf-8") as f:
    f.write(resp.text)

print("H3 tags count:", len(soup.find_all("h3")))
for h in soup.find_all("h3")[:5]:
    print(" - H3:", h.get_text(strip=True))
