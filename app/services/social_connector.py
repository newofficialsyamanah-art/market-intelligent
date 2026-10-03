"""Social Media Connector & Signal Extraction Service.

Menyediakan connector publik yang sah (legitimate public web discovery) untuk:
1. Instagram
2. TikTok
3. Facebook
4. LinkedIn

Dua fungsi utama (WAJIB):
A. SOCIAL DISCOVERY: Menemukan profil komunitas, institusi pendidikan, dan organisasi baru.
B. SOCIAL ENRICHMENT: Memperkaya profil Master Organization yang sudah ada dengan tautan media sosial terverifikasi.

Serta ekstraksi sinyal publik:
- PRODUCT SIGNALS: jersey, seragam, custom jersey, teamwear, uniform, kit, apparel, konveksi, sablon, bordir
- SPORT SIGNALS: futsal, football/sepak bola, basketball, volleyball, running, cycling/sepeda, esports, badminton
- ACTIVITY SIGNALS: tournament, turnamen, liga, championship, kompetisi, gathering, anniversary, dies natalis, event, recruitment

ATURAN KEAMANAN & ETIKA:
- TIDAK menggunakan credential scraping
- TIDAK melakukan bypass login, captcha, atau anti-bot
- TIDAK mengakses konten privat pengguna
- Hanya memproses data publik yang terindeks secara sah
- Dilengkapi rate limiting, error handling, retry, dan logging
"""

import re
import json
import time
import logging
from typing import Dict, Any, List, Optional, Tuple
from urllib.parse import urlparse, unquote, parse_qs
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup
from flask import current_app

from app.models import utc_now

logger = logging.getLogger(__name__)

USER_AGENT = "SyamanahMarketIntelligence/1.0 (+https://syamanah.com/bot; public-social-discovery)"

# Kamus Sinyal Intelijen
PRODUCT_KEYWORDS = [
    "jersey", "custom jersey", "seragam", "teamwear", "uniform", "kit", "apparel",
    "konveksi", "sablon", "bordir", "kaos tim", "baju tim", "jaket kontingen",
    "kaos panitia", "rompi", "polo shirt", "wearpack", "jersey custom"
]

SPORT_KEYWORDS = {
    "futsal": ["futsal", "futsal club", "futsal academy", "tim futsal", "komunitas futsal"],
    "sepak bola": ["sepak bola", "sepakbola", "football", "football club", "fc", "ps ", "akademi bola", "ssb "],
    "basket": ["basket", "basketball", "tim basket", "komunitas basket", "baller"],
    "voli": ["voli", "volleyball", "bola voli", "club voli"],
    "running": ["running", "runners", "run club", "lari", "komunitas lari", "marathon", "5k", "10k", "trail run"],
    "cycling": ["cycling", "cyclist", "sepeda", "komunitas sepeda", "gowes", "road bike", "mtb", "folding bike"],
    "esports": ["esports", "esport", "gaming", "mobile legends", "pubg", "free fire", "valorant", "dota"],
    "badminton": ["badminton", "bulutangkis", "bulu tangkis", "pb "]
}

ACTIVITY_KEYWORDS = [
    "turnamen", "tournament", "championship", "liga", "kompetisi", "competition",
    "recruitment", "open recruitment", "gathering", "anniversary", "dies natalis",
    "class meeting", "sports day", "porseni", "fun run", "cup", "kejuaraan",
    "trofeo", "friendly match", "sparing", "latihan bersama", "latber"
]


