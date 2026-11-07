"""Model Context Protocol (MCP) Service & Server.

Menyediakan arsitektur pencarian bebas biaya (Free & Open Source) berbasis MCP:
1. DuckDuckGo Free Search (Web & Social Dorks)
2. Playwright Headless Browser Scraper (Instagram Reels, Facebook, TikTok, Dynamic Web)
3. Fallback Resilient Scraper (OpenGraph / Meta Extractor)
4. Standard JSON-RPC 2.0 MCP Server (Tools List & Tool Calls)
"""

import sys
import os
import json
import logging
import re
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# User-Agent realistis agar tidak dicurigai bot oleh Instagram / Facebook / Web
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
MOBILE_USER_AGENT = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1"
)

# ============================================================================
# 1. CORE MCP TOOLS IMPLEMENTATION
# ============================================================================

def mcp_search_duckduckgo(query: str, max_results: int = 15, region: str = "id-id") -> List[Dict[str, Any]]:
    """Pencarian web bebas biaya menggunakan DuckDuckGo tanpa API key."""
    results = []
    
    # Prioritas 1: Gunakan library ddgs (duckduckgo_search)
    try:
        from ddgs import DDGS
        with DDGS() as ddgs_client:
            raw_items = list(ddgs_client.text(
                query,
                region=region,
                safesearch="moderate",
                max_results=max_results
            ))
            for item in raw_items:
                href = item.get("href") or item.get("link") or ""
                title = item.get("title") or ""
                body = item.get("body") or item.get("snippet") or ""
                if href and href.startswith("http"):
                    results.append({
                        "title": title,
                        "url": href,
                        "snippet": body,
                        "source": "duckduckgo_ddgs"
                    })
            if results:
                return results
    except Exception as e:
        logger.warning(f"ddgs package search failed: {e}. Falling back to HTML/RSS scraper.")

    # Prioritas 2: Fallback ke HTTP HTML Search jika ddgs error/rate-limit
    try:
        import requests
        from bs4 import BeautifulSoup
        from urllib.parse import unquote, parse_qs

        session = requests.Session()
        session.headers.update({
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7"
        })
        resp = session.post(
            "https://html.duckduckgo.com/html/",
            data={"q": query, "b": "", "kl": region},
            timeout=5.0
        )
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            for result in soup.select(".result"):
                a_tag = result.select_one(".result__title a")
                snip_tag = result.select_one(".result__snippet")
                if a_tag:
                    raw_href = a_tag.get("href", "")
                    parsed = urlparse(raw_href)
                    final_url = parse_qs(parsed.query).get("uddg", [raw_href])[0]
                    final_url = unquote(final_url)
                    if final_url.startswith("http"):
                        results.append({
                            "title": a_tag.get_text(strip=True),
                            "url": final_url,
                            "snippet": snip_tag.get_text(strip=True) if snip_tag else "",
                            "source": "duckduckgo_html"
                        })
                if len(results) >= max_results:
                    break
    except Exception as e:
        logger.warning(f"DuckDuckGo HTML fallback failed: {e}")

    return results


def mcp_search_social_events(
    query: str,
    year: str = "2027",
    platforms: Optional[List[str]] = None,
    max_results: int = 15
) -> List[Dict[str, Any]]:
    """Mencari konten event di platform media sosial (Instagram Reels, Facebook, TikTok)

    menggunakan targeted dorks via DuckDuckGo secara gratis.
    """
    if not platforms:
        platforms = ["instagram", "facebook", "tiktok"]

    all_social_results = []
    seen_urls = set()

    for platform in platforms:
        p_lower = platform.lower()
        if p_lower == "instagram":
            # Targetkan IG Reels dan Postingan Publik
            dork = f'(site:instagram.com/reel/ OR site:instagram.com/p/) {query} {year}'.strip()
        elif p_lower == "facebook":
            # Targetkan FB Events dan Public Posts
            dork = f'(site:facebook.com/events/ OR site:facebook.com) {query} {year}'.strip()
        elif p_lower == "tiktok":
            # Targetkan Video TikTok Publik
            dork = f'site:tiktok.com {query} {year}'.strip()
        elif p_lower == "linkedin":
            dork = f'site:linkedin.com/posts/ {query} {year}'.strip()
        else:
            dork = f'site:{p_lower}.com {query} {year}'.strip()

        logger.info(f"Executing Social MCP Search for {platform}: {dork}")
        raw_results = mcp_search_duckduckgo(dork, max_results=max_results)

        for res in raw_results:
            u = res.get("url", "")
            if not u or u in seen_urls:
                continue
            # Filter ketat Instagram: WAJIB link postingan (/p/) atau reels (/reel/), BUKAN sekadar profil akun atau halaman login!
            if p_lower == "instagram":
                if not ("/p/" in u or "/reel/" in u):
                    continue
                if any(bad in u.lower() for bad in ["/accounts/", "/signin", "/login", "/explore", "/tags/"]):
                    continue
            seen_urls.add(u)
            res["platform"] = p_lower
            all_social_results.append(res)

    return all_social_results


