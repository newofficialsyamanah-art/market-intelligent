import base64
import json
import re
import socket
from datetime import datetime, timezone
from urllib.parse import parse_qs, quote_plus, unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from flask import current_app

from app.extensions import db
from app.models import DiscoverySource, Event, Organization

USER_AGENT = "SyamanahMarketIntelligence/1.0 (+public-data-discovery)"
SOCIAL_HOSTS = ("instagram.com", "facebook.com", "linkedin.com", "twitter.com", "x.com", "youtube.com", "tiktok.com")
CAPTIVE_DOMAINS = ("internet-positif", "uzone.id", "internetbaik", "mercusuar", "u-ad.info", "telkomsel", "indihome")
DDG_FALLBACK_IPS = ["52.142.124.215", "40.89.244.232", "104.18.38.236", "172.67.181.71"]
_resolved_ddg_ip = None
_orig_create_connection = None


def _is_ip_responsive(ip, port=443):
    try:
        s = socket.socket()
        s.settimeout(1.2)
        res = s.connect_ex((ip, port))
        s.close()
        return res == 0
    except Exception:
        return False


def _get_ddg_ip():
    global _resolved_ddg_ip
    if _resolved_ddg_ip and _is_ip_responsive(_resolved_ddg_ip):
        return _resolved_ddg_ip
    try:
        res = requests.get(
            "https://cloudflare-dns.com/dns-query",
            params={"name": "html.duckduckgo.com", "type": "A"},
            headers={"accept": "application/dns-json"},
            timeout=2.0,
        )
        if res.status_code == 200:
            for ans in res.json().get("Answer", []):
                ip = ans.get("data")
                if ans.get("type") == 1 and ip and _is_ip_responsive(ip):
                    _resolved_ddg_ip = ip
                    return _resolved_ddg_ip
    except Exception:
        pass

    for ip in DDG_FALLBACK_IPS:
        if _is_ip_responsive(ip):
            _resolved_ddg_ip = ip
            return _resolved_ddg_ip

    _resolved_ddg_ip = DDG_FALLBACK_IPS[0]
    return _resolved_ddg_ip


def _ddg_session():
    global _orig_create_connection
    from urllib3.util import connection
    if _orig_create_connection is None:
        _orig_create_connection = connection.create_connection

        def custom_create_connection(address, *args, **kwargs):
            host, port = address
            if any(h in host for h in ("duckduckgo.com", "html.duckduckgo.com", "lite.duckduckgo.com", "api.duckduckgo.com")):
                ip = _get_ddg_ip()
                return _orig_create_connection((ip, port), *args, **kwargs)
            return _orig_create_connection(address, *args, **kwargs)

        connection.create_connection = custom_create_connection

    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Origin": "https://duckduckgo.com",
        "Referer": "https://duckduckgo.com/",
    })
    return s


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _bing_search_fallback(query):
    """Fallback search instan via Bing tanpa blokir ISP (selesai dalam <1 detik)."""
    try:
        r = requests.get(
            "https://www.bing.com/search",
            params={"q": query},
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"},
            timeout=3.0,
        )
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            results = []
            for a in soup.select("li.b_algo h2 a, li.b_algo a[href]"):
                href = a.get("href", "")
                if "bing.com/ck/a" in href:
                    u = parse_qs(urlparse(href).query).get("u", [""])[0]
                    if u.startswith("a1"):
                        try:
                            dec = base64.urlsafe_b64decode(u[2:] + "===").decode("utf-8", errors="ignore")
                            if dec.startswith("http") and not any(bad in dec for bad in CAPTIVE_DOMAINS) and "bing.com" not in dec:
                                results.append(dec)
                        except Exception:
                            pass
                elif href.startswith("http") and not any(bad in href for bad in CAPTIVE_DOMAINS) and "bing.com" not in href:
                    results.append(href)
            return list(dict.fromkeys(results))[:15]
    except Exception:
        pass
    return []


