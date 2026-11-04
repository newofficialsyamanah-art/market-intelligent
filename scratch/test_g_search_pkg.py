from googlesearch import search

query = "jadwal pameran expo 2026 2027 indonesia"
print("Searching Google with googlesearch-python for:", query)

try:
    results = list(search(query, num_results=10, advanced=True, lang="id"))
    print("Found count:", len(results))
    for r in results:
        print(" - Title:", r.title)
        print("   URL:", r.url)
        print("   Description:", r.description[:100])
        print()
except Exception as e:
    print("Error:", e)
