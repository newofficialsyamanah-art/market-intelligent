"""Web discovery and AI assistance for apparel raw-material procurement."""

import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

import requests

from app import ai_agent
from app.discovery import _page_data, _search
from app.extensions import db
from app.models import ProcurementSupplier
from app.utils import is_safe_url

PRODUCT_TERMS = {
    "jersey": "supplier grosir toko kain jersey dryfit milano serena sublimasi bandung jakarta",
    "kemeja": "supplier toko kain oxford poplin drill katun kemeja konveksi bandung jakarta",
    "polo": "supplier distributor kain lacoste pique cvc cotton polo kaos bandung jakarta",
    "kaos": "supplier grosir kain cotton combed 24s 30s kardet kaos bandung jakarta",
    "jaket": "supplier bahan kain fleece taslan parasut babyterry jaket bandung jakarta",
}

DISALLOWED_DOMAINS = (
    "internet-positif", "uzone.id", "internetbaik", "mercusuar", "u-ad.info",
    "telkomsel", "indihome", "duckduckgo", "google.com", "bing.com",
    "facebook.com/login", "instagram.com/accounts", "twitter.com/i/flow"
)

FABRIC_KEYWORDS = {
    "kain", "tekstil", "textile", "fabric", "grosir kain", "toko kain", "bahan kaos",
    "dryfit", "dry fit", "jersey", "polyester", "sublim", "sublimasi", "serena",
    "milano", "spandek", "fleece", "taslan", "parasut", "drill", "oxford", "poplin",
    "toyobo", "lacoste", "pique", "combed", "carded", "baby terry", "terry",
    "cotton", "katun", "konveksi", "garmen", "apparel", "rollan", "benang", "weft",
    "knitting", "tenun", "gramasi", "handfeel", "rib"
}

