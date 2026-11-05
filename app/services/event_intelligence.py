"""Event Intelligence Service (Phase 5).

Menyediakan engine modular untuk penemuan, validasi, deduplikasi, skoring relevansi,
dan relasi partisipan (organizer, exhibitor, sponsor, partner, speaker) ke Master Organizations.
"""

import re
import json
import logging
from datetime import datetime, timezone, date
from urllib.parse import urlparse
from typing import Dict, Any, List, Optional, Tuple

from app.discovery import parallel_tavily_search_snippets, _search
from app.extensions import db
from app.models import Event, EventParticipant, Organization, DuplicateCandidate, utc_now
from app.services.dedup_engine import (
    normalize_company_name,
    extract_domain,
    DIRECTORY_AND_AGGREGATOR_DOMAINS,
    PUBLIC_EMAIL_DOMAINS,
)

from app.services.mcp_service import (
    mcp_search_duckduckgo,
    mcp_search_social_events,
    mcp_scrape_url,
)

logger = logging.getLogger(__name__)

# Kamus Relevansi untuk B2B Apparel / Uniform / Merchandise Opportunity
HIGH_RELEVANCE_KEYWORDS = [
    "textile", "tekstil", "garment", "garmen", "apparel", "pakaian", "fashion", "busana",
    "seragam", "uniform", "merchandise", "convection", "konveksi", "sablon", "bordir",
    "indo intertex", "inatex", "inacraft", "jakarta fashion week", "jfw", "trade expo indonesia",
    "procurement", "pengadaan", "corporate apparel", "workwear", "safety wear"
]

MEDIUM_RELEVANCE_KEYWORDS = [
    "manufacturing", "manufaktur", "industrial", "industri", "expo", "pameran", "b2b",
    "leather", "alas kaki", "footwear", "giias", "otomotif", "automotive", "mining",
    "pertambangan", "oil", "gas", "konstruksi", "construction", "packaging", "kemasan",
    "hospitality", "hotel", "f&b", "kuliner", "food & beverage", "career expo", "job fair",
    "campus expo", "university fair"
]

LOW_RELEVANCE_KEYWORDS = [
    "property", "properti", "wedding", "pernikahan", "baby", "anak", "pet", "hewan",
    "beauty", "kecantikan", "art", "seni", "book", "buku", "education", "pendidikan"
]

REJECT_KEYWORDS = [
    "spam", "judi", "slot", "togel", "casino", "porn", "dating", "crypto giveaway"
]

NEWS_AND_MEDIA_DOMAINS = {
    "google.com", "news.google.com", "tavily.com", "bing.com", "yahoo.com", "duckduckgo.com",
    "kompas.com", "detik.com", "antaranews.com", "tempo.co", "liputan6.com", "tribunnews.com",
    "sindonews.com", "kumparan.com", "republika.co.id", "rm.id", "rri.co.id", "jawapos.com",
    "bisnis.com", "kontan.co.id", "suara.com", "merdeka.com", "viva.co.id", "inews.id",
    "idntimes.com", "beritasatu.com", "cnbcindonesia.com", "katadata.co.id", "okezone.com",
    "mediaindonesia.com", "jpnn.com", "idxchannel.com", "metrotvnews.com", "swa.co.id",
    "beritakota.id", "voiceofasean.com", "indotelko.com", "elshinta.com", "kemenpar.go.id"
}


def normalize_event_name(name: str) -> str:
    """Menormalisasi nama event untuk perbandingan deduplikasi."""
    if not name:
        return ""
    text = name.lower()
    text = re.sub(r"\b(the|indonesia|jakarta|international|annual|annualy|ke-\d+|\d{4})\b", " ", text)
    text = re.sub(r"[^\w\s]", " ", text)
    tokens = [t.strip() for t in text.split() if len(t.strip()) > 1]
    return " ".join(tokens)


def parse_extracted_date(date_raw: Any, default_year: Optional[int] = None) -> Tuple[Optional[datetime], str]:
    """Mengubah string tanggal/tahun menjadi tuple (datetime, precision):
    - ('exact', datetime): Jika hari, bulan, dan tahun terdefinisi pasti (contoh: 15-18 Agustus 2027)
    - ('month', datetime): Jika hanya bulan dan tahun (tanggal tbd)
    - ('tentative', None): Jika HANYA tahun tanpa bulan/hari (TIDAK MEMAKSAKAN 1 JANUARI!)
    """
    if not date_raw:
        return None, "tentative"
    if isinstance(date_raw, datetime):
        return date_raw, "exact"
    if isinstance(date_raw, date):
        return datetime(date_raw.year, date_raw.month, date_raw.day), "exact"

    val_str = str(date_raw).strip()
    val_low = val_str.lower()

    # 1. Cek format ISO (YYYY-MM-DD)
    iso_match = re.search(r'(\d{4})-(\d{2})-(\d{2})', val_str)
    if iso_match:
        try:
            return datetime(int(iso_match.group(1)), int(iso_match.group(2)), int(iso_match.group(3))), "exact"
        except Exception:
            pass

    months = {
        "januari": 1, "jan": 1, "februari": 2, "feb": 2, "maret": 3, "mar": 3,
        "april": 4, "apr": 4, "mei": 5, "may": 5, "juni": 6, "jun": 6,
        "juli": 7, "jul": 7, "agustus": 8, "agt": 8, "aug": 8, "september": 9, "sep": 9,
        "oktober": 10, "okt": 10, "oct": 10, "november": 11, "nov": 11, "desember": 12, "des": 12, "dec": 12
    }

    year_match = re.search(r'\b(202\d)\b', val_low)
    yr = int(year_match.group(1)) if year_match else default_year

    found_mo = None
    for m_name, m_num in months.items():
        if re.search(r'\b' + m_name + r'\b', val_low):
            found_mo = m_num
            break

    no_yr = re.sub(r'\b202\d\b', ' ', val_low)
    day_match = re.search(r'\b([0-2]?\d|3[01])\b', no_yr)
    found_dy = int(day_match.group(1)) if day_match and int(day_match.group(1)) > 0 else None

    if yr:
        if found_mo and found_dy:
            try:
                return datetime(yr, found_mo, min(found_dy, 28)), "exact"
            except Exception:
                return datetime(yr, found_mo, 1), "month"
        elif found_mo:
            return datetime(yr, found_mo, 1), "month"
        else:
            # HANYA TAHUN -> TENTATIF! TIDAK PERNAH DIJADIKAN 1 JANUARI PALSU!
            return None, "tentative"

    return None, "unknown"


