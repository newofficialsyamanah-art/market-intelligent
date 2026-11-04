import urllib.request
from bs4 import BeautifulSoup
import re

url = "https://news.google.com/rss/search?q=turnamen+kejuaraan+futsal+lari+marathon+2026+2027+indonesia&hl=id&gl=ID&ceid=ID:id"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})

with urllib.request.urlopen(req, timeout=8) as resp:
    xml_data = resp.read()

import xml.etree.ElementTree as ET
root = ET.fromstring(xml_data)
items = root.findall(".//item")
print(f"Total sports items found: {len(items)}")
for i, it in enumerate(items[:5], 1):
    title = it.find("title").text if it.find("title") is not None else ""
    source = it.find("source").text if it.find("source") is not None else ""
    source_url = it.find("source").attrib.get("url", "") if it.find("source") is not None else ""
    link = it.find("link").text if it.find("link") is not None else ""
    desc_html = it.find("description").text if it.find("description") is not None else ""
    desc_soup = BeautifulSoup(desc_html, "html.parser")
    clean_desc = desc_soup.get_text(strip=True)
    
    print(f"#{i} {title}")
    print(f"   Source Publisher: {source} ({source_url})")
    print(f"   Description: {clean_desc}")
    print()