def scrape_with_requests_opengraph(url: str, timeout: int = 6) -> Dict[str, Any]:
    """Fallback stealth scraper menggunakan OpenGraph & metadata parser.

    Bekerja cepat dan andal untuk mengekstrak caption & tanggal dari URL Instagram & Facebook
    karena server media sosial mengirimkan OpenGraph lengkap untuk robot web.
    """
    import requests
    from bs4 import BeautifulSoup

    data = {
        "url": url,
        "title": "",
        "description": "",
        "content": "",
        "images": [],
        "success": False,
        "method": "requests_opengraph"
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "id,en;q=0.9"
    }

    try:
        resp = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            
            # Title
            og_title = soup.find("meta", property="og:title")
            title_text = og_title.get("content") if og_title else (soup.title.string if soup.title else "")
            data["title"] = title_text.strip() if title_text else ""

            # Description (Instagram Reels & Posts menyimpan full caption di og:description!)
            og_desc = soup.find("meta", property="og:description")
            if not og_desc:
                og_desc = soup.find("meta", attrs={"name": "description"})
            desc_text = og_desc.get("content") if og_desc else ""
            data["description"] = desc_text.strip() if desc_text else ""

            # Images
            og_img = soup.find("meta", property="og:image")
            if og_img and og_img.get("content"):
                data["images"].append(og_img.get("content"))

            # Clean body text
            for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
                tag.decompose()
            body_text = " ".join([p.get_text(strip=True) for p in soup.find_all(["p", "h1", "h2", "span"]) if len(p.get_text(strip=True)) > 20])
            
            combined_content = f"{data['title']}\n{data['description']}\n{body_text[:1500]}".strip()
            data["content"] = combined_content
            data["success"] = bool(data["title"] or data["description"])
    except Exception as e:
        logger.warning(f"OpenGraph fallback scraping failed for {url}: {e}")

    return data


def mcp_scrape_page_playwright(url: str, timeout_ms: int = 10000) -> Dict[str, Any]:
    """Headless Browser Scraper menggunakan Playwright (Chromium).

    Mengeksekusi JavaScript, me-render caption dinamis Instagram Reels / FB,
    dan mengambil teks halaman secara komprehensif.
    """
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            # Jalankan Chromium headless dengan stealth flags
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-gpu"
                ]
            )
            context = browser.new_context(
                user_agent=DEFAULT_USER_AGENT,
                viewport={"width": 1280, "height": 800},
                locale="id-ID"
            )
            # Hilangkan indikator navigator.webdriver agar tidak terdeteksi bot
            context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            page = context.new_page()
            page.set_default_timeout(timeout_ms)

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            except Exception as nav_e:
                logger.warning(f"Playwright navigation partial timeout for {url}: {nav_e}")

            # Tunggu elemen konten utama sebentar jika Instagram / Facebook
            try:
                page.wait_for_timeout(1500)
            except Exception:
                pass

            title = page.title()
            
            # Ekstrak OpenGraph & Description dari DOM
            og_desc = page.evaluate("""() => {
                const meta = document.querySelector('meta[property="og:description"]') || document.querySelector('meta[name="description"]');
                return meta ? meta.getAttribute('content') : '';
            }""")

            og_title = page.evaluate("""() => {
                const meta = document.querySelector('meta[property="og:title"]');
                return meta ? meta.getAttribute('content') : '';
            }""")

            # Ekstrak teks caption Instagram / FB post
            post_caption = page.evaluate("""() => {
                // Selektor artikel IG / FB
                const articles = document.querySelectorAll('article, div[role="main"], h1, h2, div[data-ad-preview="message"]');
                let texts = [];
                articles.forEach(el => {
                    const txt = el.innerText;
                    if (txt && txt.length > 20) texts.push(txt);
                });
                return texts.join('\\n');
            }""")

            full_text = page.evaluate("""() => {
                return document.body ? document.body.innerText.slice(0, 3000) : '';
            }""")

            # Jika target adalah halaman profil IG (bukan postingan langsung), ambil link postingan/reel pertama
            specific_post_url = page.evaluate("""() => {
                const href = window.location.href;
                if (href.includes("instagram.com") && !href.includes("/p/") && !href.includes("/reel/")) {
                    const a = document.querySelector('a[href*="/p/"], a[href*="/reel/"]');
                    return a ? a.href : null;
                }
                return null;
            }""")
            canonical_url = specific_post_url or url

            browser.close()

            combined = f"{og_title or title}\n{og_desc}\n{post_caption}\n{full_text}".strip()
            return {
                "url": canonical_url,
                "title": og_title or title,
                "description": og_desc or "",
                "content": combined[:3000],
                "success": True,
                "method": "playwright_chromium"
            }
    except Exception as e:
        logger.warning(f"Playwright execution failed for {url}: {e}. Triggering requests OpenGraph fallback...")
        return scrape_with_requests_opengraph(url)