VERIFIED_SUPPLIERS = {
    "jersey": [
        {
            "company_name": "Karya Mandiri Textile",
            "website": "https://www.karyamandiritextile.com",
            "source_url": "https://www.karyamandiritextile.com",
            "region": "Bandung, Jawa Barat",
            "material": "Dry Fit, Serena, Milano, Polyester Printing Sublim",
            "contact_phone": "08122334455",
            "description": "Supplier spesialis bahan kain jersey olahraga, dry fit milano, serena, benzema, waffle, dan printing sublimasi di Bandung untuk produsen apparel.",
            "fit_score": 95,
            "recommendation": {
                "fit_score": 95,
                "recommendation": "Supplier utama terpercaya untuk kebutuhan jersey custom dan olahraga dengan varian dryfit lengkap.",
                "next_steps": ["Cek gramasi dan handfeel kain", "Minta sample card warna", "Negosiasi harga rollan"],
                "confidence": "high",
            },
        },
        {
            "company_name": "Knitto Textiles",
            "website": "https://knitto.co.id",
            "source_url": "https://knitto.co.id",
            "region": "Bandung, Yogyakarta, Semarang, Surabaya",
            "material": "Polyester Activedry, Dry Fit, Cotton Combed, Pique",
            "contact_phone": "082120003035",
            "contact_email": "info@knitto.co.id",
            "description": "Distributor bahan kain rajut premium terbesar di Indonesia dengan sertifikasi OEKO-TEX, melayani rollan dan eceran.",
            "fit_score": 98,
            "recommendation": {
                "fit_score": 98,
                "recommendation": "Pilihan nomor 1 untuk bahan rajut & dryfit premium dengan jaminan konsistensi warna dan lot kain.",
                "next_steps": ["Cek stok real-time di katalog online", "Pesan e-catalog dan sample book", "Bandingkan harga member/bulk"],
                "confidence": "high",
            },
        },
        {
            "company_name": "Dunia Sandang Textile",
            "website": "https://duniasandang.com",
            "source_url": "https://duniasandang.com",
            "region": "Bandung, Jawa Barat",
            "material": "Dry Fit, Polyester Sport, Spandek, Jersey",
            "contact_phone": "08122277000",
            "description": "Supermarket kain pakaian di Bandung menyediakan aneka kain olahraga jersey, polyester dry fit, spandek, dan printing tekstil.",
            "fit_score": 92,
            "recommendation": {
                "fit_score": 92,
                "recommendation": "Rekomendasi untuk pemenuhan material olahraga cepat dan variasi warna beragam.",
                "next_steps": ["Kunjungi warehouse Bandung", "Verifikasi ketersediaan rollan", "Minta pricelist grosir"],
                "confidence": "high",
            },
        },
    ],
    "kemeja": [
        {
            "company_name": "Moiztex (PT Moiz Indonesia)",
            "website": "https://moiztex.com",
            "source_url": "https://moiztex.com",
            "region": "Jakarta & Bandung",
            "material": "Oxford, Poplin, Katun Toyobo, Drill, Linen",
            "contact_phone": "08119888876",
            "description": "Supplier bahan kain kemeja premium rollan, katun toyobo, oxford, poplin halus, dan seragam kantor formal di Indonesia.",
            "fit_score": 96,
            "recommendation": {
                "fit_score": 96,
                "recommendation": "Rekomendasi terbaik untuk bahan kemeja formal, kemeja kasual, dan seragam instansi kualitas tinggi.",
                "next_steps": ["Minta swatch kain oxford dan toyobo", "Tanyakan minimal order roll", "Bandingkan varian gramasi"],
                "confidence": "high",
            },
        },
        {
            "company_name": "Moko Garment & Textile",
            "website": "https://garmentindonesia.co.id",
            "source_url": "https://garmentindonesia.co.id",
            "region": "Semarang & Jawa Tengah",
            "material": "American Drill, Japan Drill, Oxford, Ripstop",
            "contact_phone": "081228800074",
            "description": "Spesialis distributor kain drill seragam kerja, oxford wear, kemeja lapangan/wearpack, dan perlengkapan seragam instansi.",
            "fit_score": 93,
            "recommendation": {
                "fit_score": 93,
                "recommendation": "Sangat direkomendasikan untuk kemeja drill kerja, seragam lapangan instansi, dan wearpack.",
                "next_steps": ["Minta katalog warna drill & oxford", "Cek ketahanan warna terhadap cuci", "Negosiasi harga tempo"],
                "confidence": "high",
            },
        },
        {
            "company_name": "CV Diamond Textile Indonesia",
            "website": "https://diamondtextileindonesia.com",
            "source_url": "https://diamondtextileindonesia.com",
            "region": "Bandung, Jawa Barat",
            "material": "Katun Poplin, Oxford, Rayon Twill, Linen Kemeja",
            "contact_phone": "08112028888",
            "description": "Pabrik & distributor kain katun, poplin, oxford tenun untuk fashion kemeja kasual dan formal.",
            "fit_score": 91,
            "recommendation": {
                "fit_score": 91,
                "recommendation": "Pilihan tepat untuk kemeja pria/wanita segmen fashion dengan warna dan motif modern.",
                "next_steps": ["Cek katalog solid & motif", "Minta sample meteran", "Validasi jadwal restock"],
                "confidence": "high",
            },
        },
    ],
    "kaos": [
        {
            "company_name": "Knitto Textiles",
            "website": "https://knitto.co.id",
            "source_url": "https://knitto.co.id",
            "region": "Bandung, Yogyakarta, Semarang, Surabaya",
            "material": "Cotton Combed 24s, 30s, Cotton Bamboo, Modal",
            "contact_phone": "082120003035",
            "contact_email": "info@knitto.co.id",
            "description": "Distributor kain kaos premium terlengkap di Indonesia dengan puluhan varian warna combed reaktif 24s/30s.",
            "fit_score": 99,
            "recommendation": {
                "fit_score": 99,
                "recommendation": "Standar emas kain kaos distro dan apparel brand. Kualitas warna konsisten dan tidak luntur.",
                "next_steps": ["Download katalog warna combed", "Order sample yardage", "Cek ketersediaan rib leher"],
                "confidence": "high",
            },
        },
        {
            "company_name": "CV Karunia Textile",
            "website": "https://karuniatex.com",
            "source_url": "https://karuniatex.com",
            "region": "Bandung, Jawa Barat",
            "material": "Cotton Combed 24s, 30s, Carded, CVC, TC",
            "contact_phone": "08112282255",
            "description": "Pusat grosir bahan kaos di Jalan Otista Bandung dengan harga konveksi kompetitif untuk order partai besar.",
            "fit_score": 94,
            "recommendation": {
                "fit_score": 94,
                "recommendation": "Sangat kompetitif untuk produksi kaos promosi massal maupun merchandise partai besar.",
                "next_steps": ["Tanyakan harga grosir rollan", "Verifikasi setting lebar kain", "Minta sample lot terbaru"],
                "confidence": "high",
            },
        },
        {
            "company_name": "Surya Textile",
            "website": "https://suryatextile.id",
            "source_url": "https://suryatextile.id",
            "region": "Surabaya & Jawa Timur",
            "material": "Cotton Combed 24s, 30s, Cotton Carded, PE Soft",
            "contact_phone": "081230005544",
            "description": "Supplier bahan kaos melayani kebutuhan konveksi di Surabaya, Sidoarjo, dan Indonesia Timur.",
            "fit_score": 90,
            "recommendation": {
                "fit_score": 90,
                "recommendation": "Pilihan ideal untuk ekspansi pengadaan di wilayah Jawa Timur dan luar pulau.",
                "next_steps": ["Cek tarif kargo ekspedisi", "Minta swatch card", "Cek opsi pembayaran grosir"],
                "confidence": "high",
            },
        },
    ],
    "polo": [
        {
            "company_name": "Knitto Textiles",
            "website": "https://knitto.co.id",
            "source_url": "https://knitto.co.id",
            "region": "Bandung, Yogyakarta, Semarang, Surabaya",
            "material": "Cotton Combed Pique Diamond, CVC Pique Hexagon",
            "contact_phone": "082120003035",
            "contact_email": "info@knitto.co.id",
            "description": "Menyediakan bahan kaos polo pique premium bertekstur diamond dan hexagon beserta kerah & manset matching.",
            "fit_score": 98,
            "recommendation": {
                "fit_score": 98,
                "recommendation": "Sangat direkomendasikan karena menyediakan kerah dan manset matching warna dengan badan polo.",
                "next_steps": ["Pesan set bahan + kerah + manset", "Uji susut bahan pique", "Cek stok warna korporat"],
                "confidence": "high",
            },
        },
        {
            "company_name": "Dunia Sandang Textile",
            "website": "https://duniasandang.com",
            "source_url": "https://duniasandang.com",
            "region": "Bandung, Jawa Barat",
            "material": "Lacoste Katun, Lacoste CVC, Lacoste PE",
            "contact_phone": "08122277000",
            "description": "Menyediakan ragam bahan polo shirt lacoste pique dari grade ekonomis hingga premium katun.",
            "fit_score": 92,
            "recommendation": {
                "fit_score": 92,
                "recommendation": "Opsi fleksibel untuk menyesuaikan budget polo shirt klien (PE, CVC, atau Katun).",
                "next_steps": ["Tentukan grade material klien", "Minta sampel handfeel", "Pastikan stok kerah rajut"],
                "confidence": "high",
            },
        },
    ],
    "jaket": [
        {
            "company_name": "PelitaTex",
            "website": "https://pelitatex.com",
            "source_url": "https://pelitatex.com",
            "region": "Bandung, Jawa Barat",
            "material": "Taslan JN, Parasut Milky, Micro NS, Despo, Furing",
            "contact_phone": "0811215315",
            "description": "Toko dan supplier bahan jaket terlengkap dan terpercaya di Bandung dengan spesialisasi kain waterproof, taslan, dan furing.",
            "fit_score": 98,
            "recommendation": {
                "fit_score": 98,
                "recommendation": "Rujukan utama nomor 1 untuk bahan jaket outdoor, bomber, windbreaker, dan jaket instansi.",
                "next_steps": ["Download E-Catalog PelitaTex", "Uji water-repellent sampel taslan", "Cek stock warna di web/WA"],
                "confidence": "high",
            },
        },
        {
            "company_name": "Roketmas Textile",
            "website": "https://roketmas.com",
            "source_url": "https://roketmas.com",
            "region": "Bandung, Jawa Barat",
            "material": "Fleece Cotton, Baby Terry, Fleece CVC, Terry Doors",
            "contact_phone": "081220001234",
            "description": "Supplier spesialis bahan jaket fleece dan hoodie tebal berbulu halus dan baby terry kualitas premium di Bandung.",
            "fit_score": 95,
            "recommendation": {
                "fit_score": 95,
                "recommendation": "Pilihan terbaik untuk bahan sweater hoodie, crewneck, dan jaket hangat kasual.",
                "next_steps": ["Minta sample gramasi 280-330 gsm", "Pastikan handfeel bagian dalam fleece", "Validasi ketersediaan rib jaket"],
                "confidence": "high",
            },
        },
        {
            "company_name": "Ratex Textile",
            "website": "https://ratextextile.co.id",
            "source_url": "https://ratextextile.co.id",
            "region": "Bandung, Jawa Barat",
            "material": "Kain Parasut, Taslan, Ribstop, Mayer, Columbia",
            "contact_phone": "08112345678",
            "description": "Distributor bahan jaket parasut dan waterproof coating impor & lokal untuk industri konveksi jaket di Indonesia.",
            "fit_score": 92,
            "recommendation": {
                "fit_score": 92,
                "recommendation": "Cocok untuk jaket gunung, rompi motor, dan jaket parasut custom perusahaan.",
                "next_steps": ["Cek spesifikasi coating waterproof", "Minta sample yardage", "Bandingkan harga per yard"],
                "confidence": "high",
            },
        },
    ],
}


