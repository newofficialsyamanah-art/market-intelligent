import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + "/.."))

from app import create_app
from app.services.market_size_service import get_market_size_and_share

app = create_app()
with app.app_context():
    data = get_market_size_and_share()
    
    benchmarks = data.get("benchmarks", {})
    print("=== JERSEY BENCHMARK ===")
    for b in benchmarks.get("jersey", {}).get("top_sellers", []):
        print(f"Rank {b.get('rank')}: {b.get('shop_name')}")
        print(f"  Web: {b.get('store_url')}")
        print(f"  IG: {b.get('social_handle')} -> {b.get('social_url')}")
        print(f"  Marketplace: {b.get('marketplace_name')} -> {b.get('marketplace_url')}")

    print("\n=== JAKET BENCHMARK ===")
    for b in benchmarks.get("jaket", {}).get("top_sellers", []):
        print(f"Rank {b.get('rank')}: {b.get('shop_name')}")
        print(f"  Web: {b.get('store_url')}")
        print(f"  IG: {b.get('social_handle')} -> {b.get('social_url')}")
        print(f"  Marketplace: {b.get('marketplace_name')} -> {b.get('marketplace_url')}")

    print("\n=== SERAGAM BENCHMARK ===")
    for b in benchmarks.get("seragam", {}).get("top_sellers", []):
        print(f"Rank {b.get('rank')}: {b.get('shop_name')}")
        print(f"  Web: {b.get('store_url')}")
        print(f"  IG: {b.get('social_handle')} -> {b.get('social_url')}")
        print(f"  Marketplace: {b.get('marketplace_name')} -> {b.get('marketplace_url')}")

    print("\n=== NATIONAL TOP BRANDS ===")
    for b in benchmarks.get("national_top_brands", []):
        print(f"Rank {b.get('rank')}: {b.get('name')}")
        print(f"  Web: {b.get('web_url')}")
        print(f"  IG: {b.get('social_handle')} -> {b.get('social_url')}")
        print(f"  Marketplace: {b.get('marketplace_name')} -> {b.get('marketplace_url')}")


