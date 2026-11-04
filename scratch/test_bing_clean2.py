import requests
from bs4 import BeautifulSoup

url = "https://www.bing.com/search?q=pameran+tekstil+indonesia+2026+2027&setlang=id&cc=id"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
}
r = requests.get(url, headers=headers, timeout=5)
print("Status:", r.status_code)
soup = BeautifulSoup(r.text, "html.parser")
for li in soup.select("li.b_algo"):
    h2 = li.select_one("h2")
    p = li.select_one("p")
    if h2:
        print(" - Title:", h2.get_text(strip=True))
        if p:
            print("   Desc:", p.get_text(strip=True)[:80])