def extract_deep_event_metadata(url: str, timeout: int = 4) -> Dict[str, Any]:
    """Mengunjungi halaman web resmi/berita asli untuk mengekstrak Schema.org JSON-LD dan paragraf utuh."""
    import json
    import requests
    from bs4 import BeautifulSoup

    result = {
        "final_url": url,
        "name": None,
        "start_date": None,
        "end_date": None,
        "venue": None,
        "city": None,
        "organizer": None,
        "page_text": "",
        "date_precision": "unknown"
    }

    if not url or not url.startswith("http"):
        return result

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        resp = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        if resp.status_code != 200:
            return result

        result["final_url"] = resp.url
        soup = BeautifulSoup(resp.text, "html.parser")

        # 1. Ekstrak Schema.org JSON-LD Event
        for s in soup.find_all("script", type="application/ld+json"):
            try:
                raw_json = s.string
                if not raw_json:
                    continue
                data = json.loads(raw_json)
                items = data.get("@graph", [data]) if isinstance(data, dict) else (data if isinstance(data, list) else [])
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    item_type = str(item.get("@type", "")).lower()
                    if "event" in item_type or item_type in ["exhibitionevent", "businessevent", "sports_event", "socialevent"]:
                        if item.get("name") and not result["name"]:
                            result["name"] = item["name"]
                        if item.get("startDate") and not result["start_date"]:
                            result["start_date"] = item["startDate"]
                            result["date_precision"] = "exact"
                        if item.get("endDate") and not result["end_date"]:
                            result["end_date"] = item["endDate"]
                        
                        loc = item.get("location")
                        if isinstance(loc, dict):
                            result["venue"] = loc.get("name")
                            addr = loc.get("address")
                            if isinstance(addr, dict):
                                result["city"] = addr.get("addressLocality")
                            elif isinstance(addr, str):
                                result["city"] = addr
                        elif isinstance(loc, str):
                            result["venue"] = loc
                        
                        org = item.get("organizer")
                        if isinstance(org, dict):
                            result["organizer"] = org.get("name")
                        elif isinstance(org, str):
                            result["organizer"] = org
                        break
            except Exception:
                continue

        # 2. Ekstrak teks paragraf untuk AI reading
        for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
            tag.decompose()
        
        paragraphs = [p.get_text(strip=True) for p in soup.find_all(["p", "h1", "h2", "h3", "li"]) if len(p.get_text(strip=True)) > 25]
        full_text = " ".join(paragraphs[:20])
        result["page_text"] = full_text[:2000]

    except Exception:
        pass

    return result


def fetch_google_news_events(
    query: str = "",
    location: str = "",
    year: str = "2026, 2027",
    limit: int = 30
) -> List[Dict[str, Any]]:
    """Mencari artikel & berita event aktual di Google News RSS seputar pameran, expo, dan turnamen olahraga."""
    import urllib.request
    import urllib.parse
    import xml.etree.ElementTree as ET
    from bs4 import BeautifulSoup

    loc_clean = (location or "").strip() if location and location.lower() not in ["semua", "indonesia"] else ""
    cat_clean = (query or "").strip() or "pameran expo bisnis industri"
    year_str = (year or "").strip() or "2026 OR 2027"

    # Ekstrak token tahun
    year_tokens = [y.strip() for y in re.findall(r'\b(202\d)\b', year_str)]
    if not year_tokens:
        year_tokens = ["2026", "2027"]

    sub_queries = []
    for yr in year_tokens:
        sub_queries.extend([
            f"{cat_clean} {loc_clean} {yr}".strip(),
            f"pameran expo {cat_clean} {loc_clean} {yr}".strip(),
            f"agenda jadwal festival {cat_clean} {loc_clean} {yr}".strip(),
            f"turnamen kejuaraan {cat_clean} {loc_clean} {yr}".strip()
        ])
    if not loc_clean or "jakarta" in loc_clean.lower():
        for yr in year_tokens:
            sub_queries.extend([
                f"pameran jiexpo {yr}",
                f"pameran jcc {yr}",
                f"event ice bsd {yr}"
            ])

    seen_links = set()
    snippets = []

    for q in sub_queries:
        encoded_q = urllib.parse.quote(q)
        url = f"https://news.google.com/rss/search?q={encoded_q}&hl=id&gl=ID&ceid=ID:id"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        )
        try:
            with urllib.request.urlopen(req, timeout=8) as resp:
                xml_data = resp.read()
                root = ET.fromstring(xml_data)
                for it in root.findall(".//item"):
                    title = it.find("title").text if it.find("title") is not None else ""
                    source = it.find("source").text if it.find("source") is not None else ""
                    source_url = it.find("source").attrib.get("url", "") if it.find("source") is not None else ""
                    link = it.find("link").text if it.find("link") is not None else ""
                    pub_date = it.find("pubDate").text if it.find("pubDate") is not None else ""
                    desc_html = it.find("description").text if it.find("description") is not None else ""

                    if not title or not link or link in seen_links:
                        continue
                    seen_links.add(link)

                    soup = BeautifulSoup(desc_html, "html.parser")
                    clean_desc = soup.get_text(strip=True)

                    snippets.append({
                        "title": title,
                        "url": link,
                        "source_publisher": source,
                        "source_domain": source_url,
                        "pub_date": pub_date,
                        "content": f"Judul: {title}\nMedia: {source} ({source_url})\nTanggal Terbit: {pub_date}\nRingkasan: {clean_desc}"
                    })
                    if len(snippets) >= limit:
                        break
        except Exception as e:
            logger.warning(f"Google News RSS query failed for '{q}': {e}")
        if len(snippets) >= limit:
            break

    return snippets


