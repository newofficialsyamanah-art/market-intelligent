import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + "/.."))

from app import create_app
from app.services.market_size_service import get_market_size_and_share

app = create_app()
with app.app_context():
    data = get_market_size_and_share()
    benchmarks = data.get('benchmarks', {})
    for cat in ['jersey', 'jaket', 'seragam']:
        print(f"=== {cat.upper()} MARKETPLACES ===")
        for item in benchmarks.get(cat, {}).get('top_sellers', []):
            if item.get('has_marketplace'):
                print(f"  Rank {item.get('rank')}: {item.get('shop_name')} -> {item.get('marketplace_name')} | {item.get('marketplace_url')}")
            else:
                print(f"  Rank {item.get('rank')}: {item.get('shop_name')} -> B2B Direct | {item.get('marketplace_url')}")
