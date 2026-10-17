import urllib.request, urllib.parse, json

app_token = '3014213105586689|b1MJ6Zu9EaS8oRDPr1gsLnwmP_g'
params = {
    'ad_reached_countries': "['ID']",
    'ad_type': 'ALL',
    'search_terms': 'supplier kain',
    'fields': 'id,page_id,page_name,ad_creative_bodies,ad_delivery_start_time',
    'limit': 3,
    'access_token': app_token
}
query_str = urllib.parse.urlencode(params)
url = f'https://graph.facebook.com/v19.0/ads_archive?{query_str}'

try:
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode('utf-8'))
        print('SUCCESS WITH APP TOKEN! Total:', len(data.get('data', [])))
        for d in data.get('data', []):
            print('-', d.get('page_name'))
except urllib.error.HTTPError as e:
    err = e.read().decode('utf-8')
    print(f'HTTP Error {e.code}:', err)
