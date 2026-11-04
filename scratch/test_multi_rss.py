import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from typing import List, Dict, Any

def fetch_google_event_snippets(query: str, location: str = "", year: str = "2026, 2027", limit: int = 30) -> List[Dict[str, Any]]:
    loc_clean = location.strip() if location and location.lower() not in ["semua", "indonesia"] else ""
    cat_clean = query.strip() or "pameran expo turnamen"
    
    # Generate search phrases
    year_str = year.strip() if year else "2026 OR 2027"
    
    sub_queries = [
        f"{cat_clean} {loc_clean} {year_str}",
        f"pameran expo {cat_clean} {loc_clean} {year_str}",
        f"turnamen kejuaraan kompetisi {cat_clean} {loc_clean} {year_str}",
        f"jadwal festival kalender event {cat_clean} {loc_clean} {year_str}"
    ]
    
    seen_links = set()
    snippets = []

    for q in sub_queries:
        encoded_q = urllib.parse.quote(q)
        url = f"https://news.google.com/rss/search?q={encoded_q}&hl=id&gl=ID&ceid=ID:id"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
        try:
            with urllib.request.urlopen(req, timeout=8) as resp:
                xml_data = resp.read()
                root = ET.fromstring(xml_data)
                for it in root.findall(".//item"):
                    title = it.find("title").text if it.find("title") is not None else ""
                    source = it.find("source").text if it.find("source") is not None else ""
                    source_url = it.find("source").attrib.get("url", "") if it.find("source") is not None else ""
                    link = it.find("link").text if it.find("link") is not None else ""
                    desc_html = it.find("description").text if it.find("description") is not None else ""
                    
                    if not title or not link or link in seen_links:
                        continue
                    seen_links.add(link)
                    
                    soup = BeautifulSoup(desc_html, "html.parser")
                    clean_desc = soup.get_text(strip=True)
                    
                    snippets.append({
                        "title": title,
                        "url": link,
                        "source_publisher": source,
                        "source_domain": source_url,
                        "content": f"Judul: {title}\nMedia: {source} ({source_url})\nRingkasan: {clean_desc}"
                    })
                    if len(snippets) >= limit:
                        break
        except Exception as e:
            print(f"Error querying Google News for '{q}': {e}")
        if len(snippets) >= limit:
            break

    return snippets

res = fetch_google_event_snippets("pameran tekstil dan olahraga", location="Jawa Timur", year="2026 OR 2027", limit=10)
print(f"Total snippets returned: {len(res)}")
for i, s in enumerate(res[:5], 1):
    print(f"#{i} {s['title']}")
    print(f"   Publisher: {s['source_publisher']}")
    print(f"   URL: {s['url'][:70]}...")
    print()
