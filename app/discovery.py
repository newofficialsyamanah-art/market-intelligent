import json
import re
from datetime import datetime, timezone
from urllib.parse import parse_qs, quote_plus, unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from flask import current_app

from app.extensions import db
from app.models import DiscoverySource, Event, Organization

USER_AGENT = "SyamanahMarketIntelligence/1.0 (+public-data-discovery)"
SOCIAL_HOSTS = ("instagram.com", "facebook.com", "linkedin.com", "twitter.com", "x.com", "youtube.com")


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _ddg_api_results(query, verify_ssl):
    response = requests.get(
        "https://api.duckduckgo.com/",
        params={"q": query, "format": "json", "no_html": 1, "skip_disambig": 1},
        headers={"User-Agent": USER_AGENT},
        verify=verify_ssl,
        timeout=20,
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


def _search(query):
    provider = current_app.config.get("SEARCH_PROVIDER", "duckduckgo").lower()
    if provider in {"duckduckgo", "ddg"}:
        results = []
        verify_ssl = current_app.config.get("DUCKDUCKGO_VERIFY_SSL", True)
        for endpoint in ("https://html.duckduckgo.com/html/", "https://lite.duckduckgo.com/lite/"):
            response = requests.get(
                endpoint,
                params={"q": query, "kl": "id-id"},
                headers={"User-Agent": USER_AGENT},
                verify=verify_ssl,
                timeout=20,
            )
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            anchors = soup.select("a[href]")
            for anchor in anchors:
                href = anchor.get("href", "")
                parsed = urlparse(href)
                target = parse_qs(parsed.query).get("uddg", [href])[0]
                target = unquote(target)
                target_host = urlparse(target).netloc.lower()
                if target.startswith(("http://", "https://")) and target_host and "duckduckgo.com" not in target_host:
                    results.append(target)
            if results:
                break
        if not results:
            results.extend(_ddg_api_results(query, verify_ssl))
        return list(dict.fromkeys(results))[:10]
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


def _fetch(url):
    response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=20)
    response.raise_for_status()
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


def _page_data(url):
    final_url, soup = _fetch(url)
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = " ".join(soup.get_text(" ").split())
    links = [urljoin(final_url, link.get("href")) for link in soup.select("a[href]")]
    emails = re.findall(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", text, re.I)
    phones = re.findall(r"(?:\+62|62|0)[\s().-]?\d[\d\s().-]{7,}", text)
    social = sorted({link.split("?")[0].rstrip("/") for link in links if any(host in link.lower() for host in SOCIAL_HOSTS)})
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