def fetch_google_custom_search_events(
    query: str = "",
    location: str = "",
    year: str = "2026, 2027",
    limit: int = 15
) -> List[Dict[str, Any]]:
    """Mencari event via Google Custom Search JSON API jika API key & Engine ID terkonfigurasi."""
    import os
    import urllib.request
    import urllib.parse
    import json

    api_key = os.environ.get("GOOGLE_SEARCH_API_KEY")
    cx = os.environ.get("GOOGLE_SEARCH_ENGINE_ID")
    if not api_key or not cx:
        return []

    loc_clean = (location or "").strip() if location and location.lower() not in ["semua", "indonesia"] else ""
    cat_clean = (query or "").strip() or "pameran expo turnamen"
    q_str = f"{cat_clean} {loc_clean} {year or ''}".strip()

    url = f"https://www.googleapis.com/customsearch/v1?key={api_key}&cx={cx}&q={urllib.parse.quote(q_str)}&num={min(limit, 10)}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            items = data.get("items", [])
            results = []
            for it in items:
                link = it.get("link", "")
                if link and link.startswith("http"):
                    results.append({
                        "title": it.get("title", ""),
                        "url": link,
                        "source_publisher": it.get("displayLink", ""),
                        "source_domain": f"https://{it.get('displayLink', '')}",
                        "pub_date": "",
                        "content": f"Judul: {it.get('title')}\nSumber: {it.get('displayLink')}\nCuplikan: {it.get('snippet', '')}"
                    })
            return results
    except Exception as e:
        logger.info(f"Google Custom Search API skipped/unavailable: {e}")
        return []



