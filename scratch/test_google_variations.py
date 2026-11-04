import requests
from bs4 import BeautifulSoup

session = requests.Session()
# First, visit google.co.id home to get consent/session cookies
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
    "Sec-Ch-Ua": '"Chromium";v="128", "Not;A=Brand";v="24", "Google Chrome";v="128"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1"
}

r1 = session.get("https://www.google.co.id/", headers=headers, timeout=5)
print("Homepage status:", r1.status_code, "Cookies:", session.cookies.get_dict())

headers["Referer"] = "https://www.google.co.id/"
headers["Sec-Fetch-Site"] = "same-origin"

r2 = session.get("https://www.google.co.id/search?q=jadwal+pameran+expo+2026+2027+indonesia&hl=id", headers=headers, timeout=5)
print("Search status:", r2.status_code)
print("HTML length:", len(r2.text))
soup = BeautifulSoup(r2.text, "html.parser")
h3s = soup.find_all("h3")
print("Found h3 tags:", len(h3s))
for h in h3s[:5]:
    a = h.find_parent("a") or h.find("a")
    print(" - H3:", h.get_text(strip=True), "Link:", a.get("href") if a else "No link")