def _ddg_api_results(query, verify_ssl):
    try:
        s = _ddg_session()
        response = s.get(
            "https://api.duckduckgo.com/",
            params={"q": query, "format": "json", "no_html": 1, "skip_disambig": 1},
            verify=verify_ssl,
            timeout=3.0,
        )
        response.raise_for_status()

        def collect(items):
            found = []
            for item in items or []:
                if item.get("FirstURL"):
                    found.append(item["FirstURL"])
                found.extend(collect(item.get("Topics")))
            return found

        return collect(response.json().get("RelatedTopics"))
    except Exception:
        return []


def _search(query):
    provider = current_app.config.get("SEARCH_PROVIDER", "duckduckgo").lower()
    if provider in {"duckduckgo", "ddg"}:
        results = []
        verify_ssl = current_app.config.get("DUCKDUCKGO_VERIFY_SSL", True)

        # 1. Coba DuckDuckGo POST dengan timeout ketat 3 detik
        try:
            s = _ddg_session()
            response = s.post(
                "https://html.duckduckgo.com/html/",
                data={"q": query, "b": "", "kl": "id-id"},
                verify=verify_ssl,
                timeout=3.0,
            )
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")
                anchors = soup.select(".result__title a, a.result__url, .result__snippet")
                for anchor in anchors:
                    href = anchor.get("href", "")
                    parsed = urlparse(href)
                    target = parse_qs(parsed.query).get("uddg", [href])[0]
                    target = unquote(target)
                    target_host = urlparse(target).netloc.lower()
                    if (
                        target.startswith(("http://", "https://"))
                        and target_host
                        and not any(bad in target_host for bad in CAPTIVE_DOMAINS)
                    ):
                        results.append(target)
        except Exception:
            pass

        # 2. Jika DDG gagal, diblokir, atau bot challenge, langsung fallback ke Bing (<1 detik)
        if not results:
            results = _bing_search_fallback(query)

        # 3. Jika masih kosong, coba DuckDuckGo Lite singkat 2 detik
        if not results:
            try:
                s = _ddg_session()
                response = s.get(
                    "https://lite.duckduckgo.com/lite/",
                    params={"q": query, "kl": "id-id"},
                    verify=verify_ssl,
                    timeout=2.0,
                )
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, "html.parser")
                    for anchor in soup.select("a[href]"):
                        href = anchor.get("href", "")
                        parsed = urlparse(href)
                        target = parse_qs(parsed.query).get("uddg", [href])[0]
                        target = unquote(target)
                        target_host = urlparse(target).netloc.lower()
                        if (
                            target.startswith(("http://", "https://"))
                            and target_host
                            and not any(bad in target_host for bad in CAPTIVE_DOMAINS)
                        ):
                            results.append(target)
            except Exception:
                pass

        if not results:
            try:
                results.extend(_ddg_api_results(query, verify_ssl))
            except Exception:
                pass
        return list(dict.fromkeys(results))[:15]

    if provider in {"searxng", "searx"}:
        base_url = current_app.config.get("SEARXNG_BASE_URL", "").rstrip("/")
        if not base_url:
            raise RuntimeError("SEARXNG_BASE_URL belum diisi")
        response = requests.get(
            f"{base_url}/search",
            params={
                "q": query,
                "format": "json",
                "categories": "general",
                "language": "id-ID",
                "safesearch": 1,
            },
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            timeout=current_app.config.get("SEARXNG_TIMEOUT", 20),
        )
        response.raise_for_status()
        if any(marker in response.text.lower() for marker in ("verifying your browser", "antibot", "/captcha")):
            raise RuntimeError("Instance SearXNG memblokir automation dengan anti-bot/CAPTCHA; pilih instance lain atau self-host.")
        try:
            payload = response.json()
            return list(dict.fromkeys(
                item.get("url") for item in payload.get("results", []) if item.get("url")
            ))[:10]
        except ValueError:
            soup = BeautifulSoup(response.text, "html.parser")
            base_host = urlparse(base_url).netloc.lower()
            urls = []
            for anchor in soup.select("a.result_header[href], article.result a[href]"):
                target = unquote(anchor.get("href", ""))
                target_host = urlparse(target).netloc.lower()
                if target.startswith(("http://", "https://")) and target_host and target_host != base_host:
                    urls.append(target)
            return list(dict.fromkeys(urls))[:10]

    if provider == "google":
        key = current_app.config.get("GOOGLE_SEARCH_API_KEY")
        engine_id = current_app.config.get("GOOGLE_SEARCH_ENGINE_ID")
        if not key or not engine_id:
            raise RuntimeError("GOOGLE_SEARCH_API_KEY dan GOOGLE_SEARCH_ENGINE_ID belum diisi")
        response = requests.get(
            "https://www.googleapis.com/customsearch/v1",
            params={"key": key, "cx": engine_id, "q": query, "num": 10},
            timeout=20,
        )
        response.raise_for_status()
        return [item.get("link") for item in response.json().get("items", []) if item.get("link")]

    key = current_app.config.get("BING_SEARCH_API_KEY")
    if not key:
        raise RuntimeError("BING_SEARCH_API_KEY belum diisi, atau gunakan source URL langsung")
    response = requests.get(
        "https://api.bing.microsoft.com/v7.0/search",
        headers={"Ocp-Apim-Subscription-Key": key},
        params={"q": query, "count": 10, "mkt": "id-ID", "safeSearch": "Moderate"},
        timeout=20,
    )
    response.raise_for_status()
    return [item.get("url") for item in response.json().get("webPages", {}).get("value", []) if item.get("url")]