def mcp_scrape_url(url: str) -> Dict[str, Any]:
    """Smart wrapper: Mencoba Playwright terlebih dahulu, jika gagal otomatis fallback ke Requests OpenGraph."""
    if not url or not url.startswith("http"):
        return {"url": url, "success": False, "content": "", "method": "invalid_url"}

    # Jalankan Playwright Scraper
    result = mcp_scrape_page_playwright(url)
    if result.get("success") and len(result.get("content", "")) > 50:
        return result

    # Jika konten Playwright minim (misal dicegat login wall), coba OpenGraph fallback
    og_res = scrape_with_requests_opengraph(url)
    if og_res.get("success") and len(og_res.get("content", "")) > len(result.get("content", "")):
        return og_res

    return result


# ============================================================================
# 2. STANDARD MODEL CONTEXT PROTOCOL (MCP) INTERFACE (JSON-RPC 2.0)
# ============================================================================

MCP_SERVER_INFO = {
    "name": "market-intelligence-mcp-server",
    "version": "1.0.0"
}

MCP_PROTOCOL_VERSION = "2024-11-05"

MCP_TOOLS_SPEC = [
    {
        "name": "duckduckgo_search",
        "description": "Pencarian web bebas biaya menggunakan DuckDuckGo tanpa API key (mendukung wilayah Indonesia).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Kata kunci pencarian"},
                "max_results": {"type": "integer", "description": "Batas jumlah hasil (default 15)", "default": 15},
                "region": {"type": "string", "description": "Kode wilayah (default 'id-id')", "default": "id-id"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "search_social_events",
        "description": "Mencari postingan dan reels di Instagram, Facebook, TikTok, dan LinkedIn untuk event/pameran/kejuaraan menggunakan targeted dorks bebas biaya.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Topik atau nama event (contoh: 'pameran tekstil', 'kejuaraan karate')"},
                "year": {"type": "string", "description": "Tahun target (contoh: '2027')", "default": "2027"},
                "platforms": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Daftar platform media sosial (instagram, facebook, tiktok, linkedin)"
                },
                "max_results": {"type": "integer", "description": "Jumlah maksimal per platform", "default": 10}
            },
            "required": ["query"]
        }
    },
    {
        "name": "playwright_scrape_url",
        "description": "Headless browser scraping menggunakan Playwright (Chromium) untuk me-render konten dinamis, reels Instagram, dan halaman Facebook.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL target yang akan di-scrape"}
            },
            "required": ["url"]
        }
    },
    {
        "name": "discover_social_events_pipeline",
        "description": "Pipeline end-to-end lengkap: Mencari postingan medsos via DuckDuckGo, mengunduh konten via Playwright, dan mengembalikan kumpulan snippet teks.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Kata kunci event"},
                "year": {"type": "string", "description": "Tahun target (misal: '2027')", "default": "2027"},
                "limit": {"type": "integer", "description": "Jumlah postingan yang akan di-scrape", "default": 10}
            },
            "required": ["query"]
        }
    },
    {
        "name": "search_google_maps_suppliers",
        "description": "Mencari toko bahan kain, sentra konveksi, garmen, dan supplier tekstil lokal langsung di Google Maps Web menggunakan Playwright secara 100% bebas biaya (tanpa API key).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Kata kunci supplier (misal: 'toko kain katun', 'konveksi jersey')"},
                "location": {"type": "string", "description": "Kota atau wilayah target (misal: 'Bandung', 'Surabaya')"},
                "limit": {"type": "integer", "description": "Jumlah maksimal supplier", "default": 10}
            },
            "required": ["query"]
        }
    }
]