class EventIntelligenceService:
    """Service modular untuk Event Intelligence (Phase 5)."""

    @staticmethod
    def calculate_relevance(name: str, event_type: str = "", description: str = "", organizer: str = "") -> Tuple[str, int, str]:
        """Menghitung klasifikasi relevansi (HIGH, MEDIUM, LOW, REJECT) dan score 0-100
        terhadap potensi kebutuhan seragam, apparel kerja, dan merchandise B2B.
        """
        combined = f"{name} {event_type} {description} {organizer}".lower()

        # 1. Cek Reject (Spam / Invalid)
        for bad in REJECT_KEYWORDS:
            if bad in combined:
                return "REJECT", 0, f"Terdeteksi kata terlarang/spam: '{bad}'"

        # 2. Cek High Relevance
        high_matches = [k for k in HIGH_RELEVANCE_KEYWORDS if k in combined]
        if high_matches:
            score = min(80 + len(high_matches) * 5, 100)
            return "HIGH", score, f"Relevansi Tinggi: Terkait industri apparel/tekstil/pengadaan ({', '.join(high_matches[:3])})"

        # 3. Cek Medium Relevance
        med_matches = [k for k in MEDIUM_RELEVANCE_KEYWORDS if k in combined]
        if med_matches:
            score = min(50 + len(med_matches) * 5, 79)
            return "MEDIUM", score, f"Relevansi Menengah: Event industri/B2B/kampus dengan peluang seragam ({', '.join(med_matches[:3])})"

        # 4. Cek Low Relevance
        low_matches = [k for k in LOW_RELEVANCE_KEYWORDS if k in combined]
        if low_matches:
            return "LOW", 35, f"Relevansi Rendah: Event umum/konsumen ({', '.join(low_matches[:2])})"

        return "LOW", 30, "Relevansi Rendah: Informasi tidak spesifik apparel/B2B"

    @classmethod
    def deduplicate_event(cls, event_data: Dict[str, Any]) -> Tuple[Optional[Event], str, float]:
        """Mengecek apakah event sudah ada di database menggunakan multi-signal matching:
        - Tier 1a: Exact Source URL match (mencegah partial domain match pada portal berita)
        - Tier 1b: Dedicated Official Event Website domain match (non-media, non-aggregator)
        - Tier 2: Normalized name + Year match (membedakan event tahunan misal 2026 vs 2027)
        - Tier 3: Normalized name + Date / Venue / City
        Mengembalikan (event, match_tier, confidence) atau (None, "none", 0.0)
        """
        source_url = (event_data.get("source_url") or "").strip()
        website = (event_data.get("website") or "").strip()
        name = (event_data.get("name") or "").strip()
        start_date = event_data.get("start_date")
        city = (event_data.get("city") or "").strip()
        venue = (event_data.get("venue") or "").strip()
        organizer = (event_data.get("organizer") or "").strip()

        # 1. Tier 1a: Exact Canonical Source URL (bukan partial domain!)
        if source_url:
            clean_src = source_url.split("?")[0].rstrip("/")
            existing = Event.query.filter(
                db.or_(
                    Event.source_url == source_url,
                    Event.source_url.like(f"{clean_src}%")
                )
            ).first()
            if existing:
                return existing, "tier1_exact_source_url", 0.99

        # 2. Tier 1b: Dedicated Official Event Website (hanya domain mandiri event, BUKAN portal berita/media/search engine)
        if website and website.startswith("http"):
            dom = extract_domain(website)
            if dom and dom not in DIRECTORY_AND_AGGREGATOR_DOMAINS and dom not in NEWS_AND_MEDIA_DOMAINS:
                if not any(dom == d or dom.endswith("." + d) for d in NEWS_AND_MEDIA_DOMAINS):
                    existing = Event.query.filter(Event.website.like(f"%{dom}%")).first()
                    if existing:
                        y_exist = re.search(r'\b(202\d)\b', existing.name)
                        y_new = re.search(r'\b(202\d)\b', name)
                        if not y_exist or not y_new or y_exist.group(1) == y_new.group(1):
                            return existing, "tier1_official_website", 0.95

        # 3. Tier 2: Normalized Name Matching
        norm_name = normalize_event_name(name)
        if not norm_name:
            return None, "none", 0.0

        new_year_match = re.search(r'\b(202\d)\b', name)
        new_year = int(new_year_match.group(1)) if new_year_match else (start_date.year if isinstance(start_date, (datetime, date)) else None)

        all_events = Event.query.all()
        for ev in all_events:
            ev_norm = normalize_event_name(ev.name)
            if not ev_norm:
                continue

            if norm_name == ev_norm:
                ev_year_match = re.search(r'\b(202\d)\b', ev.name)
                ev_year = int(ev_year_match.group(1)) if ev_year_match else (ev.start_date.year if ev.start_date else None)

                # Jika tahun jelas berbeda (misal 2026 vs 2027), ini adalah event tahun yang berbeda!
                if new_year and ev_year and new_year != ev_year:
                    continue

                if start_date and ev.start_date and start_date == ev.start_date:
                    return ev, "tier2_name_date", 0.95
                if venue and ev.venue and venue.lower() == ev.venue.lower():
                    return ev, "tier2_name_venue", 0.92
                if city and ev.city and city.lower() == ev.city.lower():
                    return ev, "tier2_name_city", 0.90
                if organizer and ev.organizer and organizer.lower() == ev.organizer.lower():
                    return ev, "tier3_name_organizer", 0.85
                if new_year and ev_year and new_year == ev_year:
                    return ev, "tier2_name_year", 0.90

        return None, "none", 0.0

    @classmethod
    def create_or_update_event(cls, event_data: Dict[str, Any], dry_run: bool = False) -> Tuple[Event, bool, str]:
        """Membuat atau memperbarui event secara idempotent dan non-destructive."""
        existing, match_tier, confidence = cls.deduplicate_event(event_data)

        # Hitung relevansi
        relevance_cat, rel_score, rel_notes = cls.calculate_relevance(
            name=event_data.get("name", ""),
            event_type=event_data.get("event_type", ""),
            description=event_data.get("description", ""),
            organizer=event_data.get("organizer", "")
        )

        if existing:
            # Safe Non-Destructive Update
            if not dry_run:
                if not existing.description and event_data.get("description"):
                    existing.description = event_data["description"]
                if not existing.venue and event_data.get("venue"):
                    existing.venue = event_data["venue"]
                if not existing.city and event_data.get("city"):
                    existing.city = event_data["city"]
                if not existing.province and event_data.get("province"):
                    existing.province = event_data["province"]
                if not existing.website and event_data.get("website"):
                    existing.website = event_data["website"]
                if not existing.social_json and event_data.get("social_json"):
                    existing.social_json = event_data["social_json"]
                # Upgrade tanggal jika data baru lebih pasti (misal exact date menggantikan tentative)
                new_s, new_prec = parse_extracted_date(event_data.get("start_date"))
                new_e, _ = parse_extracted_date(event_data.get("end_date"))
                if new_prec == "exact" and (existing.date_precision != "exact" or not existing.start_date):
                    existing.start_date = new_s
                    existing.end_date = new_e
                    existing.date_precision = "exact"
                elif new_prec == "month" and (existing.date_precision == "tentative" or not existing.start_date):
                    existing.start_date = new_s
                    existing.date_precision = "month"

                if rel_score > (existing.relevance_score or 0):
                    existing.relevance_score = rel_score
                    existing.relevance_notes = rel_notes
                existing.last_seen = utc_now()
                db.session.commit()
            return existing, False, f"Updated ({match_tier})"

        # Validasi Keaslian Sumber URL
        source_url = (event_data.get("source_url") or "").strip()
        if not source_url.startswith("http://") and not source_url.startswith("https://"):
            logger.warning(f"Event ditolak karena tidak memiliki URL sumber web/berita asli: {event_data.get('name')}")
            return None, False, "Rejected (Invalid source_url)"

        # Parsing tanggal jika masih string
        start_date, start_prec = parse_extracted_date(event_data.get("start_date"))
        end_date, end_prec = parse_extracted_date(event_data.get("end_date"))
        date_precision = event_data.get("date_precision") or start_prec

        # Buat Event Baru
        event = Event(
            name=(event_data.get("name") or "").strip(),
            event_type=event_data.get("event_type", "Exhibition / Trade Fair"),
            organizer=event_data.get("organizer"),
            organizer_id=event_data.get("organizer_id"),
            status=event_data.get("status", "upcoming"),
            start_date=start_date,
            end_date=end_date,
            date_precision=date_precision,
            venue=event_data.get("venue"),
            city=event_data.get("city"),
            province=event_data.get("province"),
            address=event_data.get("address"),
            website=event_data.get("website"),
            social_json=event_data.get("social_json"),
            source_url=event_data.get("source_url"),
            description=event_data.get("description"),
            relevance_notes=rel_notes,
            relevance_score=rel_score,
            verification_status="verified" if relevance_cat in ("HIGH", "MEDIUM") else "discovered",
            created_at=utc_now(),
            last_seen=utc_now()
        )

        if not dry_run:
            db.session.add(event)
            db.session.commit()

        return event, True, "Created"

    @classmethod
    def discover_events(
        cls,
        query: str = "",
        city: str = "",
        province: str = "",
        year: str = "2026, 2027",
        limit: int = 20,
        user_id: Optional[int] = None,
        include_social_media: bool = True
    ) -> Dict[str, Any]:
        """
        Menemukan event pameran, expo, festival B2B, dan turnamen olahraga nyata
        secara dinamis di seluruh Indonesia menggunakan Google News RSS Search + Google CSE.
        Bebas halusinasi: HANYA menyimpan event dengan bukti URL berita/website nyata.
        """
        from app.ai_agent import _chat_json

        target_loc = []
        if city:
            target_loc.append(city)
        if province:
            target_loc.append(province)
        location_str = ", ".join(target_loc) if target_loc else "Indonesia"

        # 1. Tarik snippets faktual dari Google News RSS (Tier 1) & Google Custom Search (Tier 2)
        snippets = fetch_google_news_events(
            query=query,
            location=location_str,
            year=year,
            limit=limit * 2
        )

        # 1b. Coba DuckDuckGo Free Search via MCP jika hasil Google News masih kurang
        if len(snippets) < limit:
            try:
                ddg_query = f"{query or 'pameran expo'} {location_str} {year or '2027'}".strip()
                ddg_items = mcp_search_duckduckgo(query=ddg_query, max_results=limit)
                for di in ddg_items:
                    snippets.append({
                        "title": di.get("title", ""),
                        "url": di.get("url", ""),
                        "source_publisher": "DuckDuckGo (Free MCP Search)",
                        "source_domain": di.get("url", ""),
                        "pub_date": "",
                        "content": f"Judul: {di.get('title')}\nSumber: {di.get('url')}\nRingkasan: {di.get('snippet', '')}"
                    })
            except Exception as e:
                logger.warning(f"MCP DuckDuckGo search fallback error: {e}")

        # Coba Google Custom Search jika terkonfigurasi
        if len(snippets) < limit:
            cse_snips = fetch_google_custom_search_events(
                query=query,
                location=location_str,
                year=year,
                limit=limit
            )
            snippets.extend(cse_snips)

        # Coba Tavily jika API key tersedia & tidak melebihi kuota
        if len(snippets) < limit:
            try:
                tavily_q = [f"{query or ''} {location_str} {year or ''}".strip()]
                tav_snips = parallel_tavily_search_snippets(tavily_q, max_per_query=limit)
                snippets.extend(tav_snips)
            except Exception:
                pass

        # 1c. Tarik postingan Media Sosial (Instagram Reels & Posts, Facebook, TikTok) via Free MCP Engine (DuckDuckGo + Playwright)
        if include_social_media:
            try:
                logger.info("Starting Free MCP Social Media Discovery (DuckDuckGo + Playwright)...")
                # 1. Cari tautan medsos relevan melalui targeted dorks DuckDuckGo
                social_links = mcp_search_social_events(
                    query=query or "pameran expo festival event",
                    year=year or "2027",
                    platforms=["instagram", "facebook", "tiktok"],
                    max_results=min(limit, 8)
                )
                # 2. Render dan scrape setiap URL postingan/reels dengan Playwright Headless Browser
                for s_item in social_links:
                    target_url = s_item.get("url")
                    if not target_url:
                        continue
                    scraped = mcp_scrape_url(target_url)
                    body_content = scraped.get("content") or s_item.get("snippet") or ""
                    if len(body_content) > 30:
                        snippets.append({
                            "title": scraped.get("title") or s_item.get("title") or f"Event {s_item.get('platform')}",
                            "url": target_url,
                            "source_publisher": f"Social Media ({s_item.get('platform', 'Social').upper()})",
                            "source_domain": target_url,
                            "pub_date": "",
                            "content": f"Platform: {s_item.get('platform', '').upper()}\nURL Asli: {target_url}\nJudul/Caption: {scraped.get('title')}\nTeks Konten: {body_content[:1500]}"
                        })
            except Exception as e:
                logger.warning(f"Free MCP Playwright social discovery error: {e}")

        if not snippets:
            return {
                "total_processed": 0,
                "created": 0,
                "updated": 0,
                "items": [],
                "message": f"Tidak ditemukan berita atau artikel event resmi dari Google untuk kata kunci '{query}' di wilayah '{location_str}' (Tahun {year})."
            }

        # 2. AI Extraction dalam chunks dari data Google nyata
        chunk_size = 10
        all_event_candidates = []
        for i in range(0, len(snippets), chunk_size):
            chunk = snippets[i:i + chunk_size]
            prompt = f"""Kamu adalah AI Event Intelligence spesialis penemuan event B2B, expo, dan turnamen olahraga di Indonesia.
Berdasarkan data berita & pencarian web Google berikut, ekstrak HANYA daftar event/pameran/expo/turnamen nyata di Indonesia:

DATA BERITA GOOGLE:
{json.dumps([{'title': s.get('title'), 'url': s.get('url'), 'content': (s.get('content') or '')[:450]} for s in chunk], ensure_ascii=False)}

Kriteria:
- Target lokasi: {location_str}
- Kategori / Topik: {query or 'Pameran B2B / Olahraga'}
- Target Tahun: {year or '2026 atau 2027'}

ATURAN KETAT & TANGGAL PRESISI:
1. DILARANG MENGARANG EVENT! Jika suatu berita hanya tentang penutupan event lama atau bukan tentang event mendatang 2026/2027, jangan masukkan.
2. DILARANG MENGARANG TANGGAL 1 JANUARI!
   - Jika teks berita menyebutkan tanggal dan bulan pasti (contoh: '15-18 Agustus 2027'), tulis '2027-08-15' di start_date dan '2027-08-18' di end_date.
   - Jika hanya ada bulan dan tahun (contoh: 'Oktober 2027'), tulis 'Oktober 2027' di start_date dan null di end_date.
   - Jika HANYA ada tahun '2027' (jadwal tanggal & bulan belum diumumkan panitia), WAJIB isi start_date: null, end_date: null.
3. Ekstrak venue gedung yang spesifik (misal: 'JIExpo Kemayoran', 'ICE BSD Hall 5', 'JCC Senayan'). Jika belum diumumkan, isi null.
4. Setiap event yang diekstrak WAJIB memiliki "source_url" yang sama persis dengan URL berita asalnya. Jika sumber berasal dari media sosial (Instagram/Facebook/TikTok), "source_url" WAJIB berupa tautan link postingan atau reels spesifik (contoh: https://www.instagram.com/reel/XYZ... atau https://www.instagram.com/p/ABC...), DILARANG menggunakan tautan root profile profil akun saja!

Kembalikan format HANYA JSON array:
[
  {{
    "name": "Nama Resmi Event (contoh: IndoBuildTech 2027, Jatim Fair 2026)",
    "event_type": "Exhibition / Trade Fair / Conference / Sports Tournament / Career Fair",
    "venue": "Nama Gedung / Tempat jika ada",
    "city": "Kota",
    "province": "Provinsi",
    "organizer": "Nama Penyelenggara / EO / Institusi",
    "start_date": "Estimasi tanggal (YYYY-MM-DD atau Bulan Tahun jika ada)",
    "end_date": "Estimasi tanggal selesai jika ada",
    "website": "URL website resmi jika ada",
    "source_url": "URL berita atau tautan link postingan/reels media sosial asli",
    "description": "Deskripsi singkat profil event dan potensi kebutuhan seragam/apparel/merchandise",
    "status": "upcoming"
  }}
]
"""
            try:
                raw_data = _chat_json(
                    system_prompt="Kamu adalah AI Event Intelligence yang HANYA mengekstrak event faktual dari data berita Google tanpa halusinasi.",
                    user_prompt=prompt,
                    temperature=0.1
                )
                cands = raw_data if isinstance(raw_data, list) else raw_data.get("events") or raw_data.get("items") or []
                if isinstance(cands, list):
                    all_event_candidates.extend(cands)
            except Exception as e:
                logger.error(f"Error in event AI chunk extraction: {e}")

        # CATATAN: TIDAK ADA LAGI FALLBACK MENGARANG!
        # Jika hasil ekstraksi kosong, sistem jujur bahwa tidak ada event baru.

        # 3. Simpan ke database dengan validasi & deduplikasi ketat
        created_count = 0
        updated_count = 0
        items = []

        for c in all_event_candidates[:limit]:
            if not isinstance(c, dict) or not c.get("name"):
                continue

            src_url = (c.get("source_url") or "").strip()
            # Validasi mutlak: wajib URL web asli
            if not src_url.startswith("http://") and not src_url.startswith("https://"):
                continue

            # Parsing tanggal faktual dengan presisi (tanpa pemalsuan 1 Januari)
            parsed_start, start_prec = parse_extracted_date(c.get("start_date"))
            parsed_end, end_prec = parse_extracted_date(c.get("end_date"))
            date_precision = c.get("date_precision") or start_prec

            event_dict = {
                "name": (c.get("name") or "").strip(),
                "event_type": c.get("event_type", "Exhibition / Trade Fair"),
                "venue": c.get("venue") if c.get("venue") != "-" else None,
                "city": c.get("city") or city or None,
                "province": c.get("province") or province or None,
                "organizer": c.get("organizer") if c.get("organizer") != "-" else None,
                "start_date": parsed_start,
                "end_date": parsed_end,
                "date_precision": date_precision,
                "website": c.get("website") if (c.get("website") or "").startswith("http") else None,
                "description": c.get("description"),
                "status": c.get("status", "upcoming"),
                "source_url": src_url,
                "social_json": json.dumps({"instagram": src_url}) if "instagram.com" in src_url.lower() else (json.dumps({"facebook": src_url}) if "facebook.com" in src_url.lower() else (json.dumps({"tiktok": src_url}) if "tiktok.com" in src_url.lower() else None))
            }

            event, is_new, msg = cls.create_or_update_event(event_dict)
            if not event:
                continue

            if is_new:
                created_count += 1
            else:
                updated_count += 1

            items.append({
                "id": event.id,
                "name": event.name,
                "city": event.city,
                "province": event.province,
                "is_new": is_new,
                "relevance_score": event.relevance_score
            })

        return {
            "total_processed": len(items),
            "created": created_count,
            "updated": updated_count,
            "items": items
        }

    @classmethod
    def match_organization(cls, company_name: str, domain: Optional[str] = None) -> Tuple[Optional[Organization], str]:
        """Mencari entitas Master Organization yang cocok untuk menjadi peserta/organizer.
        Menggunakan Domain Match (Tier 1) atau Normalized Legal Name (Tier 2).
        Jika ambigu, mengembalikan (None, 'ambiguous').
        """
        if not company_name:
            return None, "empty_name"

        # 1. Domain match jika ada
        if domain and domain not in DIRECTORY_AND_AGGREGATOR_DOMAINS and domain not in PUBLIC_EMAIL_DOMAINS:
            org = Organization.query.filter(Organization.domain == domain).first()
            if org:
                return org, "tier1_domain"

        # 2. Normalized name match
        norm = normalize_company_name(company_name)
        if norm:
            org = Organization.query.filter(
                db.or_(
                    Organization.name == company_name,
                    Organization.name.like(f"%{norm}%")
                )
            ).first()
            if org:
                return org, "tier2_normalized_name"

        return None, "not_found"

    @classmethod
    def link_participant(
        cls,
        event_id: int,
        organization_id: int,
        role: str = "exhibitor",
        booth_number: Optional[str] = None,
        notes: Optional[str] = None,
        dry_run: bool = False
    ) -> Tuple[Optional[EventParticipant], bool]:
        """Menghubungkan organisasi master sebagai peserta event (organizer, exhibitor, sponsor, partner, speaker).
        Idempotent dan menjaga unique constraint uq_event_org_role.
        """
        existing = EventParticipant.query.filter_by(
            event_id=event_id,
            organization_id=organization_id,
            role=role
        ).first()

        if existing:
            if not dry_run and (booth_number or notes):
                if booth_number and not existing.booth_number:
                    existing.booth_number = booth_number
                if notes and not existing.notes:
                    existing.notes = notes
                db.session.commit()
            return existing, False

        part = EventParticipant(
            event_id=event_id,
            organization_id=organization_id,
            role=role,
            booth_number=booth_number,
            notes=notes,
            created_at=utc_now()
        )

        if not dry_run:
            db.session.add(part)
            db.session.commit()

        return part, True

    @classmethod
    def get_workspace_events(
        cls,
        q: str = "",
        event_type: str = "",
        relevance: str = "",
        city: str = "",
        province: str = "",
        sport: str = "",
        status: str = "",
        organizer: str = "",
        start_date_from: Optional[datetime] = None,
        start_date_to: Optional[datetime] = None,
        source: str = "",
        verification_status: str = "",
        year: str = "",
        month: str = "",
        page: int = 1,
        per_page: Optional[int] = 20
    ) -> Tuple[List[Event], int, int]:
        """Pencarian dan penyaringan data Event Intelligence Workspace."""
        query = Event.query

        if q:
            query = query.filter(
                db.or_(
                    Event.name.like(f"%{q}%"),
                    Event.organizer.like(f"%{q}%"),
                    Event.venue.like(f"%{q}%"),
                    Event.city.like(f"%{q}%"),
                    Event.province.like(f"%{q}%"),
                    Event.description.like(f"%{q}%")
                )
            )

        if sport:
            sport_clean = sport.strip().lower()
            query = query.filter(
                db.or_(
                    Event.name.ilike(f"%{sport_clean}%"),
                    Event.event_type.ilike(f"%{sport_clean}%"),
                    Event.description.ilike(f"%{sport_clean}%"),
                    Event.relevance_notes.ilike(f"%{sport_clean}%")
                )
            )

        if event_type:
            query = query.filter(Event.event_type == event_type)

        if city:
            query = query.filter(
                db.or_(
                    Event.city.ilike(f"%{city}%"),
                    Event.province.ilike(f"%{city}%")
                )
            )

        if province:
            query = query.filter(Event.province.ilike(f"%{province}%"))

        if status:
            query = query.filter(Event.status == status)

        if year:
            year_clean = year.strip()
            if year_clean.isdigit():
                y_int = int(year_clean)
                other_years = [str(y) for y in [2024, 2025, 2026, 2027, 2028, 2029] if y != y_int]
                query = query.filter(
                    db.or_(
                        Event.name.like(f"%{year_clean}%"),
                        db.and_(
                            db.extract("year", Event.start_date) == y_int,
                            *[~Event.name.like(f"%{oy}%") for oy in other_years]
                        )
                    )
                )
            else:
                query = query.filter(Event.name.like(f"%{year_clean}%"))

        if month:
            month_clean = month.strip()
            if month_clean.isdigit():
                m_int = int(month_clean)
                query = query.filter(db.extract("month", Event.start_date) == m_int)

        if organizer:
            query = query.filter(Event.organizer.like(f"%{organizer}%"))

        if start_date_from:
            query = query.filter(Event.start_date >= start_date_from)

        if start_date_to:
            query = query.filter(Event.start_date <= start_date_to)

        if source:
            query = query.filter(
                db.or_(
                    Event.website.like(f"%{source}%"),
                    Event.source_url.like(f"%{source}%")
                )
            )

        if verification_status:
            query = query.filter(Event.verification_status == verification_status)

        if relevance == "HIGH":
            query = query.filter(Event.relevance_score >= 80)
        elif relevance == "MEDIUM":
            query = query.filter(Event.relevance_score >= 50, Event.relevance_score < 80)
        elif relevance == "LOW":
            query = query.filter(Event.relevance_score < 50)

        total_count = query.count()
        has_info = db.case(
            (db.or_(Event.website.isnot(None), Event.social_json.isnot(None), Event.source_url.like('http%')), 1),
            else_=0
        )
        if per_page is None or per_page <= 0:
            items = query.order_by(
                has_info.desc(),
                Event.relevance_score.desc(),
                Event.start_date.desc().nullslast()
            ).all()
            return items, total_count, 1

        total_pages = (total_count + per_page - 1) // per_page if total_count > 0 else 1

        has_info = db.case(
            (db.or_(Event.website.isnot(None), Event.social_json.isnot(None), Event.source_url.like('http%')), 1),
            else_=0
        )
        items = query.order_by(
            has_info.desc(),
            Event.relevance_score.desc(),
            Event.start_date.desc().nullslast()
        ).offset((page - 1) * per_page).limit(per_page).all()

        return items, total_count, total_pages

    @classmethod
    def get_event_detail(cls, event_id: int) -> Optional[Dict[str, Any]]:
        """Mengambil profil lengkap event, organizer, peserta per peran, dan statistik."""
        event = db.session.get(Event, event_id)
        if not event:
            return None

        # Kelompokkan partisipan berdasarkan peran
        participants = EventParticipant.query.filter_by(event_id=event_id).all()
        by_role = {
            "organizers": [],
            "exhibitors": [],
            "sponsors": [],
            "partners": [],
            "speakers": []
        }

        for p in participants:
            role_key = f"{p.role}s" if not p.role.endswith("s") else p.role
            if role_key in by_role:
                by_role[role_key].append({
                    "id": p.id,
                    "organization_id": p.organization_id,
                    "organization_name": p.organization.name if p.organization else "Unknown",
                    "organization_industry": p.organization.industry if p.organization else None,
                    "organization_website": p.organization.website if p.organization else None,
                    "booth_number": p.booth_number,
                    "notes": p.notes
                })

        socials = {}
        if event.social_json:
            try:
                socials = json.loads(event.social_json) if isinstance(json.loads(event.social_json), dict) else {}
            except Exception:
                socials = {}

        return {
            "event": event,
            "socials": socials,
            "participants_count": len(participants),
            "by_role": by_role,
            "relevance_badge": "HIGH" if (event.relevance_score or 0) >= 80 else ("MEDIUM" if (event.relevance_score or 0) >= 50 else "LOW")
        }


    @classmethod
    def export_events_to_excel(cls, events: List[Event], filter_summary: str = ""):
        """Mengekspor daftar event terfilter ke file Excel (.xlsx) dengan formatting profesional."""
        import io
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils import get_column_letter

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Daftar Event"

        # Judul & Info Metadata
        wb.properties.title = "MARKET INTELLIGENCE - DAFTAR EVENT B2B & EXPO"
        wb.properties.subject = filter_summary or "Semua Data"




        ws.row_dimensions[1].height = 28









        # Baris Header Kolom
        headers = [
            ("No", 6, "center"),
            ("Nama Event", 35, "left"),
            ("Jenis Event", 20, "left"),
            ("Tanggal Pelaksanaan", 25, "center"),
            ("Status Tanggal", 15, "center"),
            ("Tahun", 10, "center"),
            ("Venue / Gedung", 28, "left"),
            ("Kota", 16, "left"),
            ("Provinsi", 16, "left"),
            ("Penyelenggara", 28, "left"),
            ("Status", 14, "center"),
            ("Skor", 10, "right"),
            ("Peluang B2B / Apparel", 35, "left"),
            ("Website Resmi", 25, "left"),
            ("URL Sumber Bukti", 30, "left")
        ]

        header_font = Font(name="Calibri", size=11, bold=True, color="000000")
        header_fill = PatternFill(fill_type="solid", fgColor="D9E1F2", start_color="D9E1F2", end_color="D9E1F2")
        thin_border = Border(
            left=Side(style="thin", color="CBD5E1"),
            right=Side(style="thin", color="CBD5E1"),
            top=Side(style="thin", color="CBD5E1"),
            bottom=Side(style="medium", color="305496")
        )


        for col_idx, (h_name, width, align) in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col_idx, value=h_name)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.border = thin_border
            ws.column_dimensions[get_column_letter(col_idx)].width = width

        # Data Rows
        zebra_fill = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")
        white_fill = PatternFill(start_color="FFFFFF", end_color="FFFFFF", fill_type="solid")
        data_font = Font(name="Calibri", size=10)

        for row_idx, ev in enumerate(events, 2):
            is_even = (row_idx % 2 == 0)
            row_fill = zebra_fill if is_even else white_fill
            ws.row_dimensions[row_idx].height = 22

            status_tgl = "Pasti / Terkonfirmasi" if ev.is_date_confirmed else ("Bulan (Estimasi)" if ev.date_precision == "month" else "Tentatif (Estimasi)")

            row_data = [
                (row_idx - 1, "center"),
                (ev.name or "", "left"),
                (ev.event_type or "-", "left"),
                (ev.date_display or "-", "center"),
                (status_tgl, "center"),
                (ev.event_year or "-", "center"),
                (ev.venue or "-", "left"),
                (ev.city or "-", "left"),
                (ev.province or "-", "left"),
                (ev.organizer or "-", "left"),
                ((ev.status or "upcoming").capitalize(), "center"),
                (ev.relevance_score or 0, "right"),
                (ev.relevance_notes or ev.description or "-", "left"),
                (ev.clean_website or "-", "left"),
                (ev.clean_source_url or ev.source_url or "-", "left")
            ]

            for col_idx, (val, align) in enumerate(row_data, 1):
                cell = ws.cell(row=row_idx, column=col_idx, value=val)
                cell.font = data_font
                cell.fill = row_fill
                cell.border = thin_border
                cell.alignment = Alignment(horizontal=align, vertical="center")

                if col_idx in [14, 15] and isinstance(val, str) and val.startswith("http"):
                    cell.hyperlink = val
                    cell.font = Font(name="Calibri", size=10, color="0044CC", underline="single")

        if not events:
            ws.merge_cells("A2:O2")
            empty_cell = ws["A2"]
            empty_cell.value = "Tidak ada event yang ditemukan untuk kriteria filter yang dipilih."
            empty_cell.font = Font(name="Calibri", size=11, italic=True, color="475569")
            empty_cell.alignment = Alignment(horizontal="center", vertical="center")
            ws.row_dimensions[2].height = 28

        # Freeze Panes: Baris 1 Header selalu terkunci / terbawa saat scroll ke bawah
        ws.freeze_panes = "A2"

        # Aktifkan AutoFilter Excel di baris header
        total_rows = max(len(events) + 1, 2)
        ws.auto_filter.ref = f"A1:O{total_rows}"
        ws.print_title_rows = "1:1"

        stream = io.BytesIO()
        wb.save(stream)
        stream.seek(0)
        return stream
