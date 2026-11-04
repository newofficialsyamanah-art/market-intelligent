import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET

query = "pameran expo 2026 2027 indonesia"
encoded_q = urllib.parse.quote(query)
url = f"https://news.google.com/rss/search?q={encoded_q}&hl=id&gl=ID&ceid=ID:id"

print("Testing Google News RSS:", url)
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})

try:
    with urllib.request.urlopen(req, timeout=8) as resp:
        xml_data = resp.read()
        print("Google RSS Status 200 OK! Data length:", len(xml_data))
        root = ET.fromstring(xml_data)
        items = root.findall(".//item")
        print(f"Total Google News items found: {len(items)}")
        for i, it in enumerate(items[:6], 1):
            title = it.find("title").text if it.find("title") is not None else ""
            link = it.find("link").text if it.find("link") is not None else ""
            pub_date = it.find("pubDate").text if it.find("pubDate") is not None else ""
            desc = it.find("description").text if it.find("description") is not None else ""
            print(f"#{i} {title}")
            print(f"   Date: {pub_date}")
            print(f"   Link: {link[:80]}...")
            print()
except Exception as e:
    print("Google RSS Error:", e)