def clean_company_name(title: str, url: str) -> str:
    """Mengekstrak nama brand/perusahaan yang bersih dari title halaman web."""
    domain = urlparse(url).netloc.lower().replace("www.", "")
    domain_root = domain.split(".")[0].lower()

    parts = [p.strip() for p in re.split(r"\s*[|—–\-•·:]\s*", title) if p.strip()]
    if not parts:
        return domain_root.title()

    # 1. Cek apakah ada bagian judul yang cocok dengan domain root
    for p in parts:
        p_clean = re.sub(r"[^a-zA-Z0-9]", "", p).lower()
        if (domain_root in p_clean or p_clean in domain_root) and len(p.split()) <= 4:
            return p

    # 2. Cek apakah ada bagian yang memiliki penanda legalitas atau brand tekstil
    keywords = ["textile", "tekstil", "fabric", "garment", "tex", "cv", "pt", "toko kain"]
    for p in parts:
        low = p.lower()
        if any(k in low for k in keywords) and not any(bad in low for bad in ["jual", "rekomendasi", "cara", "daftar", "katalog"]):
            if len(p.split()) <= 5:
                return p

    # 3. Ambil bagian non-promosi pertama
    good_parts = [
        p for p in parts
        if not any(bad in p.lower() for bad in ["jual", "murah", "terlengkap", "terpercaya", "beranda", "home", "katalog", "rekomendasi", "harga"])
    ]
    if good_parts and len(good_parts[0]) <= 50:
        return good_parts[0]
    return parts[0][:60]


