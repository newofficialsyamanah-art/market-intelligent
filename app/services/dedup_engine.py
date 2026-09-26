"""Deduplication & Identity Resolution Engine.

Menyediakan engine resolusi identitas entitas perusahaan / organisasi untuk Market Intelligence.
Prinsip utama:
1. `organizations` adalah Master Single Source of Truth.
2. Tidak melakukan destructive merge otomatis hanya karena kemiripan fuzzy.
3. Matching Signals:
   - Tier 1: Corporate Domain Match (Strongest match signal)
   - Tier 2: Normalized Legal Name + Wilayah Match (Strong match signal)
   - Tier 3: Corporate Contact Match (Supporting match signal)
   - Tier 4: Fuzzy Name Similarity (Fuzzy candidate match -> Candidate / Review jika confidence tidak cukup tinggi)
4. Audit & Provenance lengkap pada setiap entitas yang digabungkan.
5. Idempotent: menjalankan resolusi berulang kali pada dataset yang sama tidak menimbulkan duplikasi atau perubahan kumulatif.
"""

import re
import json
import logging
from datetime import datetime, timezone
from urllib.parse import urlparse
from difflib import SequenceMatcher
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple, Any

from app.models import Organization, DuplicateCandidate
from app.extensions import db

logger = logging.getLogger(__name__)

# Daftar akhiran & awalan badan hukum di Indonesia dan internasional
LEGAL_ENTITY_REGEX = re.compile(
    r"\b("
    r"PT|P\.T|PERSEROAN TERBATAS|"
    r"CV|C\.V|COMMANDITAIRE VENNOOTSCHAP|"
    r"UD|U\.D|USAHA DAGANG|"
    r"TBK|T\.B\.K|TERBUKA|"
    r"PERSERO|PERUM|PERJAN|"
    r"YAYASAN|KOPERASI|KOP|"
    r"PD|P\.D|PERUSAHAAN DAERAH|"
    r"PO|P\.O|PERUSAHAAN OTOBUS|"
    r"NV|N\.V|FA|FIRMA|"
    r"INC|CORP|CORPORATION|LTD|LIMITED|LLC|LLP|GMBH|CO|CO\."
    r")\b",
    re.IGNORECASE,
)

# Domain penyedia email publik / gratis (tidak boleh dipakai untuk corporate domain matching)
PUBLIC_EMAIL_DOMAINS = {
    "gmail.com", "yahoo.com", "yahoo.co.id", "hotmail.com", "outlook.com",
    "ymail.com", "icloud.com", "rocketmail.com", "live.com", "zoho.com",
    "mail.com", "aol.com", "protonmail.com", "tutanota.com"
}

# Domain aggregator / direktori / marketplace / instansi yang bukan domain privat perusahaan tunggal
DIRECTORY_AND_AGGREGATOR_DOMAINS = {
    "dnb.com", "indonetwork.co.id", "indotrading.com", "yellowpages.co.id",
    "kemendag.go.id", "kemenperin.go.id", "bps.go.id", "kemenkeu.go.id",
    "kompass.com", "indonesia-product.com", "indotrade.co.id", "tokopedia.com",
    "shopee.co.id", "bukalapak.com", "lazada.co.id", "blibli.com", "alibaba.com",
    "facebook.com", "instagram.com", "linkedin.com", "twitter.com", "x.com",
    "youtube.com", "tiktok.com", "pinterest.com", "medium.com", "blogspot.com",
    "wordpress.com", "wixsite.com", "github.com", "google.com", "bing.com",
    "duckduckgo.com", "volza.com", "companyhouse.id", "companieshouse.id",
    "companiesfacts.id", "daftarperusahaan.com", "semuabis.com", "emis.com",
    "freight-world.com.au", "info-clipper.com", "go4worldbusiness.com",
    "datanyze.com", "sini.id", "opencorpdata.com", "jobstreet.com",
    "disb2b.com", "databasesets.com", "soundcloud.com"
}

# Prefiks wilayah yang diabaikan saat normalisasi
LOCATION_PREFIX_REGEX = re.compile(r"\b(KOTA|KABUPATEN|KAB|PROVINSI|PROV)\b\.?", re.IGNORECASE)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# =========================================================================
# A. IDENTITY NORMALIZATION
# =========================================================================

