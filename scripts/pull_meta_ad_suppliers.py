"""CLI Runner untuk menarik supplier dari Meta Ad Library API.

Penggunaan:
python scripts/pull_meta_ad_suppliers.py --token "EAA..." --query "supplier kain" --limit 20
"""

import sys
import os
import argparse

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app
from app.services.meta_ad_supplier_service import MetaAdSupplierService

def main():
    parser = argparse.ArgumentParser(description="Tarik data supplier aktif dari Meta Ad Library API.")
    parser.add_argument("--token", required=True, help="User Access Token Meta (diawali EAA...)")
    parser.add_argument("--query", default="supplier kain", help="Kata kunci pencarian iklan (misal: supplier kain, pabrik konveksi)")
    parser.add_argument("--limit", type=int, default=15, help="Jumlah maksimal iklan supplier yang ditarik")

    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        print("=" * 60)
        print("MENJALANKAN META AD LIBRARY SUPPLIER FETCHER")
        print(f"Query Target: '{args.query}' | Limit: {args.limit}")
        print("=" * 60)

        res = MetaAdSupplierService.fetch_supplier_ads(
            access_token=args.token,
            search_terms=args.query,
            limit=args.limit
        )

        if not res["success"]:
            print(f"\n[GAGAL] Meta API Response Status: {res.get('status_code')}")
            print(f"Error Message: {res.get('error')}")
            if res.get("error_user_msg"):
                print(f"Instruksi Meta: {res.get('error_user_msg')}")
            return

        ads_list = res.get("data", [])
        print(f"\n[SUKSES] Berhasil menarik {len(ads_list)} iklan supplier aktif!")

        ingest_res = MetaAdSupplierService.ingest_ads_to_suppliers(ads_list)
        if ingest_res.get("success"):
            print(f"- Supplier Baru Disimpan: {ingest_res['created']}")
            print(f"- Supplier Diperbarui: {ingest_res['updated']}")
            print("\nDaftar Supplier:")
            for s in ingest_res.get("suppliers", []):
                status_str = "BARU" if s["is_new"] else "UPDATE"
                print(f"  * [#{s['id']}] {s['name']} ({status_str})")
        else:
            print(f"Gagal menyimpan ke database: {ingest_res.get('error')}")

if __name__ == "__main__":
    main()