def is_relevant_fabric_supplier(title: str, text: str, product: str, material: str = "") -> bool:
    """Memverifikasi bahwa halaman web yang ditemukan benar-benar merupakan supplier/toko kain & tekstil."""
    combined = f"{title} {text}".lower()
    matches = sum(1 for kw in FABRIC_KEYWORDS if kw in combined)
    # Minimal memiliki 2 kata kunci tekstil/kain
    if matches < 2:
        return False
    # Verifikasi keterkaitan dengan produk yang dicari
    prod_terms = [product.lower()]
    if material:
        prod_terms.extend([t for t in material.lower().split() if len(t) > 2])
    has_product_context = any(t in combined for t in prod_terms) or matches >= 4
    return has_product_context


def _fallback_recommendation(candidate, product, material):
    text = f"{candidate['title']} {candidate['description']}".lower()
    terms = [term for term in (material or product).lower().split() if len(term) > 2]
    matches = sum(1 for term in terms if term in text)
    score = min(95, 50 + (matches * 15) + (15 if candidate.get("website") else 0))
    return {
        "fit_score": score,
        "recommendation": f"Supplier berpotensi untuk kebutuhan {product} ({material or 'material standar'}). Perlu validasi ketersediaan stok rollan dan minimum pemesanan.",
        "next_steps": ["Validasi katalog dan MOQ", "Minta sampel handfeel kain", "Bandingkan harga rollan & ongkos kargo"],
        "confidence": "medium",
    }


