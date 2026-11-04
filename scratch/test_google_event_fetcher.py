import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import json
from bs4 import BeautifulSoup
from typing import List, Dict, Any

def fetch_google_news_events(query: str, location: str = "", year: str = "2027", limit: int = 15) -> List[Dict[str, Any]]:
    """Mencari artikel & berita event aktual di Google News RSS seputar pameran, expo, dan turnamen olahraga."""
    terms = []
    if query:
        terms.append(query)
    else:
        terms.append("pameran expo konferensi industri turnamen olahraga")
    
    if location and location.lower() not in ["semua", "indonesia", ""]:
        terms.append(location)
    
    if year:
        terms.append(year)
    else:
        terms.append("2026 OR 2027")

    full_query = " ".join(terms)
    encoded_q = urllib.parse.quote(full_query)
    url = f"https://news.google.com/rss/search?q={encoded_q}&hl=id&gl=ID&ceid=ID:id"

    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    })

    results = []
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            xml_data = resp.read()
            root = ET.fromstring(xml_data)
            items = root.findall(".//item")
            for it in items[:limit]:
                title = it.find("title").text if it.find("title") is not None else ""
                source = it.find("source").text if it.find("source") is not None else ""
                source_domain = it.find("source").attrib.get("url", "") if it.find("source") is not None else ""
                link = it.find("link").text if it.find("link") is not None else ""
                pub_date = it.find("pubDate").text if it.find("pubDate") is not None else ""
                desc_html = it.find("description").text if it.find("description") is not None else ""
                
                soup = BeautifulSoup(desc_html, "html.parser")
                clean_desc = soup.get_text(strip=True)

                if title and link:
                    results.append({
                        "title": title,
                        "url": link,
                        "source_publisher": source,
                        "source_domain": source_domain,
                        "pub_date": pub_date,
                        "content": f"{title}. {clean_desc} (Diterbitkan oleh {source})"
                    })
    except Exception as e:
        print("Error fetching Google News:", e)
    return results

# Test with 2027 query
print("=== TESTING GOOGLE SEARCH UNTUK EVENT 2027 ===")
res2027 = fetch_google_news_events(query="pameran expo", location="Surabaya", year="2027", limit=5)
print(f"Total ditemukan untuk 2027 di Surabaya: {len(res2027)}")
for r in res2027:
    print(" - Title:", r["title"])
    print("   Publisher:", r["source_publisher"], f"({r['source_domain']})")
    print("   Date:", r["pub_date"])
    print()

print("=== TESTING GOOGLE SEARCH UNTUK TURNAMEN 2027 ===")
res_sport = fetch_google_news_events(query="turnamen futsal marathon", location="Bandung", year="2027", limit=5)
print(f"Total ditemukan untuk turnamen 2027 di Bandung: {len(res_sport)}")
for r in res_sport:
    print(" - Title:", r["title"])
    print("   Publisher:", r["source_publisher"])
    print("   Date:", r["pub_date"])
    print()