def normalize_company_name(name: Optional[str]) -> str:
    """Menormalisasi nama perusahaan menjadi format standar perbandingan:
    1. Menghapus awalan/akhiran badan hukum (PT, CV, UD, Tbk, Persero, dll).
    2. Menghapus tanda baca, simbol, tanda kurung.
    3. Mengubah menjadi huruf kecil (lowercase).
    4. Menggabungkan whitespace ganda.
    
    Contoh:
    'PT. INDOFOOD SUKSES MAKMUR TBK' -> 'indofood sukses makmur'
    'PAPANDAYAN COCOA INDUSTRIES, PT' -> 'papandayan cocoa industries'
    'CV. ABADI TEXTILE (BANDUNG)' -> 'abadi textile bandung'
    """
    if not name or not isinstance(name, str):
        return ""
    
    cleaned = name.strip()
    
    # 1. Hapus tanda kurung tetapi pertahankan isinya sebagai token
    cleaned = cleaned.replace("(", " ").replace(")", " ")
    
    # 2. Hapus badan hukum dengan regex
    cleaned = LEGAL_ENTITY_REGEX.sub(" ", cleaned)
    
    # 3. Hapus tanda baca dan karakter khusus (hanya huruf, angka, dan spasi)
    cleaned = re.sub(r"[^\w\s]", " ", cleaned)
    
    # 4. Hapus sisa-sisa badan hukum jika masih ada setelah tanda baca dihapus
    cleaned = LEGAL_ENTITY_REGEX.sub(" ", cleaned)
    
    # 5. Lowercase dan bersihkan spasi
    tokens = [t.lower() for t in cleaned.split() if t.strip()]
    return " ".join(tokens)


def extract_domain(url_or_email: Optional[str]) -> Optional[str]:
    """Mengekstrak root corporate domain dari URL atau email.
    Mengabaikan domain email publik seperti gmail, yahoo, dll.
    
    Contoh:
    'https://www.panbrothers.co.id/contact' -> 'panbrothers.co.id'
    'info@garmenindah.com' -> 'garmenindah.com'
    'marketing@gmail.com' -> None (karena public email)
    """
    if not url_or_email or not isinstance(url_or_email, str):
        return None
    
    text = url_or_email.strip().lower()
    if not text or text in ("nan", "none", "-", "null"):
        return None
    
    # Jika email
    if "@" in text:
        parts = text.split("@")
        if len(parts) >= 2:
            candidate_domain = parts[-1].strip().lower()
            if candidate_domain in PUBLIC_EMAIL_DOMAINS or candidate_domain in DIRECTORY_AND_AGGREGATOR_DOMAINS:
                return None
            return candidate_domain
        return None
    
    # Jika URL
    if not text.startswith(("http://", "https://")):
        text = "http://" + text
        
    try:
        parsed = urlparse(text)
        host = (parsed.netloc or "").split(":")[0].strip().lower()
        if host.startswith("www."):
            host = host[4:]
        if not host or "." not in host or host in PUBLIC_EMAIL_DOMAINS or host in DIRECTORY_AND_AGGREGATOR_DOMAINS:
            return None
        return host
    except Exception:
        return None


def normalize_phone(phone: Optional[str]) -> Optional[str]:
    """Menstandarkan nomor telepon kantor ke format digit murni.
    Menghilangkan karakter spasi, tanda minus, tanda kurung.
    Mengubah awalan +62 atau 62 menjadi 0.
    """
    if not phone or not isinstance(phone, str):
        return None
    
    digits = re.sub(r"[^\d]", "", phone.strip())
    if not digits:
        return None
        
    # Ubah format internasional 62... -> 0...
    if digits.startswith("62") and len(digits) > 8:
        digits = "0" + digits[2:]
        
    # Minimal panjang nomor telepon valid
    if len(digits) < 6 or digits in ("000000", "123456"):
        return None
        
    return digits


