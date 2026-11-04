import subprocess
import json
from bs4 import BeautifulSoup
from urllib.parse import quote_plus, parse_qs, urlparse

chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
query = "jadwal pameran expo 2026 2027 indonesia"
url = f"https://www.google.com/search?q={quote_plus(query)}&hl=id&gl=ID"

cmd = [
    chrome_path,
    "--headless=new",
    "--disable-gpu",
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--window-size=1280,800",
    "--dump-dom",
    url
]

try:
    print("Running Chrome headless for query:", query)
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=12, text=True, encoding="utf-8", errors="ignore")
    html = res.stdout
    print("Chrome finished! HTML length:", len(html))
    soup = BeautifulSoup(html, "html.parser")
    
    results = []
    # Search for Google result blocks
    for g in soup.find_all("div", class_=["g", "MjjYud", "tF2Cxc"]):
        h3 = g.find("h3")
        a = g.find("a", href=True)
        # snippet
        snip = g.find("div", class_=["VwiC3b", "yXK7lf"])
        if h3 and a:
            href = a['href']
            if href.startswith("http") and "google.com" not in href:
                results.append({
                    "title": h3.get_text(strip=True),
                    "url": href,
                    "content": snip.get_text(strip=True) if snip else ""
                })
    
    # Also fallback to any h3 with parent a
    if not results:
        for h3 in soup.find_all("h3"):
            a = h3.find_parent("a", href=True) or h3.find("a", href=True)
            if a:
                href = a['href']
                if href.startswith("http") and "google.com" not in href:
                    results.append({
                        "title": h3.get_text(strip=True),
                        "url": href,
                        "content": ""
                    })

    print(f"Total Google Search Results Extracted: {len(results)}")
    for i, r in enumerate(results[:6], 1):
        print(f"#{i} {r['title']}")
        print(f"   URL: {r['url']}")
        print(f"   Snippet: {r['content'][:100]}")
        print()

except Exception as e:
    print("Chrome headless error:", e)