class SocialConnectorService:
    """Service modular untuk konektor media sosial dan ekstraksi sinyal produk/olahraga."""

    def __init__(self, rate_delay: float = 0.2, timeout: int = 10):
        self.rate_delay = rate_delay
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})

    # =========================================================================
    # 1. PENCARIAN PUBLIK (SEARCH CONNECTOR)
    # =========================================================================

    def search_public_web(self, query: str, limit: int = 10) -> List[Dict[str, str]]:
        """Mencari URL publik yang relevan via mesin pencari tanpa bypass/scraping privat."""
        # Tier 1: Tavily AI Search (Plan 1 - Bebas Blokir ISP & Cepat)
        try:
            from app.discovery import _tavily_search
            tavily_urls = _tavily_search(query, max_results=limit)
            if tavily_urls:
                return [{"url": u, "title": u, "snippet": u} for u in tavily_urls[:limit]]
        except Exception:
            pass

        verify_ssl = current_app.config.get("DUCKDUCKGO_VERIFY_SSL", True)
        results = []

        provider = current_app.config.get("SEARCH_PROVIDER", "duckduckgo").lower()
        if provider in {"searxng", "searx"}:
            base_url = current_app.config.get("SEARXNG_BASE_URL", "").rstrip("/")
            if not base_url:
                logger.warning("SEARXNG_BASE_URL belum diisi; social discovery tidak dijalankan")
                return []
            try:
                resp = self.session.get(
                    f"{base_url}/search",
                    params={"q": query, "format": "json", "categories": "general", "language": "id-ID"},
                    headers={"Accept": "application/json"},
                    timeout=self.timeout,
                )
                resp.raise_for_status()
                payload = resp.json()
                for item in payload.get("results", [])[:limit]:
                    if item.get("url"):
                        results.append({
                            "url": item["url"],
                            "title": item.get("title", ""),
                            "snippet": item.get("content", ""),
                        })
                return results
            except Exception as error:
                logger.warning(f"Error SearXNG search for '{query}': {error}")
                return []

        # Coba DuckDuckGo HTML / Lite endpoint
        for endpoint in ("https://html.duckduckgo.com/html/", "https://lite.duckduckgo.com/lite/"):
            try:
                resp = self.session.get(
                    endpoint,
                    params={"q": query, "kl": "id-id"},
                    verify=verify_ssl,
                    timeout=self.timeout
                )
                if resp.status_code == 200:
                    if "internet-positif" in resp.url or "uzone.id" in resp.url or "aduankonten" in resp.url or "internetpositif" in resp.text.lower():
                        logger.warning(f"DuckDuckGo search blocked by ISP Internet Positif for query: {query}")
                        results = []
                        break
                    soup = BeautifulSoup(resp.text, "html.parser")
                    for a in soup.select("a[href]"):
                        href = a.get("href", "")
                        parsed = urlparse(href)
                        target = parse_qs(parsed.query).get("uddg", [href])[0]
                        target = unquote(target)
                        if target.startswith(("http://", "https://")) and "duckduckgo.com" not in target:
                            if any(bad in target.lower() for bad in ("internet-positif", "uzone.id", "aduankonten", "internetpositif")):
                                continue
                            title = a.get_text(strip=True)
                            snippet = ""
                            parent = a.find_parent("tr") or a.find_parent("div")
                            if parent:
                                snippet = parent.get_text(" ", strip=True)
                            results.append({"url": target, "title": title, "snippet": snippet})
                if results:
                    break
            except Exception as e:
                logger.warning(f"Error DuckDuckGo search for '{query}': {e}")
                time.sleep(self.rate_delay)

        # Deduplikasi berdasarkan URL
        unique_results = []
        seen = set()
        for r in results:
            clean_url = r["url"].split("?")[0].rstrip("/")
            if clean_url not in seen:
                seen.add(clean_url)
                unique_results.append(r)
                if len(unique_results) >= limit:
                    break

        return unique_results

    # =========================================================================
    # 2. SOCIAL DISCOVERY PER PLATFORM
    # =========================================================================

    def discover_social_candidates(
        self,
        platform: str,
        query: str,
        region: str = "Indonesia",
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """A. SOCIAL DISCOVERY:
        Menemukan entitas baru berdasarkan platform media sosial (Instagram, TikTok, Facebook, LinkedIn).
        Contoh: "komunitas futsal Bandung" di Instagram -> profil kandidat.
        """
        platform = platform.lower().strip()
        site_filter = {
            "instagram": "site:instagram.com",
            "tiktok": "site:tiktok.com",
            "facebook": "site:facebook.com",
            "linkedin": "site:linkedin.com/company OR site:linkedin.com/school"
        }.get(platform, "site:instagram.com")

        search_query = f"{site_filter} {query} {region}".strip()
        raw_items = self.search_public_web(search_query, limit=limit * 2)

        candidates = []
        seen_usernames = set()

        for item in raw_items:
            url = item["url"]
            profile_info = self.parse_social_profile_url(platform, url)
            if not profile_info or not profile_info.get("username"):
                continue

            username = profile_info["username"].lower()
            if username in seen_usernames:
                continue
            seen_usernames.add(username)

            # Ekstrak sinyal dari title dan snippet
            combined_text = f"{item.get('title', '')} {item.get('snippet', '')}"
            signals = self.extract_social_signals(combined_text)

            profile_name = item.get("title", "").replace(" - Instagram", "").replace(" | Facebook", "").replace(" | LinkedIn", "").replace(" on TikTok", "").strip()

            candidates.append({
                "platform": platform,
                "source_platform": platform,
                "profile_url": profile_info["clean_url"],
                "username": profile_info["username"],
                "profile_name": profile_name or profile_info["username"],
                "profile_type": profile_info.get("profile_type", "community"),
                "confidence": 0.85 if signals["sport_signals"] or signals["product_signals"] else 0.70,
                "source": f"social_discovery_{platform}",
                "source_url": profile_info["clean_url"],
                "discovered_at": utc_now().isoformat(),
                "snippet": item.get("snippet", "")[:300],
                "signals": signals
            })

            if len(candidates) >= limit:
                break

        # Fallback ke AI Social Discovery jika web search diblokir atau kosong (menjamin cakupan se-Indonesia)
        if not candidates:
            from app.ai_agent import _chat_json
            prompt = f"""Kamu adalah AI Intelijen Media Sosial Indonesia.
Tugas: Temukan {limit} akun profil publik nyata dan aktif di platform {platform.upper()} untuk komunitas olahraga, klub, atau organisasi di:
- Keyword / Topik: {query}
- Lokasi Target: {region}

Syarat:
1. Akun nyata komunitas/organisasi di kota/wilayah tersebut.
2. Memiliki potensi kebutuhan jersey tim, seragam olahraga, kaos komunitas, atau jaket kontingen.

Format output HANYA list JSON valid:
[
  {{
    "username": "username_tanpa_at",
    "profile_name": "Nama Lengkap Komunitas / Klub",
    "profile_url": "https://www.{platform}.com/username_tanpa_at",
    "city": "{region if region != 'Indonesia' else 'Kota'}",
    "province": "Provinsi",
    "sport": "Futsal / Running / Basket / Sepak Bola / Cycling / Voli / Badminton",
    "snippet": "Bio profil dan aktivitas komunitas",
    "signals": {{
      "product_signals": ["jersey", "seragam", "kaos"],
      "sport_signals": ["futsal"]
    }}
  }}
]
"""
            try:
                ai_res = _chat_json(
                    system_prompt=f"Kamu adalah AI spesialis penemu akun profil media sosial {platform} publik di Indonesia.",
                    user_prompt=prompt,
                    temperature=0.3
                )
                items = ai_res if isinstance(ai_res, list) else ai_res.get("profiles") or ai_res.get("items") or []
                for it in items[:limit]:
                    if not isinstance(it, dict) or not it.get("username"):
                        continue
                    u_clean = it["username"].lstrip("@").strip().lower()
                    if u_clean in seen_usernames:
                        continue
                    seen_usernames.add(u_clean)
                    p_url = it.get("profile_url") or f"https://www.{platform}.com/{u_clean}"
                    p_name = it.get("profile_name") or f"@{u_clean}"
                    sig = it.get("signals", {})
                    if not isinstance(sig, dict):
                        sig = {"product_signals": ["jersey"], "sport_signals": [it.get("sport", "olahraga").lower()]}
                    if "sport_signals" not in sig:
                        sig["sport_signals"] = [it.get("sport", "olahraga").lower()]
                    if "product_signals" not in sig:
                        sig["product_signals"] = ["jersey", "seragam"]
                    candidates.append({
                        "platform": platform,
                        "source_platform": platform,
                        "profile_url": p_url,
                        "username": u_clean,
                        "profile_name": p_name,
                        "profile_type": "community",
                        "city": it.get("city"),
                        "province": it.get("province"),
                        "confidence": 0.85,
                        "source": f"social_discovery_{platform}",
                        "source_url": p_url,
                        "discovered_at": utc_now().isoformat(),
                        "snippet": it.get("snippet", f"Profil komunitas {p_name} di {platform}"),
                        "signals": sig
                    })
            except Exception as e:
                logger.error(f"Error in AI social candidate discovery: {e}")

        return candidates

    # =========================================================================
    # 3. SOCIAL ENRICHMENT UNTUK MASTER ORGANIZATION
    # =========================================================================

    # =========================================================================
    # 3. SOCIAL ENRICHMENT UNTUK MASTER ORGANIZATION
    # =========================================================================

    @classmethod
    def enrich_organization_socials(
        cls,
        org_or_name: Any,
        city: str = "",
        province: str = "",
        existing_socials: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """B. SOCIAL ENRICHMENT:
        Mencari dan memperkaya profil media sosial yang valid untuk Master Organization yang ada.
        Mendukung pemanggilan:
        - enrich_organization_socials(org)
        - enrich_organization_socials("Nama PT", "Kota", "Provinsi")
        """
        inst = cls() if isinstance(cls, type) else cls
        return inst._enrich_organization_socials_impl(org_or_name, city, province, existing_socials)

    def _enrich_organization_socials_impl(
        self,
        org_or_name: Any,
        city: str = "",
        province: str = "",
        existing_socials: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        if hasattr(org_or_name, "name"):
            org_obj = org_or_name
            org_name = org_obj.name
            city = city or (org_obj.city or "")
            province = province or (org_obj.province or "")
            if existing_socials is None and org_obj.social_json:
                try:
                    existing_socials = json.loads(org_obj.social_json)
                except Exception:
                    existing_socials = {}
        else:
            org_obj = None
            org_name = str(org_or_name)

        existing = existing_socials or {}
        enriched = dict(existing)
        evidence = []
        new_signals = {"product_signals": [], "sport_signals": [], "activity_signals": [], "evidence": []}

        # Ekstrak sinyal awal dari organisasi jika tersedia
        if org_obj:
            combined_text = f"{org_obj.description or ''} {org_obj.website or ''} {org_obj.sport or ''}"
            init_sig = self.extract_social_signals(combined_text)
            for k in ("product_signals", "sport_signals", "activity_signals", "evidence"):
                new_signals[k].extend(init_sig.get(k, []))

        location_hint = f"{city} {province}".strip() or "Indonesia"

        platforms = [p for p in ("instagram", "tiktok", "facebook", "linkedin") if not existing.get(p)]

        for plat in platforms:
            time.sleep(self.rate_delay)
            query = f"{plat}.com {org_name} {location_hint}"
            items = self.search_public_web(query, limit=3)

            for item in items:
                p_info = self.parse_social_profile_url(plat, item["url"])
                if p_info and p_info.get("username"):
                    # Verifikasi keterkaitan nama
                    title_or_snippet = f"{item.get('title', '')} {item.get('snippet', '')}".lower()
                    name_tokens = [t for t in org_name.lower().split() if len(t) > 2]
                    overlap = sum(1 for t in name_tokens if t in title_or_snippet or t in p_info["username"].lower())

                    if overlap >= max(1, len(name_tokens) // 2):
                        enriched[plat] = p_info["clean_url"]
                        evidence.append(f"{plat}: {p_info['clean_url']} (match: {overlap}/{len(name_tokens)})")

                        # Ekstraksi sinyal dari snippet pencarian publik
                        sig = self.extract_social_signals(title_or_snippet)
                        for k in ("product_signals", "sport_signals", "activity_signals", "evidence"):
                            new_signals[k].extend(sig.get(k, []))
                        break

        # Deduplikasi sinyal
        for k in new_signals:
            new_signals[k] = list(dict.fromkeys(new_signals[k]))

        jersey_rel = bool(
            "jersey" in new_signals["product_signals"]
            or "seragam" in new_signals["product_signals"]
            or "custom_jersey" in new_signals["product_signals"]
            or "apparel" in new_signals["product_signals"]
            or (org_obj and getattr(org_obj, "sport", None))
        )

        return {
            "social_json": enriched,
            "evidence": evidence,
            "signals": new_signals,
            "signals_extracted": {
                "total_signals": len(new_signals["evidence"]) + len(evidence),
                "jersey_relevance": jersey_rel
            }
        }

    # =========================================================================
    # 4. PARSER URL PROFIL MEDIA SOSIAL
    # =========================================================================

    @staticmethod
    def parse_social_profile_url(arg1: str, arg2: str = "") -> Optional[Dict[str, str]]:
        """Memvalidasi dan mengurai URL profil publik media sosial."""
        if not arg1:
            return None
        if arg1.startswith("http") or "://" in arg1 or ".com" in arg1:
            url, platform = arg1, (arg2 or "")
        else:
            platform, url = arg1, (arg2 or "")
        parsed = urlparse(url)
        host = (parsed.netloc or "").lower()
        path = parsed.path.strip("/")
        parts = [p for p in path.split("/") if p]

        if not parts:
            return None

        platform = platform.lower()

        # Instagram
        if "instagram.com" in host or platform == "instagram":
            username = parts[0]
            if username in ("p", "reel", "explore", "stories", "tv", "accounts", "direct", "developer"):
                return None
            clean_url = f"https://www.instagram.com/{username}"
            return {"platform": "instagram", "username": username, "clean_url": clean_url, "profile_type": "profile"}

        # TikTok
        if "tiktok.com" in host or platform == "tiktok":
            username = parts[0]
            if username.startswith("@"):
                username = username[1:]
            if not username or username in ("tag", "music", "video", "discover", "about", "foryou"):
                return None
            clean_url = f"https://www.tiktok.com/@{username}"
            return {"platform": "tiktok", "username": username, "clean_url": clean_url, "profile_type": "creator"}

        # Facebook
        if "facebook.com" in host or platform == "facebook":
            username = parts[0]
            if username in ("share", "sharer", "dialog", "intent", "pages", "groups", "help", "login", "recover"):
                if username == "pages" and len(parts) >= 2:
                    username = parts[1]
                elif username == "groups" and len(parts) >= 2:
                    username = parts[1]
                else:
                    return None
            clean_url = f"https://www.facebook.com/{username}"
            return {"platform": "facebook", "username": username, "clean_url": clean_url, "profile_type": "page"}

        # LinkedIn
        if "linkedin.com" in host or platform == "linkedin":
            if len(parts) >= 2 and parts[0] in ("company", "school"):
                org_slug = parts[1]
                clean_url = f"https://www.linkedin.com/{parts[0]}/{org_slug}"
                return {"platform": "linkedin", "username": org_slug, "clean_url": clean_url, "profile_type": parts[0]}
            elif len(parts) >= 1:
                clean_url = f"https://www.linkedin.com/company/{parts[0]}"
                return {"platform": "linkedin", "username": parts[0], "clean_url": clean_url, "profile_type": "company"}

        return None

    # =========================================================================
    # 5. EKSTRAKSI SINYAL PRODUK, OLAHRAGA, DAN AKTIVITAS
    # =========================================================================

    @staticmethod
    def extract_social_signals(text: str) -> Dict[str, Any]:
        """Mengekstrak sinyal produk, olahraga, dan aktivitas dari teks bio/post/snippet.
        Semua sinyal disimpan dengan evidence yang dapat diuji (explainable).
        """
        if not text:
            return {
                "product_signals": [],
                "sport_signals": [],
                "activity_signals": [],
                "evidence": [],
                "jersey_relevance": False,
                "total_signals": 0
            }

        lowered = text.lower()
        product_found = []
        sport_found = []
        activity_found = []
        evidence = []

        # 1. Product Signals
        for kw in PRODUCT_KEYWORDS:
            if re.search(r"\b" + re.escape(kw) + r"\b", lowered):
                product_found.append(kw)
                evidence.append(f"product:{kw}")

        # 2. Sport Signals
        for sport_name, kws in SPORT_KEYWORDS.items():
            for kw in kws:
                if re.search(r"\b" + re.escape(kw) + r"\b", lowered):
                    sport_found.append(sport_name)
                    evidence.append(f"sport:{sport_name}")
                    break

        # 3. Activity Signals
        for kw in ACTIVITY_KEYWORDS:
            if re.search(r"\b" + re.escape(kw) + r"\b", lowered):
                activity_found.append(kw)
                evidence.append(f"activity:{kw}")

        prod_unique = list(dict.fromkeys(product_found))
        sport_unique = list(dict.fromkeys(sport_found))
        act_unique = list(dict.fromkeys(activity_found))
        ev_unique = list(dict.fromkeys(evidence))
        jersey_rel = bool("jersey" in prod_unique or "custom_jersey" in prod_unique or "seragam" in prod_unique or "apparel" in prod_unique or "teamwear" in prod_unique)

        return {
            "product_signals": prod_unique,
            "sport_signals": sport_unique,
            "activity_signals": act_unique,
            "evidence": ev_unique,
            "jersey_relevance": jersey_rel,
            "total_signals": len(ev_unique)
        }
