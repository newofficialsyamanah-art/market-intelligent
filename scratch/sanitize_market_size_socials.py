import re

target_file = r"D:\market_intelligence\app\services\market_size_service.py"

with open(target_file, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update Syamanah accounts to verified @raffizsport
content = re.sub(r"'social_handle':\s*['\"]@syamanahjersey['\"]", "'social_handle': '@raffizsport'", content)
content = re.sub(r"'social_url':\s*['\"]https://www\.instagram\.com/syamanahjersey/['\"]", "'social_url': 'https://www.instagram.com/raffizsport/'", content)

content = re.sub(r"'social_handle':\s*['\"]@syamanahjacket['\"]", "'social_handle': '@raffizsport'", content)
content = re.sub(r"'social_url':\s*['\"]https://www\.instagram\.com/syamanahjacket/['\"]", "'social_url': 'https://www.instagram.com/raffizsport/'", content)

content = re.sub(r"'social_handle':\s*['\"]@syamanahseragam['\"]", "'social_handle': '@raffizsport'", content)
content = re.sub(r"'social_url':\s*['\"]https://www\.instagram\.com/syamanahseragam/['\"]", "'social_url': 'https://www.instagram.com/raffizsport/'", content)

# 2. Update Trisula to official verified account
content = re.sub(r"'social_handle':\s*['\"]@trisulacorporation['\"]", "'social_handle': '@trisulainternational'", content)
content = re.sub(r"'social_url':\s*['\"]https://www\.instagram\.com/trisulacorporation/['\"]", "'social_url': 'https://www.instagram.com/trisulainternational/'", content)

# 3. Update Boogie Apparel to official account
content = re.sub(r"'social_handle':\s*['\"]@boogie\.indonesia['\"]", "'social_handle': '@boogieapparel.co.id'", content)
content = re.sub(r"'social_url':\s*['\"]https://www\.instagram\.com/boogie\.indonesia/['\"]", "'social_url': 'https://www.instagram.com/boogieapparel.co.id/'", content)

# 4. Neutralize unverified / fake guesses to None (jangan ngarang!)
unverified_handles = [
    "@vendor.jersey",
    "@maestrojersey",
    "@jrsykeren.id",
    "@rumahkomunitas.id",
    "@customjersey.id",
    "@bikinjersey",
    "@indokonveksi.id",
    "@jogjakonveksii",
    "@totalsportsapparel",
    "@greengarment.id",
    "@pabrikseragam.co.id",
    "@konveksibandung_jaya",
    "@konveksibandung.id",
    "@hasangarment",
    "@spirit.konveksi",
    "@seragamkantor.id",
    "@konveksikaosku",
    "@pusatkonveksi",
    "@nvnkonveksi",
]

for h in unverified_handles:
    # replace social_handle
    content = re.sub(rf"'social_handle':\s*['\"]{re.escape(h)}['\"]", "'social_handle': None", content)

# Also neutralize corresponding social_url
unverified_urls = [
    "https://www.instagram.com/vendor.jersey/",
    "https://www.instagram.com/maestrojersey/",
    "https://www.instagram.com/jrsykeren.id/",
    "https://www.instagram.com/rumahkomunitas.id/",
    "https://www.instagram.com/customjersey.id/",
    "https://www.instagram.com/bikinjersey/",
    "https://www.instagram.com/indokonveksi.id/",
    "https://www.instagram.com/jogjakonveksii/",
    "https://www.instagram.com/totalsportsapparel/",
    "https://www.instagram.com/greengarment.id/",
    "https://www.instagram.com/pabrikseragam.co.id/",
    "https://www.instagram.com/konveksibandung_jaya/",
    "https://www.instagram.com/konveksibandung.id/",
    "https://www.instagram.com/hasangarment/",
    "https://www.instagram.com/spirit.konveksi/",
    "https://www.instagram.com/seragamkantor.id/",
    "https://www.instagram.com/konveksikaosku/",
    "https://www.instagram.com/pusatkonveksi/",
    "https://www.instagram.com/nvnkonveksi/",
]

for u in unverified_urls:
    content = re.sub(rf"'social_url':\s*['\"]{re.escape(u)}['\"]", "'social_url': None", content)

with open(target_file, "w", encoding="utf-8") as f:
    f.write(content)

print("Successfully sanitized social URLs in market_size_service.py!")