def normalize_location(city: Optional[str], province: Optional[str]) -> Tuple[str, str]:
    """Menstandarkan nama kota/kabupaten dan provinsi."""
    c_clean = ""
    p_clean = ""
    
    if city and isinstance(city, str):
        c_clean = LOCATION_PREFIX_REGEX.sub(" ", city.strip())
        c_clean = re.sub(r"[^\w\s]", " ", c_clean).strip().lower()
        c_clean = " ".join(c_clean.split())
        if c_clean in ("nan", "none", "null", "-", ""):
            c_clean = ""
        
    if province and isinstance(province, str):
        p_clean = LOCATION_PREFIX_REGEX.sub(" ", province.strip())
        p_clean = re.sub(r"[^\w\s]", " ", p_clean).strip().lower()
        p_clean = " ".join(p_clean.split())
        if p_clean in ("nan", "none", "null", "-", ""):
            p_clean = ""
        
    return c_clean, p_clean


def calculate_fuzzy_ratio(str1: str, str2: str) -> float:
    """Menghitung skor kemiripan komposit antara dua string normalisasi:
    Menggunakan Standard Token Set Ratio (toleran urutan dan subset kata) serta Sequence Matcher.
    """
    if not str1 or not str2:
        return 0.0
    if str1 == str2:
        return 1.0

    t1 = set(str1.split())
    t2 = set(str2.split())
    intersection = t1.intersection(t2)
    diff1 = t1 - intersection
    diff2 = t2 - intersection

    inter_str = " ".join(sorted(list(intersection)))
    d1_str = " ".join(sorted(list(diff1)))
    d2_str = " ".join(sorted(list(diff2)))

    base = inter_str.strip()
    s1_sort = (inter_str + " " + d1_str).strip()
    s2_sort = (inter_str + " " + d2_str).strip()

    r1 = SequenceMatcher(None, base, s1_sort).ratio() if base and s1_sort else 0.0
    r2 = SequenceMatcher(None, base, s2_sort).ratio() if base and s2_sort else 0.0
    r3 = SequenceMatcher(None, s1_sort, s2_sort).ratio() if s1_sort and s2_sort else 0.0
    seq_ratio = SequenceMatcher(None, str1, str2).ratio()

    return max(r1, r2, r3, seq_ratio)



# =========================================================================
# B, C, D. MATCHING SIGNALS & DECISION MATRIX
# =========================================================================

@dataclass
class MatchResult:
    decision: str  # 'auto_match', 'review_candidate', 'unmatched'
    tier: Optional[str]  # 'tier1_domain', 'tier2_name_location', 'tier3_contact', 'tier4_fuzzy_candidate', None
    confidence: float  # 0.0 - 1.0
    signal_strength: str  # 'STRONGEST', 'STRONG', 'SUPPORTING', 'CANDIDATE', 'NONE'
    matched_org: Optional[Organization] = None
    reason: str = ""


