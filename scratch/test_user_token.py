import urllib.request
import json

app_token = '3014213105586689|b1MJ6Zu9EaS8oRDPr1gsLnwmP_g'
old_token = 'EAAq1aS1vkgEBSq2yW73Gexy3bFD2SThY2LUzPK3bc7wfb8VZAcvtHUohgTWWNfJJUYpfZALUriPnFSyazvfhggUVRitxOrqqxM6yQ08VlXuWy7bNmkgJnLW6EkfqQwdbeDj4DvL7zuggV6ZCIwcCKtGsSiVHxRiqXfxSff7G1qM90jIYHPJ8gZCXAZCageebwRa7ZBAbSPASBOEa795NoRB3KeADJsh60BaViY8SuqS5LBqKyonAQAgR6jrXsNURebcJiwpZAJsZBZBHAK2EZB6rTx'

url = f'https://graph.facebook.com/debug_token?input_token={old_token}&access_token={app_token}'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
try:
    with urllib.request.urlopen(req) as resp:
        print(json.dumps(json.loads(resp.read().decode('utf-8')), indent=2))
except urllib.error.HTTPError as e:
    print(e.code, e.read().decode('utf-8'))
