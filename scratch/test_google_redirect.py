import re
import requests
from bs4 import BeautifulSoup

session = requests.Session()
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
}

r1 = session.get("https://www.google.co.id/search?q=jadwal+pameran+expo+2026+2027+indonesia&hl=id", headers=headers, timeout=5)
# Find redirect url
m = re.search(r'href="(/httpservice/retry/enablejs\?[^"]+)"', r1.text)
if m:
    redir_url = "https://www.google.co.id" + m.group(1)
    print("Found redirect URL:", redir_url)
    r2 = session.get(redir_url, headers=headers, timeout=5)
    print("After redirect status:", r2.status_code, "HTML length:", len(r2.text))
    soup = BeautifulSoup(r2.text, "html.parser")
    print("H3 tags after redirect:", len(soup.find_all("h3")))
    for h in soup.find_all("h3")[:5]:
        print("  -", h.get_text(strip=True))