class IdentityResolutionEngine:
    """Mesin Resolusi Identitas & Deduplikasi Cerdas berbasis In-Memory Indexing.
    Mendukung resolusi cepat untuk dataset skala ribuan hingga puluhan ribu record.
    """

    def __init__(self, existing_orgs: Optional[List[Organization]] = None):
        self.orgs: List[Organization] = []
        self.domain_index: Dict[str, Organization] = {}
        self.name_location_index: Dict[Tuple[str, str], List[Organization]] = {}
        self.normalized_name_index: Dict[str, List[Organization]] = {}
        self.phone_index: Dict[str, Organization] = {}
        self.first_token_index: Dict[str, List[Organization]] = {}
        self.two_token_index: Dict[Tuple[str, str], List[Organization]] = {}
        
        if existing_orgs:
            for org in existing_orgs:
                self.index_organization(org)

    def index_organization(self, org: Organization):
        """Mendaftarkan entitas Organization ke dalam indeks pencarian in-memory."""
        self.orgs.append(org)
        
        # 1. Indeks Domain
        dom = org.domain or extract_domain(org.website) or extract_domain(org.email)
        if dom:
            self.domain_index[dom] = org
            if not org.domain:
                org.domain = dom
                
        # 2. Indeks Nama Normalisasi
        norm_name = org.normalized_name or normalize_company_name(org.name)
        if norm_name:
            if not org.normalized_name:
                org.normalized_name = norm_name
            self.normalized_name_index.setdefault(norm_name, []).append(org)
            
            # Indeks Nama + Kota/Provinsi
            city_norm, prov_norm = normalize_location(org.city, org.province)
            if city_norm:
                self.name_location_index.setdefault((norm_name, city_norm), []).append(org)
            if prov_norm:
                self.name_location_index.setdefault((norm_name, prov_norm), []).append(org)
                
            # Indeks Token untuk akselerasi pencarian fuzzy Tier 4 (O(1) dictionary lookup)
            tokens = norm_name.split()
            if tokens:
                self.first_token_index.setdefault(tokens[0], []).append(org)
                if len(tokens) >= 2:
                    self.two_token_index.setdefault((tokens[0], tokens[1]), []).append(org)
                
        # 3. Indeks Telepon
        phone_norm = normalize_phone(org.phone)
        if phone_norm:
            self.phone_index[phone_norm] = org

    def evaluate_candidate(
        self,
        name: str,
        website: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        city: Optional[str] = None,
        province: Optional[str] = None
    ) -> MatchResult:
        """Mengevaluasi calon entitas terhadap master database berdasarkan sinyal Tier 1-4."""
        norm_name = normalize_company_name(name)
        candidate_domain = extract_domain(website) or extract_domain(email)
        candidate_phone = normalize_phone(phone)
        candidate_city, candidate_prov = normalize_location(city, province)

        # ---------------------------------------------------------------------
        # TIER 1: Corporate Domain Match (Strongest Signal)
        # ---------------------------------------------------------------------
        if candidate_domain and candidate_domain in self.domain_index:
            matched = self.domain_index[candidate_domain]
            return MatchResult(
                decision="auto_match",
                tier="tier1_domain",
                confidence=0.98,
                signal_strength="STRONGEST",
                matched_org=matched,
                reason=f"Cocok kuat melalui corporate domain identik: '{candidate_domain}'"
            )

        # ---------------------------------------------------------------------
        # TIER 2: Normalized Legal Name + Wilayah Match (Strong Signal)
        # ---------------------------------------------------------------------
        if norm_name:
            # Cek kecocokan nama + kota
            if candidate_city and (norm_name, candidate_city) in self.name_location_index:
                matched = self.name_location_index[(norm_name, candidate_city)][0]
                return MatchResult(
                    decision="auto_match",
                    tier="tier2_name_location",
                    confidence=0.95,
                    signal_strength="STRONG",
                    matched_org=matched,
                    reason=f"Cocok kuat melalui nama normalisasi identik ('{norm_name}') dan kota ('{candidate_city}')"
                )
            
            # Cek kecocokan nama + provinsi
            if candidate_prov and (norm_name, candidate_prov) in self.name_location_index:
                matched = self.name_location_index[(norm_name, candidate_prov)][0]
                return MatchResult(
                    decision="auto_match",
                    tier="tier2_name_location",
                    confidence=0.92,
                    signal_strength="STRONG",
                    matched_org=matched,
                    reason=f"Cocok kuat melalui nama normalisasi identik ('{norm_name}') dan provinsi ('{candidate_prov}')"
                )

            # Cek nama normalisasi sama persis tetapi lokasi belum tentu sama
            if norm_name in self.normalized_name_index:
                matched_list = self.normalized_name_index[norm_name]
                matched = matched_list[0]
                m_city, m_prov = normalize_location(matched.city, matched.province)
                
                # Jika salah satu tidak punya info lokasi, ini tetap strong match
                if not candidate_city and not candidate_prov or not m_city and not m_prov:
                    return MatchResult(
                        decision="auto_match",
                        tier="tier2_name_location",
                        confidence=0.90,
                        signal_strength="STRONG",
                        matched_org=matched,
                        reason=f"Nama normalisasi identik ('{norm_name}') tanpa konflik wilayah"
                    )
                # Jika lokasi sama
                if (candidate_city and candidate_city == m_city) or (candidate_prov and candidate_prov == m_prov):
                    return MatchResult(
                        decision="auto_match",
                        tier="tier2_name_location",
                        confidence=0.94,
                        signal_strength="STRONG",
                        matched_org=matched,
                        reason=f"Nama normalisasi dan wilayah cocok ('{norm_name}')"
                    )
                # Konflik lokasi berbeda secara eksplisit -> REVIEW CANDIDATE (Jangan auto-merge!)
                return MatchResult(
                    decision="review_candidate",
                    tier="tier2_name_location_conflict",
                    confidence=0.75,
                    signal_strength="MODERATE",
                    matched_org=matched,
                    reason=f"Nama identik ('{norm_name}') tetapi lokasi berbeda (Incoming: {candidate_city}/{candidate_prov} vs Existing: {m_city}/{m_prov})"
                )

        # ---------------------------------------------------------------------
        # TIER 3: Corporate Contact Match (Supporting Signal)
        # ---------------------------------------------------------------------
        if candidate_phone and candidate_phone in self.phone_index:
            matched = self.phone_index[candidate_phone]
            m_norm_name = matched.normalized_name or normalize_company_name(matched.name)
            name_sim = calculate_fuzzy_ratio(norm_name, m_norm_name)
            
            if name_sim >= 0.70:
                return MatchResult(
                    decision="auto_match",
                    tier="tier3_contact",
                    confidence=0.88,
                    signal_strength="STRONG",
                    matched_org=matched,
                    reason=f"Nomor telepon kantor identik ('{candidate_phone}') dengan kemiripan nama ({name_sim:.2f})"
                )
            else:
                # Telepon sama tapi nama beda jauh -> Masuk review candidate
                return MatchResult(
                    decision="review_candidate",
                    tier="tier3_contact_name_diff",
                    confidence=0.65,
                    signal_strength="SUPPORTING",
                    matched_org=matched,
                    reason=f"Nomor telepon identik ('{candidate_phone}') tetapi nama berbeda signifikan ('{norm_name}' vs '{m_norm_name}')"
                )

        # ---------------------------------------------------------------------
        # TIER 4: Fuzzy Name Similarity Match (Candidate Review Signal)
        # ---------------------------------------------------------------------
        if norm_name and len(norm_name) >= 4:
            tokens = norm_name.split()
            candidates_to_check = set()
            
            # 1. Cek index 2 token terlebih dahulu (sangat terarah dan akurat)
            if len(tokens) >= 2:
                two_tok = (tokens[0], tokens[1])
                if two_tok in self.two_token_index:
                    candidates_to_check.update(self.two_token_index[two_tok])
                    
            # 2. Cek index token pertama jika kandidat masih sedikit
            if len(candidates_to_check) < 40 and tokens:
                first_token = tokens[0]
                if len(first_token) >= 3 and first_token in self.first_token_index:
                    candidates_to_check.update(self.first_token_index[first_token][:60])
                    
            best_ratio = 0.0
            best_org = None
            len_query = len(norm_name)
            
            for candidate in candidates_to_check:
                c_norm = candidate.normalized_name or normalize_company_name(candidate.name)
                len_cand = len(c_norm)
                # Mathematical ratio bound: lewati jika rasio teoritis maksimum < 0.88
                if len_cand and (2.0 * min(len_query, len_cand) / (len_query + len_cand)) < 0.88:
                    continue
                    
                ratio = calculate_fuzzy_ratio(norm_name, c_norm)
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_org = candidate
                    
            if best_ratio >= 0.88 and best_org:
                m_city, m_prov = normalize_location(best_org.city, best_org.province)
                location_match = bool(
                    (candidate_city and candidate_city == m_city) or
                    (candidate_prov and candidate_prov == m_prov)
                )
                
                # Jika kemiripan sangat tinggi (>= 0.94) DAN wilayah cocok -> Auto Match
                if best_ratio >= 0.94 and location_match:
                    return MatchResult(
                        decision="auto_match",
                        tier="tier4_fuzzy_candidate",
                        confidence=0.88,
                        signal_strength="STRONG",
                        matched_org=best_org,
                        reason=f"Fuzzy name similarity sangat tinggi ({best_ratio:.2f}) dan wilayah cocok"
                    )
                else:
                    # Kemiripan antara 0.88 - 0.93 -> KANDIDAT REVIEW (Jangan auto-merge!)
                    return MatchResult(
                        decision="review_candidate",
                        tier="tier4_fuzzy_candidate",
                        confidence=round(best_ratio, 2),
                        signal_strength="CANDIDATE",
                        matched_org=best_org,
                        reason=f"Fuzzy name similarity ({best_ratio:.2f}) memenuhi ambang batas kandidat; memerlukan review manual"
                    )

        # ---------------------------------------------------------------------
        # UNMATCHED: Entitas Baru
        # ---------------------------------------------------------------------
        return MatchResult(
            decision="unmatched",
            tier=None,
            confidence=0.0,
            signal_strength="NONE",
            matched_org=None,
            reason="Tidak ditemukan sinyal kecocokan yang memenuhi kriteria"
        )


