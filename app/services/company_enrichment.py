"""Company Data Enrichment Service (Phase 4.5).

Menyediakan enrichment layer modular untuk memperkaya Company Intelligence
dari entitas Master Organization (Single Source of Truth):
1. Website & Domain Discovery & Verification
2. Social Media Enrichment (Instagram, Facebook, LinkedIn)
3. Corporate Phone & Email Validation
4. Location Verification (Address, City, Province)
5. Employee Size Extraction
6. Granular Field-Level Provenance & Audit Trail
7. Source Precedence & Non-Destructive Safe Merge
8. Decision Classification (AUTO_ACCEPT, REVIEW, REJECT)
9. Rate Limiting, Caching, and Checkpointing / Resume Support.
"""

import os
import re
import json
import time
import logging
from datetime import datetime, timezone
from urllib.parse import urlparse, urljoin
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field

import requests
from bs4 import BeautifulSoup
from flask import current_app

from app.extensions import db
from app.models import Organization, DuplicateCandidate
from app.services.dedup_engine import (
    normalize_company_name,
    extract_domain,
    normalize_phone,
    DIRECTORY_AND_AGGREGATOR_DOMAINS,
    PUBLIC_EMAIL_DOMAINS,
    LEGAL_ENTITY_REGEX,
)

logger = logging.getLogger(__name__)

USER_AGENT = "SyamanahMarketIntelligence/1.0 (+https://syamanah.com/bot; company-enrichment)"
SOCIAL_HOSTS = ("instagram.com", "facebook.com", "linkedin.com")
TEMPLATE_EMAIL_DOMAINS = {
    "example.com", "example.org", "example.net",
    "domain.com", "yourdomain.com", "situs.com",
    "test.com", "sample.com", "email.com"
}