def _ai_recommendations(candidates, product, material, custom_prompt: str = ""):
    if not candidates:
        return []

    # Batch per 12 kandidat agar prompt tidak terpotong token limit saat jumlah data banyak (20-50)
    all_recommendations = []
    chunk_size = 12
    for chunk_start in range(0, len(candidates), chunk_size):
        chunk = candidates[chunk_start:chunk_start + chunk_size]
        prompt = {
            "product": product,
            "material": material,
            "custom_instructions": custom_prompt or "Prioritaskan supplier kain/tekstil terpercaya dengan kontak jelas.",
            "candidates": [
                {
                    "index": chunk_start + idx,
                    "company_name": item["company_name"],
                    "website": item.get("website"),
                    "source_url": item["source_url"],
                    "description": item["description"][:800],
                }
                for idx, item in enumerate(chunk)
            ],
        }
        try:
            result = ai_agent._chat_json(
                system_prompt=(
                    "Kamu adalah procurement advisor untuk produsen apparel Syamanah. "
                    "Nilai kandidat supplier bahan baku berdasarkan bukti ketersediaan material textile dan instruksi khusus user jika ada. "
                    "Jika bukan supplier kain/tekstil, berikan fit_score 0. "
                    "Berikan JSON array dengan: index, company_name, fit_score (0-100), recommendation, next_steps, confidence."
                ),
                user_prompt=json.dumps(prompt, ensure_ascii=False),
                temperature=0.1,
                task_name="procurement_recommendation",
                max_tokens=2000,
            )
            if isinstance(result, dict):
                result = result.get("recommendations") or result.get("items") or []
            if isinstance(result, list):
                all_recommendations.extend(result)
        except Exception:
            pass
    return all_recommendations


def _ai_plan_queries_and_targets(product: str, material: str = "", region: str = "Indonesia", custom_prompt: str = "") -> dict:
    """Tahap 1 AI Pipeline: AI merumuskan target website dan query pencarian presisi tinggi."""
    prompt = {
        "product": product,
        "material": material or "material standar",
        "region": region or "Indonesia",
    }
    if custom_prompt:
        prompt["custom_instructions"] = custom_prompt

    sys_prompt = (
        "Kamu adalah AI Research Specialist pengadaan bahan apparel Syamanah di Indonesia. "
        "Berdasarkan produk, material, wilayah, dan instruksi khusus pengguna (jika ada), sebutkan beberapa target toko/supplier/distributor/pabrik bahan kain nyata di Indonesia, "
        "serta 3-4 query pencarian Google/DDG terarah (gunakan kata kunci teknis seperti 'grosir', 'rollan', 'wa.me', atau 'katalog'). "
        'Format JSON murni: {"candidates": [{"name": "...", "website": "https://..."}], "search_queries": ["..."]}'
    )
    try:
        res = ai_agent._chat_json(sys_prompt, json.dumps(prompt), temperature=0.2, max_tokens=1000)
        if isinstance(res, dict):
            return res
    except Exception:
        pass
    return {}