def _fetch(url, timeout=8):
    response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
    response.raise_for_status()
    final_host = urlparse(response.url).netloc.lower()
    if any(bad in final_host for bad in CAPTIVE_DOMAINS):
        raise RuntimeError(f"Halaman dialihkan ke captive portal / blokir ISP: {response.url}")
    return response.url, BeautifulSoup(response.text, "html.parser")


def _json_ld(soup):
    values = []
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            payload = json.loads(script.string or script.get_text())
            values.extend(payload if isinstance(payload, list) else [payload])
        except (TypeError, ValueError):
            continue
    return values


def _page_data(url, timeout=8):
    final_url, soup = _fetch(url, timeout=timeout)
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = " ".join(soup.get_text(" ").split())
    links = [urljoin(final_url, link.get("href")) for link in soup.select("a[href]") if link.get("href")]

    # Extract emails from mailto and text
    emails = []
    for link in links:
        m = re.match(r"^mailto:([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})", link, re.I)
        if m:
            emails.append(m.group(1).lower())
    for em in re.findall(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", text, re.I):
        em_lower = em.lower()
        if em_lower not in emails:
            emails.append(em_lower)

    # Extract phones from WhatsApp, tel, and text
    phones = []
    for link in links:
        wa_match = (
            re.search(r"wa\.me/(\+?\d+)", link)
            or re.search(r"[?&]phone=(\+?\d+)", link)
            or re.search(r"^tel:([+0-9\s()-]{8,})", link)
        )
        if wa_match:
            digits = re.sub(r"[^0-9+]", "", wa_match.group(1))
            if digits.startswith("+62"):
                digits = "0" + digits[3:]
            elif digits.startswith("62"):
                digits = "0" + digits[2:]
            if len(digits) >= 8 and digits not in phones:
                phones.append(digits)

    # Text regex for phone numbers (cellular and landlines)
    for raw_phone in re.findall(r"(?:\+62|62|0)8[1-9][0-9\s().-]{7,12}", text):
        clean_p = re.sub(r"[^0-9+]", "", raw_phone)
        if clean_p.startswith("+62"):
            clean_p = "0" + clean_p[3:]
        elif clean_p.startswith("62"):
            clean_p = "0" + clean_p[2:]
        if 9 <= len(clean_p) <= 14 and clean_p not in phones:
            phones.append(clean_p)

    social = sorted({
        link.split("?")[0].rstrip("/")
        for link in links
        if any(host in link.lower() for host in SOCIAL_HOSTS)
    })
    return final_url, soup, text[:20000], emails[:5], phones[:5], social[:10]


def _first(data, *keys):
    for key in keys:
        if data.get(key):
            value = data[key]
            if isinstance(value, dict):
                return value.get("name") or value.get("streetAddress") or value.get("addressLocality")
            return value
    return None


def _score(text, kind):
    words = (
        ["apparel", "fashion", "tekstil", "konveksi", "seragam", "garmen", "pameran", "expo", "bazaar"]
        if kind == "event" else
        ["company", "perusahaan", "manufactur", "industri", "universitas", "sekolah", "instansi", "organisasi"]
    )
    lowered = text.lower()
    return min(100, sum(15 for word in words if word in lowered))


def _upsert_organization(url, source, data=None, page_data=None):
    data = data or {}
    page_data = page_data or {}
    existing = Organization.query.filter_by(source_url=url).first()
    organization = existing or Organization(source_url=url, name="Unnamed organization", organization_type=source.category or "organization")
    organization.name = _first(data, "name", "legalName") or organization.name
    organization.organization_type = source.category or organization.organization_type
    organization.address = _first(data, "address", "streetAddress") or organization.address
    organization.city = _first(data, "addressLocality") or organization.city
    organization.province = _first(data, "addressRegion") or organization.province
    organization.phone = _first(data, "telephone") or organization.phone
    organization.email = _first(data, "email") or organization.email
    organization.website = _first(data, "url") or organization.website or url
    organization.social_json = json.dumps(page_data.get("social", []))
    organization.description = _first(data, "description") or organization.description
    organization.relevance_score = _score(json.dumps(data), "organization")
    organization.last_seen = _now()
    db.session.add(organization)
    return not existing


def _upsert_event(url, source, data=None, page_data=None):
    data = data or {}
    page_data = page_data or {}
    existing = Event.query.filter_by(source_url=url).first()
    event = existing or Event(source_url=url, name="Unnamed event")
    event.name = _first(data, "name") or event.name
    event.event_type = source.category or event.event_type
    event.organizer = _first(data, "organizer") or event.organizer
    event.venue = _first(data, "location", "name") or event.venue
    event.address = _first(data, "address", "streetAddress") or event.address
    event.city = _first(data, "addressLocality") or event.city
    event.province = _first(data, "addressRegion") or event.province
    event.website = _first(data, "url") or event.website or url
    event.description = _first(data, "description") or event.description or page_data.get("text", "")[:1000]
    event.social_json = json.dumps(page_data.get("social", []))
    event.relevance_score = _score(f"{event.name} {event.description}", "event")
    event.last_seen = _now()
    db.session.add(event)
    return not existing


def run_discovery(source_id):
    source = db.session.get(DiscoverySource, source_id)
    if not source or not source.is_active:
        return "source tidak aktif"
    urls = json.loads(source.source_urls_json or "[]")
    if source.query_text and source.query_text.strip():
        query = f"{source.query_text} {source.region or 'Indonesia'}"
        urls.extend(_search(query))
    elif not urls:
        source.last_run = _now()
        source.last_status = "warning: keyword dan URL sumber masih kosong"
        db.session.commit()
        return source.last_status
    urls = list(dict.fromkeys(urls))[:30]
    created = 0
    seen_final_urls = set()

    for url in urls:
        try:
            final_url, soup, text, emails, phones, social = _page_data(url)
            if final_url in seen_final_urls:
                continue
            seen_final_urls.add(final_url)

            structured = _json_ld(soup)
            candidates = [item for item in structured if isinstance(item, dict)]
            if source.source_kind == "event":
                events = [item for item in candidates if "Event" in str(item.get("@type", ""))] or [{}]
                for item in events:
                    with db.session.begin_nested():
                        is_new = _upsert_event(final_url, source, item, {"text": text, "social": social})
                        if is_new:
                            created += 1
            else:
                organizations = [item for item in candidates if "Organization" in str(item.get("@type", ""))]
                item = organizations[0] if organizations else {
                    "name": soup.title.get_text(strip=True) if soup.title else final_url,
                    "email": emails[0] if emails else None,
                    "telephone": phones[0] if phones else None,
                    "url": final_url,
                    "description": text[:1000]
                }
                with db.session.begin_nested():
                    is_new = _upsert_organization(final_url, source, item, {"social": social})
                    if is_new:
                        created += 1
        except Exception:
            continue

    source.last_run = _now()
    source.last_status = f"success: {created} data baru dari {len(urls)} URL"
    if not urls:
        source.last_status = "warning: DuckDuckGo tidak mengembalikan URL hasil pencarian"
    db.session.commit()
    return source.last_status