# Hirarki Prioritas Sumber (Source Precedence Hierarchy)
SOURCE_PRIORITY = {
    "official_website": 100,
    "official_social": 85,
    "government_institutional": 75,
    "bps_directory": 70,
    "trusted_directory": 55,
    "search_discovery": 40,
    "unverified_aggregator": 20,
    "unknown": 10
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class EnrichedField:
    value: Any
    source: str
    source_url: Optional[str] = None
    confidence: str = "medium"  # high, medium, low
    discovered_at: str = field(default_factory=utc_now_iso)


@dataclass
class EnrichmentResult:
    organization_id: int
    company_name: str
    decision: str  # AUTO_ACCEPT, REVIEW, REJECT, NO_DATA
    fields_updated: List[str] = field(default_factory=list)
    fields_rejected: List[str] = field(default_factory=list)
    review_reasons: List[str] = field(default_factory=list)
    candidate_data: Dict[str, Any] = field(default_factory=dict)
    elapsed_seconds: float = 0.0


class CompanyEnrichmentService:
    """Service modular untuk memproses pengayaan data Company Intelligence secara batch,
    idempotent, aman, dengan audit provenance per-field."""

    def __init__(
        self,
        cache_file: str = "instance/enrichment_cache.json",
        state_file: str = "instance/enrichment_state.json",
        rate_limit_delay: float = 0.2,
        timeout: int = 8
    ):
        self.cache_file = cache_file
        self.state_file = state_file
        self.rate_limit_delay = rate_limit_delay
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        self._load_cache()

    def _load_cache(self):
        self.cache = {}
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    self.cache = json.load(f)
            except Exception:
                self.cache = {}

    def _save_cache(self):
        try:
            os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Gagal menyimpan cache enrichment: {e}")

    # =========================================================================
    # 1. CANDIDATE DISCOVERY & VALIDATION
    # =========================================================================

    def _clean_company_tokens(self, name: str) -> List[str]:
        """Menghasilkan kata-kata kunci unik dari nama perusahaan untuk pencarian domain."""
        norm = normalize_company_name(name)
        tokens = [t for t in norm.split() if len(t) > 2 and t not in (
            "indonesia", "nusantara", "jaya", "abadi", "makmur", "utama", "mandiri", "persada", "sejahtera"
        )]
        return tokens or [t for t in norm.split() if len(t) > 1]

    def _generate_candidate_domains(self, name: str) -> List[str]:
        """Menghasilkan hipotesis domain resmi berdasarkan pola korporat Indonesia."""
        norm = normalize_company_name(name)
        tokens = norm.split()
        if not tokens:
            return []

        candidates = []
        clean_full = "".join(tokens)
        hyphen_full = "-".join(tokens)

        # Pola umum korporat Indonesia
        candidates.append(f"{clean_full}.co.id")
        candidates.append(f"{clean_full}.com")
        candidates.append(f"{clean_full}.id")
        if len(tokens) > 1:
            candidates.append(f"{hyphen_full}.co.id")
            candidates.append(f"{hyphen_full}.com")

        # Jika ada singkatan atau kata utama
        if len(tokens) >= 2:
            main_word = tokens[0]
            if len(main_word) >= 4:
                candidates.append(f"{main_word}.co.id")
                candidates.append(f"{main_word}.com")

        return candidates

    def _verify_website(self, url: str, expected_company_name: str) -> Tuple[bool, Optional[str], Optional[BeautifulSoup], str]:
        """Memverifikasi bahwa website target aktif, bukan redirect ISP/captive portal,
        dan memiliki relevansi tekstual dengan perusahaan yang dituju.
        Mengembalikan: (is_valid, final_url, soup, reason)
        """
        if not url:
            return False, None, None, "URL kosong"

        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        parsed = urlparse(url)
        host = (parsed.netloc or "").split(":")[0].lower()
        if host.startswith("www."):
            host = host[4:]

        if host in DIRECTORY_AND_AGGREGATOR_DOMAINS or host in PUBLIC_EMAIL_DOMAINS:
            return False, None, None, f"Domain '{host}' adalah direktori/aggregator publik"

        if any(bad in host for bad in ("internetbaik", "mercusuar", "telkomsel", "u-ad.info")):
            return False, None, None, "Terdeteksi redirect captive portal / ISP block"

        # Cek Cache
        cache_key = f"web:{host}"
        if cache_key in self.cache:
            c_data = self.cache[cache_key]
            if not c_data.get("is_valid"):
                return False, None, None, c_data.get("reason", "Cached invalid")

        try:
            resp = self.session.get(url, timeout=self.timeout, allow_redirects=True)
            if resp.status_code != 200:
                self.cache[cache_key] = {"is_valid": False, "reason": f"Status {resp.status_code}"}
                return False, None, None, f"HTTP Status {resp.status_code}"

            final_url = resp.url
            final_host = urlparse(final_url).netloc.lower()
            if any(bad in final_host for bad in ("internetbaik", "mercusuar", "telkomsel")):
                self.cache[cache_key] = {"is_valid": False, "reason": "Redirected to ISP block"}
                return False, None, None, "Redirected to ISP block"

            soup = BeautifulSoup(resp.text, "html.parser")
            for tag in soup(["script", "style", "noscript", "svg"]):
                tag.decompose()

            # Verifikasi keterkaitan identitas perusahaan (Token Overlap)
            page_text = " ".join(soup.get_text(" ").split()).lower()
            page_title = (soup.title.string if soup.title else "").lower()
            tokens = self._clean_company_tokens(expected_company_name)

            # Hitung kecocokan token
            matched_tokens = [t for t in tokens if t in page_text or t in page_title or t in final_host]
            match_ratio = len(matched_tokens) / len(tokens) if tokens else 0.0

            if match_ratio >= 0.5 or (tokens and tokens[0] in final_host):
                self.cache[cache_key] = {"is_valid": True, "final_url": final_url}
                return True, final_url, soup, f"Verified (Token match: {len(matched_tokens)}/{len(tokens)})"
            else:
                self.cache[cache_key] = {"is_valid": False, "reason": f"Low token match ratio ({match_ratio:.2f})"}
                return False, final_url, soup, f"Token match tidak mencukupi ({match_ratio:.2f})"

        except Exception as e:
            self.cache[cache_key] = {"is_valid": False, "reason": str(e)}
            return False, None, None, f"Connection error: {e}"

    # =========================================================================
    # 2. FIELD EXTRACTION FROM VERIFIED PAGE
    # =========================================================================

    def _extract_page_intelligence(self, final_url: str, soup: BeautifulSoup) -> Dict[str, Any]:
        """Mengekstrak profil intelijen dari konten web resmi yang telah diverifikasi."""
        extracted = {
            "emails": [],
            "phones": [],
            "social": {},
            "address": None,
            "city": None,
            "province": None,
            "employee_size": None,
            "description": None,
        }

        # 1. Ekstraksi Structured Data (JSON-LD)
        for script in soup.select('script[type="application/ld+json"]'):
            try:
                data = json.loads(script.string or script.get_text())
                items = data if isinstance(data, list) else [data]
                for item in items:
                    if isinstance(item, dict):
                        addr = item.get("address")
                        if isinstance(addr, dict):
                            if addr.get("streetAddress") and not extracted["address"]:
                                extracted["address"] = str(addr["streetAddress"]).strip()
                            if addr.get("addressLocality") and not extracted["city"]:
                                extracted["city"] = str(addr["addressLocality"]).strip()
                            if addr.get("addressRegion") and not extracted["province"]:
                                extracted["province"] = str(addr["addressRegion"]).strip()
                        if item.get("telephone") and not extracted["phones"]:
                            extracted["phones"].append(str(item["telephone"]).strip())
                        if item.get("email") and not extracted["emails"]:
                            extracted["emails"].append(str(item["email"]).strip())
                        if item.get("numberOfEmployees") and not extracted["employee_size"]:
                            emp = item.get("numberOfEmployees")
                            extracted["employee_size"] = str(emp.get("value") if isinstance(emp, dict) else emp).strip()
            except Exception:
                continue

        # 2. Ekstraksi Link Media Sosial Resmi dari Halaman
        for a in soup.select("a[href]"):
            href = a.get("href", "").strip()
            if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
                continue
            try:
                full_href = urljoin(final_url, href)
                clean_url = full_href.split("?")[0].rstrip("/")
                u_low = clean_url.lower()

                if "instagram.com" in u_low and not extracted["social"].get("instagram"):
                    path_parts = [p for p in urlparse(clean_url).path.split("/") if p]
                    if path_parts and path_parts[0] not in ("p", "reel", "explore", "stories"):
                        extracted["social"]["instagram"] = clean_url
                elif "facebook.com" in u_low and not extracted["social"].get("facebook"):
                    path_parts = [p for p in urlparse(clean_url).path.split("/") if p]
                    if path_parts and path_parts[0] not in ("share", "sharer", "dialog", "intent"):
                        extracted["social"]["facebook"] = clean_url
                elif "linkedin.com" in u_low and not extracted["social"].get("linkedin"):
                    if "/company/" in u_low or "/school/" in u_low:
                        extracted["social"]["linkedin"] = clean_url
            except Exception:
                continue

        # 3. Ekstraksi Email & Telepon Regex dari Teks
        page_text = " ".join(soup.get_text(" ").split())
        raw_emails = re.findall(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", page_text, re.IGNORECASE)
        domain = extract_domain(final_url)

        # Prioritaskan email korporat yang berakhiran domain perusahaan
        corp_emails = []
        other_emails = []
        for em in raw_emails:
            em_clean = em.strip().lower()
            if any(em_clean.endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".gif", ".webp")):
                continue
            em_host = em_clean.split("@")[-1]
            if em_host in TEMPLATE_EMAIL_DOMAINS or any(p in em_clean for p in ("example.", "sample.", "domain.com", "yourdomain")):
                continue
            if domain and domain in em_clean:
                corp_emails.append(em_clean)
            elif em_host not in PUBLIC_EMAIL_DOMAINS:
                other_emails.append(em_clean)

        extracted["emails"] = list(dict.fromkeys(extracted["emails"] + corp_emails + other_emails))[:3]

        # Telepon Indonesia (+62 / 021 / (021) / 0...)
        raw_phones = re.findall(r"\(?(?:\+62|62|0)(?:21|22|24|31|274|271|61|711|\d{2,3})\)?[\s().-]?\d{3,4}[\s().-]?\d{3,5}", page_text)
        clean_phones = []
        for ph in raw_phones:
            p_norm = normalize_phone(ph)
            if p_norm and len(p_norm) >= 9:
                clean_phones.append(p_norm)
        
        json_ld_phones = [normalize_phone(p) for p in extracted["phones"] if normalize_phone(p)]
        extracted["phones"] = list(dict.fromkeys(json_ld_phones + clean_phones))[:3]

        # 4. Deskripsi / Meta Description
        meta_desc = soup.select_one('meta[name="description"], meta[property="og:description"]')
        if meta_desc and meta_desc.get("content"):
            extracted["description"] = meta_desc["content"].strip()[:500]

        return extracted

    # =========================================================================
    # 3. PROVENANCE MANAGEMENT (PER-FIELD & MERGE LOG)
    # =========================================================================

    def _get_provenance_store(self, org: Organization) -> Dict[str, Any]:
        """Membaca store provenance terstruktur yang mendukung merge history & per-field provenance."""
        if not org.provenance_json:
            return {"merge_history": [], "fields": {}}
        try:
            parsed = json.loads(org.provenance_json)
            if isinstance(parsed, list):
                # Migrasi dari list format lama ke dict format terstruktur
                return {"merge_history": parsed, "fields": {}}
            elif isinstance(parsed, dict):
                if "merge_history" not in parsed:
                    parsed["merge_history"] = []
                if "fields" not in parsed:
                    parsed["fields"] = {}
                return parsed
        except Exception:
            return {"merge_history": [], "fields": {}}
        return {"merge_history": [], "fields": {}}

    def _can_update_field(self, current_val: Any, current_source: str, incoming_val: Any, incoming_source: str) -> bool:
        """Menentukan apakah field boleh di-update berdasarkan aturan Source Precedence & Non-Destructive."""
        # 1. Jika nilai baru kosong -> REJECT
        if not incoming_val or str(incoming_val).strip() in ("", "None", "nan", "-", "null", "N/A"):
            return False

        # 2. Jika nilai saat ini kosong -> ALLOW
        if not current_val or str(current_val).strip() in ("", "None", "nan", "-", "null", "N/A"):
            return True

        # 3. Jika nilai sama persis -> NOOP
        if str(current_val).strip().lower() == str(incoming_val).strip().lower():
            return False

        # 4. Jika nilai saat ini sudah ada, hanya boleh di-override jika incoming_source memiliki prioritas lebih tinggi
        curr_prio = SOURCE_PRIORITY.get(current_source, 10)
        inc_prio = SOURCE_PRIORITY.get(incoming_source, 10)
        return inc_prio > curr_prio

    # =========================================================================
    # 4. CORE SINGLE-ORGANIZATION ENRICHMENT
    # =========================================================================

    def enrich_organization(self, org: Organization, dry_run: bool = False) -> EnrichmentResult:
        """Memproses enrichment untuk satu entitas Organization Master.
        Menghasilkan EnrichmentResult dengan status AUTO_ACCEPT, REVIEW, atau REJECT.
        """
        start_time = time.time()
        res = EnrichmentResult(organization_id=org.id, company_name=org.name, decision="NO_DATA")

        # Cek apakah organisasi sudah memiliki website resmi
        verified_url = None
        soup = None
        target_website = org.website

        # Jika website sudah ada, validasi langsung
        if target_website and str(target_website).strip() not in ("nan", "none", "-", ""):
            is_valid, v_url, s_obj, reason = self._verify_website(target_website, org.name)
            if is_valid:
                verified_url = v_url
                soup = s_obj
            else:
                res.review_reasons.append(f"Existing website '{target_website}' failed verification: {reason}")

        # Jika website belum ada / tidak valid, coba generate kandidat domain resmi
        if not verified_url:
            candidate_domains = self._generate_candidate_domains(org.name)
            for cand_dom in candidate_domains:
                time.sleep(self.rate_limit_delay)
                is_valid, v_url, s_obj, reason = self._verify_website(f"https://www.{cand_dom}", org.name)
                if not is_valid:
                    is_valid, v_url, s_obj, reason = self._verify_website(f"http://{cand_dom}", org.name)
                if is_valid:
                    verified_url = v_url
                    soup = s_obj
                    break

        # Jika tidak ditemukan website yang valid
        if not verified_url or not soup:
            res.decision = "REVIEW" if res.review_reasons else "NO_DATA"
            res.elapsed_seconds = round(time.time() - start_time, 3)
            return res

        # Ekstraksi informasi dari website resmi yang terverifikasi
        try:
            page_intel = self._extract_page_intelligence(verified_url, soup)
        except Exception as e:
            logger.warning(f"Error extracting page intelligence from {verified_url}: {e}")
            page_intel = {"emails": [], "phones": [], "social": {}, "address": None, "city": None, "province": None, "employee_size": None, "description": None}
        res.candidate_data = page_intel

        # Baca store provenance
        prov_store = self._get_provenance_store(org)
        fields_store = prov_store["fields"]
        now_str = utc_now_iso()
        is_modified = False

        # --- A. Website & Domain ---
        dom = extract_domain(verified_url)
        if self._can_update_field(org.website, fields_store.get("website", {}).get("source", "bps"), verified_url, "official_website"):
            if not dry_run:
                org.website = verified_url
                org.domain = dom
            fields_store["website"] = {"value": verified_url, "source": "official_website", "source_url": verified_url, "confidence": "high", "discovered_at": now_str}
            fields_store["domain"] = {"value": dom, "source": "official_website", "source_url": verified_url, "confidence": "high", "discovered_at": now_str}
            res.fields_updated.extend(["website", "domain"])
            is_modified = True

        # --- B. Phone ---
        if page_intel.get("phones"):
            best_phone = page_intel["phones"][0]
            if self._can_update_field(org.phone, fields_store.get("phone", {}).get("source", "bps"), best_phone, "official_website"):
                if not dry_run:
                    org.phone = best_phone
                fields_store["phone"] = {"value": best_phone, "source": "official_website", "source_url": verified_url, "confidence": "high", "discovered_at": now_str}
                res.fields_updated.append("phone")
                is_modified = True

        # --- C. Email ---
        if page_intel.get("emails"):
            best_email = page_intel["emails"][0]
            if self._can_update_field(org.email, fields_store.get("email", {}).get("source", "bps"), best_email, "official_website"):
                if not dry_run:
                    org.email = best_email
                fields_store["email"] = {"value": best_email, "source": "official_website", "source_url": verified_url, "confidence": "high", "discovered_at": now_str}
                res.fields_updated.append("email")
                is_modified = True

        # --- D. Address / City / Province ---
        if page_intel.get("address"):
            addr_val = page_intel["address"]
            if self._can_update_field(org.address, fields_store.get("address", {}).get("source", "bps"), addr_val, "official_website"):
                if not dry_run:
                    org.address = addr_val
                fields_store["address"] = {"value": addr_val, "source": "official_website", "source_url": verified_url, "confidence": "high", "discovered_at": now_str}
                res.fields_updated.append("address")
                is_modified = True

        if page_intel.get("city"):
            city_val = page_intel["city"]
            if self._can_update_field(org.city, fields_store.get("city", {}).get("source", "bps"), city_val, "official_website"):
                if not dry_run:
                    org.city = city_val
                fields_store["city"] = {"value": city_val, "source": "official_website", "source_url": verified_url, "confidence": "high", "discovered_at": now_str}
                res.fields_updated.append("city")
                is_modified = True

        if page_intel.get("province"):
            prov_val = page_intel["province"]
            if self._can_update_field(org.province, fields_store.get("province", {}).get("source", "bps"), prov_val, "official_website"):
                if not dry_run:
                    org.province = prov_val
                fields_store["province"] = {"value": prov_val, "source": "official_website", "source_url": verified_url, "confidence": "high", "discovered_at": now_str}
                res.fields_updated.append("province")
                is_modified = True

        # --- E. Social Media (Non-Destructive Safe Merge) ---
        new_socials = page_intel.get("social", {})
        curr_socials = {}
        if org.social_json:
            try:
                curr_socials = json.loads(org.social_json) if isinstance(json.loads(org.social_json), dict) else {}
            except Exception:
                curr_socials = {}

        social_updated = False
        for platform in ("instagram", "facebook", "linkedin"):
            if new_socials.get(platform):
                new_u = new_socials[platform]
                curr_u = curr_socials.get(platform)
                if not curr_u or str(curr_u).strip() in ("", "None", "nan", "-"):
                    curr_socials[platform] = new_u
                    fields_store[f"social_{platform}"] = {
                        "value": new_u, "source": "official_website", "source_url": verified_url, "confidence": "high", "discovered_at": now_str
                    }
                    social_updated = True
                    res.fields_updated.append(f"social_{platform}")

        if social_updated:
            if not dry_run:
                org.social_json = json.dumps(curr_socials, ensure_ascii=False)
            is_modified = True

        # --- F. Description ---
        if page_intel.get("description") and not org.description:
            desc_val = page_intel["description"]
            if not dry_run:
                org.description = desc_val
            fields_store["description"] = {"value": desc_val, "source": "official_website", "source_url": verified_url, "confidence": "high", "discovered_at": now_str}
            res.fields_updated.append("description")
            is_modified = True

        # Simpan kembali provenance terstruktur
        if is_modified and not dry_run:
            prov_store["merge_history"].append({
                "source_type": "official_website_discovery",
                "source_url": verified_url,
                "fields_enriched": res.fields_updated,
                "confidence": 0.95,
                "merged_at": now_str
            })
            org.provenance_json = json.dumps(prov_store, ensure_ascii=False)
            org.last_seen = datetime.now(timezone.utc).replace(tzinfo=None)
            org.data_freshness = org.last_seen

        res.decision = "AUTO_ACCEPT" if res.fields_updated else "NO_DATA"
        res.elapsed_seconds = round(time.time() - start_time, 3)
        return res

    # =========================================================================
    # 5. BATCH RUNNER WITH RESUME & AUDIT METRICS
    # =========================================================================

    def run_batch(
        self,
        limit: int = 50,
        offset: int = 0,
        dry_run: bool = False,
        resume: bool = True,
        organization_ids: Optional[List[int]] = None
    ) -> Dict[str, Any]:
        """Menjalankan batch enrichment terhadap N master organization.
        Menyimpan checkpoint ke state_file agar dapat di-resume jika terjadi interupsi.
        """
        start_time = time.time()
        start_id = 0
        if resume and os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    state = json.load(f)
                    start_id = state.get("last_processed_id", 0)
            except Exception:
                start_id = 0

        # Ambil organisasi master yang belum lengkap websitenya atau kontak
        if organization_ids:
            target_orgs = Organization.query.filter(
                Organization.id.in_(organization_ids)
            ).order_by(Organization.id).limit(limit).all()
        else:
            query = Organization.query.filter(
                Organization.source_type == "bps_upload",
                Organization.id >= start_id
            ).order_by(Organization.id)
            target_orgs = query.offset(offset).limit(limit).all()

        report = {
            "organizations_processed": 0,
            "auto_accepted": 0,
            "review_candidates": 0,
            "no_data": 0,
            "rejected": 0,
            "website_found": 0,
            "domain_found": 0,
            "social_found": 0,
            "phone_found": 0,
            "email_found": 0,
            "address_found": 0,
            "employee_size_found": 0,
            "errors": 0,
            "retries": 0,
            "cache_hits": 0,
            "last_processed_id": start_id,
            "elapsed_seconds": 0.0,
            "details": []
        }

        for org in target_orgs:
            report["organizations_processed"] += 1
            report["last_processed_id"] = org.id
            try:
                res = self.enrich_organization(org, dry_run=dry_run)
                report["details"].append({
                    "org_id": org.id,
                    "name": org.name,
                    "decision": res.decision,
                    "fields_updated": res.fields_updated,
                    "review_reasons": res.review_reasons,
                })

                if res.decision == "AUTO_ACCEPT":
                    report["auto_accepted"] += 1
                    for f in res.fields_updated:
                        if f == "website": report["website_found"] += 1
                        elif f == "domain": report["domain_found"] += 1
                        elif "social" in f: report["social_found"] += 1
                        elif f == "phone": report["phone_found"] += 1
                        elif f == "email": report["email_found"] += 1
                        elif f in ("address", "city", "province"): report["address_found"] += 1
                        elif f == "employee_size": report["employee_size_found"] += 1
                elif res.decision == "REVIEW":
                    report["review_candidates"] += 1
                    # Catat ke DuplicateCandidate jika belum ada (Idempotent)
                    if not dry_run and res.review_reasons:
                        existing_cand = DuplicateCandidate.query.filter_by(
                            organization_id=org.id,
                            candidate_source="company_enrichment_review"
                        ).first()
                        if not existing_cand:
                            cand = DuplicateCandidate(
                                organization_id=org.id,
                                candidate_name=org.name,
                                candidate_source="company_enrichment_review",
                                candidate_payload_json=json.dumps(res.candidate_data, ensure_ascii=False),
                                match_tier="tier4_fuzzy_candidate",
                                confidence_score=0.6,
                                status="pending"
                            )
                            db.session.add(cand)
                else:
                    report["no_data"] += 1

                if not dry_run:
                    db.session.commit()

            except Exception as e:
                report["errors"] += 1
                if not dry_run:
                    db.session.rollback()
                logger.error(f"Error enriching org #{org.id}: {e}")

            # Simpan state checkpoint secara berkala
            if not dry_run and report["organizations_processed"] % 10 == 0:
                self._save_state(report["last_processed_id"])
                self._save_cache()

        if not dry_run:
            self._save_state(report["last_processed_id"])
            self._save_cache()

        report["elapsed_seconds"] = round(time.time() - start_time, 2)
        return report

    def _save_state(self, last_id: int):
        try:
            os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump({"last_processed_id": last_id, "updated_at": utc_now_iso()}, f, indent=2)
        except Exception as e:
            logger.warning(f"Gagal menyimpan state checkpoint: {e}")