class MarketIntelligenceMCPServer:
    """Implementasi Model Context Protocol (MCP) Server mandiri berbasis JSON-RPC 2.0."""

    @classmethod
    def list_tools(cls) -> List[Dict[str, Any]]:
        return MCP_TOOLS_SPEC

    @classmethod
    def call_tool(cls, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Eksekusi tool MCP sesuai nama dan parameter."""
        if name == "duckduckgo_search":
            q = arguments.get("query", "")
            limit = int(arguments.get("max_results", 15))
            reg = arguments.get("region", "id-id")
            data = mcp_search_duckduckgo(query=q, max_results=limit, region=reg)
            return {"content": [{"type": "text", "text": json.dumps(data, ensure_ascii=False)}]}

        elif name == "search_social_events":
            q = arguments.get("query", "")
            yr = str(arguments.get("year", "2027"))
            plats = arguments.get("platforms")
            limit = int(arguments.get("max_results", 10))
            data = mcp_search_social_events(query=q, year=yr, platforms=plats, max_results=limit)
            return {"content": [{"type": "text", "text": json.dumps(data, ensure_ascii=False)}]}

        elif name == "playwright_scrape_url":
            target_url = arguments.get("url", "")
            data = mcp_scrape_url(target_url)
            return {"content": [{"type": "text", "text": json.dumps(data, ensure_ascii=False)}]}

        elif name == "discover_social_events_pipeline":
            q = arguments.get("query", "")
            yr = str(arguments.get("year", "2027"))
            limit = int(arguments.get("limit", 8))
            
            # 1. Cari tautan medsos
            links = mcp_search_social_events(query=q, year=yr, max_results=limit)
            scraped_snippets = []
            
            # 2. Render dan scrape tiap URL dengan Playwright / OpenGraph
            for item in links[:limit]:
                u = item.get("url")
                if not u:
                    continue
                scraped = mcp_scrape_url(u)
                snippet_text = scraped.get("content") or item.get("snippet") or ""
                if len(snippet_text) > 30:
                    scraped_snippets.append({
                        "title": scraped.get("title") or item.get("title"),
                        "url": u,
                        "platform": item.get("platform", "social"),
                        "content": snippet_text,
                        "method": scraped.get("method")
                    })
            return {"content": [{"type": "text", "text": json.dumps(scraped_snippets, ensure_ascii=False)}]}

        elif name == "search_google_maps_suppliers":
            from app.services.google_maps_supplier_service import GoogleMapsSupplierService
            q = arguments.get("query", "")
            loc = arguments.get("location", "")
            lim = int(arguments.get("limit", 10))
            res = GoogleMapsSupplierService.search_places(query=q, location=loc, limit=lim)
            return {"content": [{"type": "text", "text": json.dumps(res, ensure_ascii=False)}]}

        else:
            raise ValueError(f"Unknown MCP tool: '{name}'")

    @classmethod
    def handle_jsonrpc_request(cls, request: Dict[str, Any]) -> Dict[str, Any]:
        """Memproses request JSON-RPC 2.0 sesuai spesifikasi MCP."""
        req_id = request.get("id")
        method = request.get("method")
        params = request.get("params") or {}

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": MCP_PROTOCOL_VERSION,
                    "serverInfo": MCP_SERVER_INFO,
                    "capabilities": {
                        "tools": {
                            "listChanged": False
                        }
                    }
                }
            }

        elif method == "notifications/initialized":
            return {}

        elif method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "tools": cls.list_tools()
                }
            }

        elif method == "tools/call":
            tool_name = params.get("name")
            tool_args = params.get("arguments") or {}
            try:
                result = cls.call_tool(tool_name, tool_args)
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": result
                }
            except Exception as e:
                logger.error(f"Error calling MCP tool {tool_name}: {e}")
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {
                        "code": -32603,
                        "message": str(e)
                    }
                }

        elif method == "ping":
            return {"jsonrpc": "2.0", "id": req_id, "result": {}}

        else:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: '{method}'"
                }
            }


# ============================================================================
# 3. CLI STDIN/STDOUT RUNNER FOR MCP HOSTS (Claude Desktop, Cursor, Antigravity)
# ============================================================================

def run_mcp_stdio_server():
    """Menjalankan server MCP standar melalui STDIN/STDOUT."""
    logger.info("Market Intelligence MCP Server is starting on stdio...")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            resp = MarketIntelligenceMCPServer.handle_jsonrpc_request(req)
            if resp:
                sys.stdout.write(json.dumps(resp) + "\n")
                sys.stdout.flush()
        except Exception as e:
            err_resp = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": f"Parse error: {e}"}
            }
            sys.stdout.write(json.dumps(err_resp) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    run_mcp_stdio_server()