# =========================================================================
# E, F. SAFE MERGE STRATEGY & AUDIT / PROVENANCE
# =========================================================================

def safe_merge_organization(
    master: Organization,
    incoming: Dict[str, Any],
    match_result: MatchResult
) -> Tuple[bool, str]:
    """Menggabungkan data baru ke entitas master Organization secara aman (non-destructive):
    - Tidak pernah menimpa data master yang sudah ada dan terverifikasi dengan data kosong.
    - Melengkapi field master yang masih kosong.
    - Menyimpan log riwayat sumber ke dalam `provenance_json`.
    - Memastikan IDEMPOTENCY: jika data yang sama sudah pernah dimasukkan, tidak melakukan perubahan.
    
    Mengembalikan: (is_modified: bool, log_message: str)
    """
    is_modified = False
    now_str = utc_now_iso()
    
    # 1. Parsing riwayat provenance
    provenance_list = []
    if master.provenance_json:
        try:
            provenance_list = json.loads(master.provenance_json)
        except Exception:
            provenance_list = []
            
    # Cek idempotency: jika source_id dan source_type yang sama sudah ada di riwayat
    incoming_source_id = incoming.get("source_id")
    incoming_raw_data_id = incoming.get("raw_data_id")
    incoming_source_type = incoming.get("source_type") or "bps"
    incoming_raw_name = incoming.get("name", "").strip()
    
    already_recorded = False
    for entry in provenance_list:
        if entry.get("source_type") == incoming_source_type:
            if incoming_raw_data_id is not None and entry.get("raw_data_id") == incoming_raw_data_id:
                already_recorded = True
                break
            if incoming_source_id is not None and entry.get("source_id") == incoming_source_id:
                already_recorded = True
                break
            if incoming_source_id is None and incoming_raw_data_id is None and incoming_raw_name and entry.get("raw_name") == incoming_raw_name:
                already_recorded = True
                break

    # 2. Enrich field master yang masih kosong / null
    fields_to_enrich = [
        ("industry", incoming.get("industry")),
        ("address", incoming.get("address")),
        ("city", incoming.get("city")),
        ("province", incoming.get("province")),
        ("phone", incoming.get("phone")),
        ("email", incoming.get("email")),
        ("website", incoming.get("website")),
        ("product_fit", incoming.get("product_fit")),
        ("employee_size", incoming.get("employee_size")),
        ("description", incoming.get("description")),
    ]
    
    for field_name, inc_val in fields_to_enrich:
        if inc_val and str(inc_val).strip() and str(inc_val).lower() not in ("nan", "none", "-", ""):
            curr_val = getattr(master, field_name, None)
            if not curr_val or str(curr_val).strip() in ("", "-", "None", "nan"):
                setattr(master, field_name, str(inc_val).strip())
                is_modified = True

    # 3. Update Domain jika master belum punya
    if not master.domain:
        inc_domain = extract_domain(incoming.get("website")) or extract_domain(incoming.get("email"))
        if inc_domain:
            master.domain = inc_domain
            is_modified = True

    # 3b. Non-destructive merge untuk social_json
    inc_social_raw = incoming.get("social_json")
    if inc_social_raw and str(inc_social_raw).strip() not in ("", "{}", "null", "nan", "None"):
        try:
            inc_social = json.loads(inc_social_raw) if isinstance(inc_social_raw, str) else inc_social_raw
        except Exception:
            inc_social = {}

        if isinstance(inc_social, dict) and inc_social:
            curr_social = {}
            if master.social_json:
                try:
                    parsed_curr = json.loads(master.social_json)
                    if isinstance(parsed_curr, dict):
                        curr_social = parsed_curr
                    elif isinstance(parsed_curr, list):
                        for url in parsed_curr:
                            u_str = str(url).strip()
                            u_low = u_str.lower()
                            if "instagram.com" in u_low:
                                curr_social["instagram"] = u_str
                            elif "facebook.com" in u_low:
                                curr_social["facebook"] = u_str
                            elif "linkedin.com" in u_low:
                                curr_social["linkedin"] = u_str
                except Exception:
                    curr_social = {}

            social_updated = False
            for k in ("instagram", "facebook", "linkedin"):
                v = inc_social.get(k)
                if v and str(v).strip() and str(v).lower() not in ("nan", "none", "-"):
                    if not curr_social.get(k) or str(curr_social.get(k)).lower() in ("nan", "none", "-", ""):
                        curr_social[k] = str(v).strip()
                        social_updated = True

            if social_updated:
                master.social_json = json.dumps(curr_social, ensure_ascii=False)
                is_modified = True

    # 4. Update Skor Peluang (ambil skor tertinggi)
    inc_score = incoming.get("opportunity_score")
    if inc_score is not None:
        try:
            inc_score_int = int(inc_score)
            if inc_score_int > (master.opportunity_score or 0):
                master.opportunity_score = inc_score_int
                is_modified = True
        except (ValueError, TypeError):
            pass

    # 5. Update Priority Tier (Tier A > B > C > D)
    tier_rank = {"Tier A": 4, "A - HOT": 4, "Tier B": 3, "B - WARM": 3, "Tier C": 2, "C - POTENTIAL": 2, "Tier D": 1, "D - LOW": 1}
    inc_tier = incoming.get("priority_tier")
    if inc_tier and inc_tier in tier_rank:
        curr_rank = tier_rank.get(master.priority_tier, 0)
        new_rank = tier_rank.get(inc_tier, 0)
        if new_rank > curr_rank:
            master.priority_tier = inc_tier
            is_modified = True

    # Jika sumber sudah tercatat dan tidak ada field baru yang diubah -> Idempotent no-op
    if already_recorded and not is_modified:
        return False, "Data identik sudah tercatat dalam riwayat provenance (idempotent)."

    # 6. Catat riwayat provenance (hanya jika belum tercatat)
    if not already_recorded:
        provenance_entry = {
            "source_type": incoming_source_type,
            "source_id": incoming_source_id,
            "raw_data_id": incoming_raw_data_id,
            "raw_name": incoming_raw_name,
            "match_tier": match_result.tier,
            "confidence": match_result.confidence,
            "merged_at": now_str
        }
        provenance_list.append(provenance_entry)
        master.provenance_json = json.dumps(provenance_list, ensure_ascii=False)
    
    # 7. Update kesegaran data jika ada modifikasi
    if is_modified:
        master.last_seen = datetime.now(timezone.utc).replace(tzinfo=None)
        master.data_freshness = master.last_seen
    
    return is_modified, f"Berhasil digabungkan secara aman via {match_result.tier} (Confidence: {match_result.confidence})"