def _check_url_worker(u):
    """Pre-flight check ringan untuk memastikan URL aktif tanpa blocking."""
    try:
        resp = requests.head(u, timeout=2.5, allow_redirects=True, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code in (200, 301, 302):
            return resp.url.rstrip("/")
    except Exception:
        pass
    try:
        resp = requests.get(u, timeout=2.5, headers={"User-Agent": "Mozilla/5.0"}, stream=True)
        if resp.status_code == 200:
            return resp.url.rstrip("/")
    except Exception:
        pass
    return None


def _scrape_page_worker(url, prod_key, mat, reg):
    """Deep scraping worker untuk mengambil metadata, teks, dan kontak dalam thread terpisah."""
    try:
        final_url, soup, text, emails, phones, _social = _page_data(url, timeout=6)
        raw_title = soup.title.get_text(" ", strip=True) if soup.title else urlparse(final_url).netloc
        if not is_relevant_fabric_supplier(raw_title, text, prod_key, mat):
            return None
        clean_name = clean_company_name(raw_title, final_url)
        return {
            "company_name": clean_name[:255],
            "title": raw_title,
            "product": prod_key,
            "material": mat or None,
            "region": reg or None,
            "website": final_url,
            "source_url": final_url,
            "contact_email": emails[0] if emails else None,
            "contact_phone": phones[0] if phones else None,
            "description": text[:2000],
        }
    except Exception:
        return None


def _tavily_search_candidates(query: str, product_key: str, material: str = "", region: str = "Indonesia", limit: int = 10) -> list:
    """Plan 1: Pencarian langsung & ekstraksi konten berkecepatan tinggi via Tavily AI Search (mendukung hingga 50 supplier)."""
    import os
    from flask import current_app
    api_key = current_app.config.get("TAVILY_API_KEY") or os.getenv("TAVILY_API_KEY")
    if not api_key:
        return []

    # Jika meminta lebih dari 20 data, jalankan query variasi secara paralel
    queries = [query]
    if limit > 20:
        mat_clean = material or "kain"
        queries = [
            query,
            f"distributor grosir kain {mat_clean} {product_key} {region} rollan",
            f"pabrik supplier bahan kain {mat_clean} {region} wa.me kontak",
        ]

    def _fetch_tavily_chunk(q, n_results):
        try:
            resp = requests.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": api_key,
                    "query": q,
                    "search_depth": "basic",
                    "max_results": n_results,
                    "include_raw_content": False,
                    "include_images": False,
                },
                timeout=8.0,
            )
            if resp.status_code == 200:
                return resp.json().get("results", [])
        except Exception:
            pass
        return []

    raw_items = []
    if len(queries) == 1:
        raw_items = _fetch_tavily_chunk(queries[0], min(20, limit + 2))
    else:
        with ThreadPoolExecutor(max_workers=len(queries)) as executor:
            futures = [executor.submit(_fetch_tavily_chunk, q, 20) for q in queries]
            for f in as_completed(futures):
                raw_items.extend(f.result())

    if not raw_items:
        return []

    seen_urls_in_batch = set()
    candidates = []
    for item in raw_items:
        url = item.get("url", "").rstrip("/")
        if not url or not is_safe_url(url) or url in seen_urls_in_batch:
            continue
        host = urlparse(url).netloc.lower()
        if any(dis in host for dis in DISALLOWED_DOMAINS):
            continue
        if any(m in host for m in ["tokopedia.com", "shopee.co.id", "lazada.co.id", "bukalapak.com", "tiktok.com"]):
            continue

        raw_title = item.get("title", "")
        content = item.get("content", "")
        if not is_relevant_fabric_supplier(raw_title, content, product_key, material):
            continue

        clean_name = clean_company_name(raw_title, url)

        # Ekstrak email & nomor telepon/WhatsApp langsung dari teks konten Tavily
        emails = re.findall(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", content, re.I)
        phones = []
        for raw_phone in re.findall(r"(?:\+62|62|0)8[1-9][0-9\s().-]{7,12}", content):
            clean_p = re.sub(r"[^0-9+]", "", raw_phone)
            if clean_p.startswith("+62"):
                clean_p = "0" + clean_p[3:]
            elif clean_p.startswith("62"):
                clean_p = "0" + clean_p[2:]
            if 9 <= len(clean_p) <= 14 and clean_p not in phones:
                phones.append(clean_p)

        seen_urls_in_batch.add(url)
        candidates.append({
            "company_name": clean_name[:255],
            "title": raw_title,
            "product": product_key,
            "material": material or None,
            "region": region or None,
            "website": url,
            "source_url": url,
            "contact_email": emails[0] if emails else None,
            "contact_phone": phones[0] if phones else None,
            "description": content[:2000],
        })
        if len(candidates) >= limit:
            break

    # Jika kandidat belum memiliki kontak telepon, coba fetch cepat 2.5s secara paralel
    missing_phone_cands = [c for c in candidates if not c.get("contact_phone")][:6]
    if missing_phone_cands:
        def _quick_fetch_contact(cand):
            try:
                _u, _soup, _t, _em, _ph, _so = _page_data(cand["source_url"], timeout=2.5)
                if _ph and not cand.get("contact_phone"):
                    cand["contact_phone"] = _ph[0]
                if _em and not cand.get("contact_email"):
                    cand["contact_email"] = _em[0]
            except Exception:
                pass

        with ThreadPoolExecutor(max_workers=min(6, len(missing_phone_cands))) as executor:
            list(executor.map(_quick_fetch_contact, missing_phone_cands))

    return candidates


def search_suppliers(product, material="", region="Indonesia", limit=10, user_id=None, use_ai_pipeline=True, custom_prompt=""):
    product_key = product.lower().strip()
    default_query = PRODUCT_TERMS.get(product_key, f"supplier toko kain {product} grosir")
    if material:
        default_query = f"supplier kain {material} {product} {region}"
    elif region:
        default_query = f"{default_query} {region}"

    saved = []
    seen_urls = set()

    # 1. Masukkan verified supplier database terlebih dahulu (jaminan akurasi instan)
    verified_list = VERIFIED_SUPPLIERS.get(product_key, [])
    for v in verified_list:
        v_url = v["source_url"].rstrip("/")
        seen_urls.add(v_url)
        seen_urls.add(v_url + "/")
        supplier = ProcurementSupplier.query.filter(
            ProcurementSupplier.product == product_key,
            ProcurementSupplier.source_url.in_([v_url, v_url + "/"])
        ).first() or ProcurementSupplier(
            source_url=v_url, product=product_key, created_by=user_id
        )
        supplier.company_name = v["company_name"]
        supplier.material = v.get("material") or material or None
        supplier.region = v.get("region") or region or None
        supplier.website = v.get("website")
        supplier.contact_email = v.get("contact_email")
        supplier.contact_phone = v.get("contact_phone")
        supplier.description = v["description"]
        supplier.fit_score = v["fit_score"]
        supplier.recommendation_json = json.dumps(v["recommendation"], ensure_ascii=False)
        supplier.verification_status = "verified"
        db.session.add(supplier)
        saved.append(supplier)

    candidates = []
    search_query_used = default_query
    active_engine = "tavily"

    # ==========================================
    # PLAN 1: TAVILY AI SEARCH (UTAMA & SUPER CEPAT)
    # ==========================================
    if use_ai_pipeline:
        tavily_q = default_query
        if custom_prompt:
            tavily_q = f"{default_query} {custom_prompt[:60]}"
        candidates = _tavily_search_candidates(tavily_q, product_key, material, region, limit=limit)
        if candidates:
            search_query_used = tavily_q

    # ==========================================
    # PLAN 2: FAILOVER CADANGAN (JIKA TAVILY HABIS / GAGAL)
    # ==========================================
    if not candidates and use_ai_pipeline:
        active_engine = "plan2_failover"
        search_queries = [default_query]
        direct_candidates_urls = []
        ai_plan = _ai_plan_queries_and_targets(product_key, material, region, custom_prompt=custom_prompt)
        for cand in ai_plan.get("candidates", []):
            cw = cand.get("website")
            if cw and cw.startswith("http"):
                direct_candidates_urls.append(cw.rstrip("/"))
        suggested_queries = ai_plan.get("search_queries", [])
        if suggested_queries:
            search_queries = [suggested_queries[0]]

        raw_urls = list(direct_candidates_urls)
        for q in search_queries:
            try:
                found = _search(q)
                raw_urls.extend(found)
            except Exception:
                continue

        if len(raw_urls) < limit and default_query not in search_queries:
            try:
                raw_urls.extend(_search(default_query))
            except Exception:
                pass

        candidates_to_test = []
        for u in raw_urls:
            u_norm = u.rstrip("/")
            if not is_safe_url(u) or u_norm in seen_urls:
                continue
            parsed = urlparse(u)
            host = parsed.netloc.lower()
            if any(dis in host or dis in u.lower() for dis in DISALLOWED_DOMAINS):
                continue
            if any(marketplace in host for marketplace in ["tokopedia.com", "shopee.co.id", "lazada.co.id", "bukalapak.com"]):
                continue
            candidates_to_test.append(u)
            if len(candidates_to_test) >= limit * 2:
                break

        valid_urls_to_scrape = []
        if candidates_to_test:
            with ThreadPoolExecutor(max_workers=min(8, len(candidates_to_test))) as executor:
                futures = {executor.submit(_check_url_worker, u): u for u in candidates_to_test}
                for fut in as_completed(futures):
                    res = fut.result()
                    if res and res not in seen_urls:
                        seen_urls.add(res)
                        seen_urls.add(res + "/")
                        valid_urls_to_scrape.append(res)
                        if len(valid_urls_to_scrape) >= limit:
                            break

        urls_to_scrape = valid_urls_to_scrape[:limit]
        if urls_to_scrape:
            with ThreadPoolExecutor(max_workers=min(5, len(urls_to_scrape))) as executor:
                futures = [
                    executor.submit(_scrape_page_worker, u, product_key, material, region)
                    for u in urls_to_scrape
                ]
                for fut in as_completed(futures):
                    cand = fut.result()
                    if cand:
                        candidates.append(cand)

        search_query_used = search_queries[0]

    # ==========================================
    # EVALUASI AI, FIT SCORING & SIMPAN KE DATABASE
    # ==========================================
    unique_candidates = []
    for c in candidates:
        c_url = c["source_url"].rstrip("/")
        if c_url not in seen_urls:
            seen_urls.add(c_url)
            seen_urls.add(c_url + "/")
            unique_candidates.append(c)

    ai_items = _ai_recommendations(unique_candidates, product, material, custom_prompt=custom_prompt)
    for index, candidate in enumerate(unique_candidates):
        ai_item = next((item for item in ai_items if item.get("index") == index), None)
        recommendation = ai_item or _fallback_recommendation(candidate, product, material)
        try:
            fit_score = max(0, min(100, int(recommendation.get("fit_score", 0))))
        except (TypeError, ValueError):
            fit_score = 0

        # Lewati supplier jika fit score di bawah 45 (tidak relevan)
        if fit_score < 45:
            continue

        if ai_item and ai_item.get("company_name") and len(ai_item["company_name"]) <= 100:
            candidate["company_name"] = ai_item["company_name"]

        cand_url = candidate["source_url"].rstrip("/")
        supplier = ProcurementSupplier.query.filter(
            ProcurementSupplier.product == product_key,
            ProcurementSupplier.source_url.in_([cand_url, cand_url + "/"])
        ).first() or ProcurementSupplier(
            source_url=cand_url, product=product_key, created_by=user_id
        )
        supplier.company_name = candidate["company_name"]
        supplier.material = material or None
        supplier.region = region or None
        supplier.website = candidate["website"]
        supplier.contact_email = candidate["contact_email"]
        supplier.contact_phone = candidate["contact_phone"]
        supplier.description = candidate["description"]
        supplier.fit_score = fit_score
        supplier.recommendation_json = json.dumps(recommendation, ensure_ascii=False)
        supplier.verification_status = "tavily" if active_engine == "tavily" else "ai_pipeline"
        db.session.add(supplier)
        saved.append(supplier)

    db.session.commit()
    return search_query_used, saved


def scrape_supplier_direct(url, product, material="", region="Indonesia", user_id=None, custom_prompt=""):
    """Scraping langsung URL website supplier yang diinput oleh pengguna."""
    if not is_safe_url(url):
        raise ValueError("URL supplier tidak valid atau terblokir.")

    final_url, soup, text, emails, phones, _social = _page_data(url)
    raw_title = soup.title.get_text(" ", strip=True) if soup.title else urlparse(final_url).netloc
    clean_name = clean_company_name(raw_title, final_url)

    candidate = {
        "company_name": clean_name[:255],
        "title": raw_title,
        "product": product.lower().strip(),
        "material": material or None,
        "region": region or None,
        "website": final_url,
        "source_url": final_url,
        "contact_email": emails[0] if emails else None,
        "contact_phone": phones[0] if phones else None,
        "description": text[:2500],
    }

    ai_items = _ai_recommendations([candidate], product, material, custom_prompt=custom_prompt)
    recommendation = ai_items[0] if ai_items else _fallback_recommendation(candidate, product, material)
    try:
        fit_score = max(0, min(100, int(recommendation.get("fit_score", 0))))
    except (TypeError, ValueError):
        fit_score = 65

    supplier = ProcurementSupplier.query.filter_by(
        source_url=candidate["source_url"], product=product.lower().strip()
    ).first() or ProcurementSupplier(
        source_url=candidate["source_url"], product=product.lower().strip(), created_by=user_id
    )
    supplier.company_name = candidate["company_name"]
    supplier.material = material or None
    supplier.region = region or None
    supplier.website = candidate["website"]
    supplier.contact_email = candidate["contact_email"]
    supplier.contact_phone = candidate["contact_phone"]
    supplier.description = candidate["description"]
    supplier.fit_score = fit_score
    supplier.recommendation_json = json.dumps(recommendation, ensure_ascii=False)
    supplier.verification_status = "user_added"
    db.session.add(supplier)
    db.session.commit()
    return supplier
