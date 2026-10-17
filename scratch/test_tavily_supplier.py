import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.discovery import parallel_tavily_search_snippets

queries = [
    'supplier bahan kain katun combed bandung grosir "08"',
    'distributor kain tekstil murah jakarta surabaya "wa.me"',
    'pabrik konveksi maklon seragam b2b "whatsapp"'
]

snippets = parallel_tavily_search_snippets(queries, max_per_query=5)
print(f"Total snippets supplier ditemukan: {len(snippets)}\n")
for i, s in enumerate(snippets[:6], 1):
    print(f"{i}. Judul: {s.get('title')}")
    print(f"   URL: {s.get('url')}")
    print(f"   Snippet: {(s.get('content') or '')[:160]}...")
    print("-" * 50)
