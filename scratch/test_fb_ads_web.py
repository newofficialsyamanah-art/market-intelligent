import urllib.request
import re
import json

url = 'https://www.facebook.com/ads/library/?active_status=all&ad_type=all&country=ID&q=supplier%20kain&search_type=keyword_unordered&media_type=all'
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7',
}
req = urllib.request.Request(url, headers=headers)
try:
    with urllib.request.urlopen(req) as resp:
        html = resp.read().decode('utf-8', errors='ignore')
        print(f"Status 200 OK! Panjang HTML: {len(html)} bytes")
        
        # Cari data JSON di dalam script tags
        # Facebook sering menaruh initial data di window.__additionalData or require or similar
        print("Mencari data supplier dari payload HTML...")
        for script in re.findall(r'<script[^>]*>(.*?)</script>', html, re.DOTALL):
            if 'ad_archive' in script or 'supplier' in script.lower():
                print("Ditemukan script dengan konteks ad_archive / supplier!")
                # Cari pola pageName
                names = re.findall(r'"pageName":"([^"]+)"', script)
                if names:
                    print("Page Names:", set(names))
                pages = re.findall(r'"page_name":"([^"]+)"', script)
                if pages:
                    print("Page Names 2:", set(pages))
except Exception as e:
    print(f"Error: {e}")