def create_organization_from_source(data: Dict[str, Any], initial_id: Optional[int] = None) -> Organization:
    """Membuat entitas baru Organization dengan provenance awal yang terstruktur dan lengkap."""
    raw_name = (data.get("name") or "").strip()
    norm_name = normalize_company_name(raw_name)
    dom = extract_domain(data.get("website")) or extract_domain(data.get("email"))
    
    source_type = data.get("source_type") or "bps"
    source_id = data.get("source_id")
    raw_data_id = data.get("raw_data_id")
    
    initial_provenance = [{
        "source_type": source_type,
        "source_id": source_id,
        "raw_data_id": raw_data_id,
        "raw_name": raw_name,
        "match_tier": "initial_creation",
        "confidence": 1.0,
        "merged_at": utc_now_iso()
    }]
    
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    org_kwargs = {
        "name": raw_name,
        "normalized_name": norm_name,
        "domain": dom,
        "organization_type": data.get("organization_type") or "Perusahaan",
        "industry": data.get("industry"),
        "address": data.get("address"),
        "city": data.get("city"),
        "province": data.get("province"),
        "phone": normalize_phone(data.get("phone")),
        "email": data.get("email"),
        "website": data.get("website"),
        "social_json": data.get("social_json"),
        "product_fit": data.get("product_fit"),
        "opportunity_score": int(data.get("opportunity_score") or 0),
        "priority_tier": data.get("priority_tier"),
        "source_id": source_id,
        "source_type": source_type,
        "employee_size": data.get("employee_size"),
        "verification_status": data.get("verification_status") or "discovered",
        "provenance_json": json.dumps(initial_provenance, ensure_ascii=False),
        "data_freshness": now,
        "last_seen": now,
        "created_at": now
    }
    if initial_id is not None:
        org_kwargs["id"] = initial_id
        
    return Organization(**org_kwargs)

