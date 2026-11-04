import requests
from bs4 import BeautifulSoup
from urllib.parse import quote_plus

# Test Qwant
try:
    r_qwant = requests.get("https://api.qwant.com/v3/search/web?q=" + quote_plus("pameran expo indonesia 2026 2027") + "&count=10&locale=id_id", headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
    print("Qwant status:", r_qwant.status_code)
    if r_qwant.status_code == 200:
        data = r_qwant.json()
        items = data.get("data", {}).get("result", {}).get("items", {}).get("mainline", [])
        print("Qwant items:", len(items))
except Exception as e:
    print("Qwant error:", e)

# Test Mojeek
try:
    r_mojeek = requests.get("https://www.mojeek.com/search?q=" + quote_plus("pameran expo indonesia 2026 2027"), headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
    print("Mojeek status:", r_mojeek.status_code)
    soup_m = BeautifulSoup(r_mojeek.text, "html.parser")
    m_links = soup_m.select("a.ob")
    print("Mojeek links:", len(m_links))
    for m in m_links[:3]:
        print(" - Mojeek:", m.get_text(strip=True)[:50], m.get("href"))
except Exception as e:
    print("Mojeek error:", e)
