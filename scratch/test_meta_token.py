import urllib.request
import urllib.parse
import json

fresh_token = 'EAAq1aS1vkgEBSq2yW73Gexy3bFD2SThY2LUzPK3bc7wfb8VZAcvtHUohgTWWNfJJUYpfZALUriPnFSyazvfhggUVRitxOrqqxM6yQ08VlXuWy7bNmkgJnLW6EkfqQwdbeDj4DvL7zuggV6ZCIwcCKtGsSiVHxRiqXfxSff7G1qM90jIYHPJ8gZCXAZCageebwRa7ZBAbSPASBOEa795NoRB3KeADJsh60BaViY8SuqS5LBqKyonAQAgR6jrXsNURebcJiwpZAJsZBZBHAK2EZB6rTx'

params = {
    'ad_reached_countries': "['ID']",
    'ad_type': 'ALL',
    'search_terms': 'supplier kain',
    'fields': 'id,page_id,page_name,ad_creative_bodies,ad_creative_link_captions,ad_creative_link_titles,publisher_platforms,ad_delivery_start_time',
    'limit': 5,
    'access_token': fresh_token
}

query_str = urllib.parse.urlencode(params)
url = f'https://graph.facebook.com/v19.0/ads_archive?{query_str}'

print("Menguji endpoint Meta Ad Library API dengan Fresh Token...")

try:
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode('utf-8'))
        print("\n=======================================================")
        print("🎉 BERHASIL BESAR! META AD LIBRARY API MERESPON SUKSES!")
        print("=======================================================")
        items = data.get('data', [])
        print(f"Total supplier aktif yang ditarik: {len(items)}\n")
        for i, item in enumerate(items, 1):
            print(f"--- Supplier #{i} ---")
            print(f"Nama Supplier / Page: {item.get('page_name')}")
            print(f"Page ID: {item.get('page_id')}")
            print(f"Ad ID: {item.get('id')}")
            print(f"Platforms: {item.get('publisher_platforms')}")
            bodies = item.get('ad_creative_bodies', [])
            if bodies:
                print(f"Teks Iklan: {bodies[0][:200]}...")
            link_titles = item.get('ad_creative_link_titles', [])
            if link_titles:
                print(f"Link Title: {link_titles[0]}")
            captions = item.get('ad_creative_link_captions', [])
            if captions:
                print(f"Link Caption: {captions[0]}")
            print()
except urllib.error.HTTPError as e:
    err_body = e.read().decode('utf-8')
    print(f"\nHTTP Error {e.code}:")
    try:
        err_json = json.loads(err_body)
        print(json.dumps(err_json, indent=2))
    except Exception:
        print(err_body)
except Exception as e:
    print(f"Exception: {e}")
