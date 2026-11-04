import requests
from bs4 import BeautifulSoup

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
}

url = "https://www.google.com/maps/search/supplier+kain+bandung"
r = requests.get(url, headers=headers, timeout=10)
print("Status code:", r.status_code)
print("HTML length:", len(r.text))
with open("scratch/gmaps_resp.html", "w", encoding="utf-8") as f:
    f.write(r.text[:50000])

