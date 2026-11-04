import primp
from bs4 import BeautifulSoup

client = primp.Client(impersonate="chrome_128")
url = "https://www.google.co.id/search?q=pameran+expo+2026+2027+indonesia&hl=id"

try:
    r = client.get(url)
    print("Status code with primp Chrome 128:", r.status_code)
    print("HTML length:", len(r.text))
    soup = BeautifulSoup(r.text, "html.parser")
    h3s = soup.find_all("h3")
    print("Found h3 tags:", len(h3s))
    for h in h3s[:8]:
        a = h.find_parent("a") or h.find("a")
        href = a.get("href") if a else "No link"
        print("  - H3:", h.get_text(strip=True)[:60])
        print("    Link:", href)
except Exception as e:
    print("Error with primp:", e)
