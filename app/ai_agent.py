"""
AI Agent module powered by Groq.
Mengimplementasikan use case pada kelompok "2. Data Processing & AI":
- Klasifikasi Jenis Data / Identifikasi Struktur Data
- Mapping Kolom / Rekomendasi Mapping Kolom
- Validasi & Cleaning Data / Deteksi Data Tidak Valid
- Enrichment Data / Cari Data Tambahan dari Sumber Publik
- Ekstraksi Entitas dari Teks Bebas / PDF
Serta dipakai juga oleh Prospect Management (Scoring) & Market Analysis (Rekomendasi Produk) & Reporting (Ringkasan AI).
"""

import json
import re
from groq import Groq
from flask import current_app


def _client():
    api_key = current_app.config.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY belum diset di file .env")
    return Groq(api_key=api_key)


def _model():
    return current_app.config.get("GROQ_MODEL", "llama-3.3-70b-versatile")


def _get_task_config(agent_task: str):
    """Membaca model dan prompt template kustom dari tabel ai_agent_configs jika aktif."""
    try:
        from app.models import AIAgentConfig
        cfg = AIAgentConfig.query.filter_by(agent_task=agent_task, is_active=True).first()
        if cfg:
            model = cfg.model_name.strip() if cfg.model_name and cfg.model_name.strip() else _model()
            prompt = cfg.prompt_template.strip() if cfg.prompt_template and cfg.prompt_template.strip() else None
            return model, prompt
    except Exception:
        pass
    return _model(), None


def _extract_json(text: str):
    """Groq kadang membungkus JSON dengan teks/markdown. Ambil blok JSON pertama secara robust."""
    if not text:
        return {}
    clean = text.strip()
    clean = re.sub(r"^```(?:json)?\s*", "", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\s*```$", "", clean)

    # 1. Coba parse langsung
    try:
        return json.loads(clean)
    except Exception:
        pass

    # 2. Cari blok objek {...} terluar
    first_brace = clean.find("{")
    last_brace = clean.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        try:
            return json.loads(clean[first_brace:last_brace + 1])
        except Exception:
            pass

    # 3. Cari blok array [...] terluar
    first_bracket = clean.find("[")
    last_bracket = clean.rfind("]")
    if first_bracket != -1 and last_bracket != -1 and last_bracket > first_bracket:
        try:
            return json.loads(clean[first_bracket:last_bracket + 1])
        except Exception:
            pass

    # 4. Fallback regex
    match = re.search(r"(\[.*\]|\{.*\})", clean, flags=re.DOTALL)
    if match:
        return json.loads(match.group(1))

    raise ValueError(f"Tidak dapat mengekstrak JSON dari teks: {text[:200]}")


def _chat_json(system_prompt: str, user_prompt: str, temperature: float = 0.2, task_name: str = None):
    model_name = _model()
    effective_system = system_prompt

    if task_name:
        custom_model, custom_prompt = _get_task_config(task_name)
        if custom_model:
            model_name = custom_model
        if custom_prompt:
            effective_system = custom_prompt

    client = _client()
    resp = client.chat.completions.create(
        model=model_name,
        temperature=temperature,
        messages=[
            {"role": "system", "content": effective_system + "\nSelalu balas HANYA dengan JSON valid, tanpa penjelasan tambahan."},
            {"role": "user", "content": user_prompt},
        ],
    )
    content = resp.choices[0].message.content
    try:
        return _extract_json(content)
    except Exception:
        return {"raw_response": content, "parse_error": True}


def _chat_text(system_prompt: str, user_prompt: str, temperature: float = 0.4, task_name: str = None):
    model_name = _model()
    effective_system = system_prompt

    if task_name:
        custom_model, custom_prompt = _get_task_config(task_name)
        if custom_model:
            model_name = custom_model
        if custom_prompt:
            effective_system = custom_prompt

    client = _client()
    resp = client.chat.completions.create(
        model=model_name,
        temperature=temperature,
        messages=[
            {"role": "system", "content": effective_system},
            {"role": "user", "content": user_prompt},
        ],
    )
    return resp.choices[0].message.content.strip()


# ---------- Skema Standar Prospek ----------

TARGET_SCHEMA = [
    "company_name", "industry", "region", "company_size", "website",
    "contact_name", "contact_email", "contact_phone", "description",
]


# ---------- 1. Ekstraksi & Klasifikasi Data ----------

def classify_data(sample_text: str):
    """Use case: Klasifikasi Jenis Data (AI Agent) -> Identifikasi Struktur Data (<<include>>)"""
    system = (
        "Kamu adalah AI agent yang mengklasifikasikan jenis data mentah untuk sistem market intelligence. "
        "Tentukan apakah data berisi daftar perusahaan/prospek bisnis, data pasar/industri, atau data lain. "
        "Identifikasi juga struktur datanya (kolom-kolom yang kemungkinan ada)."
    )
    user = f"Data mentah (contoh potongan):\n{sample_text[:4000]}\n\n" \
           "Balas JSON dengan format: " \
           '{"data_category": "...", "confidence": 0-1, "detected_structure": ["kolom1","kolom2",...], "notes": "..."}'
    return _chat_json(system, user, task_name="classify_data")


def extract_entities_from_text(raw_text: str):
    """Mengekstrak calon prospek bisnis dari teks bebas / PDF menjadi daftar record terstruktur."""
    system = (
        "Kamu adalah AI agent ekstraksi data bisnis. Ekstrak semua entitas perusahaan atau prospek bisnis yang disebutkan "
        f"dalam teks berikut ke dalam format array of objects dengan kolom: {TARGET_SCHEMA}. "
        "Jika suatu informasi tidak ada di dalam teks, isi dengan string kosong ''."
    )
    user = f"Teks sumber:\n{raw_text[:8000]}\n\nBalas JSON dengan format: " \
           '{"prospects": [{"company_name": "...", "industry": "...", "region": "...", "company_size": "...", "website": "...", "contact_name": "...", "contact_email": "...", "contact_phone": "...", "description": "..."}]}'
    res = _chat_json(system, user, task_name="extract_entities")
    if isinstance(res, dict) and "prospects" in res and isinstance(res["prospects"], list):
        return res["prospects"]
    if isinstance(res, list):
        return res
    return []


# ---------- 2. Mapping Kolom ----------

def map_columns(source_columns: list):
    """Use case: Mapping Kolom (AI Agent) -> Rekomendasi Mapping Kolom (<<include>>)"""
    system = (
        "Kamu adalah AI agent yang memetakan kolom data sumber ke skema target sistem prospek. "
        f"Skema target: {TARGET_SCHEMA}. Untuk setiap kolom sumber, tentukan kolom target paling sesuai "
        "atau null jika tidak relevan."
    )
    user = f"Kolom sumber: {source_columns}\n\nBalas JSON dengan format: " \
           '{"mapping": {"kolom_sumber": "target_field_atau_null", ...}, "unmapped_target_fields": [...]}'
    return _chat_json(system, user, task_name="map_columns")


# ---------- 3. Validasi & Deteksi Data Tidak Valid ----------

def validate_record(record: dict):
    """Use case: Validasi & Cleaning Data -> Deteksi Data Tidak Valid (<<include>>)"""
    system = (
        "Kamu adalah AI agent quality-control data prospek bisnis. Periksa apakah record berikut valid, "
        "lengkap dan masuk akal (misal: email format benar, nama perusahaan bukan placeholder, dsb)."
    )
    user = f"Record: {json.dumps(record, ensure_ascii=False)}\n\nBalas JSON: " \
           '{"is_valid": true/false, "issues": ["..."], "cleaned_record": {...field yang sudah dibersihkan...}}'
    return _chat_json(system, user, task_name="validate_record")


# ---------- 4. Enrichment Data ----------

def enrich_prospect(company_name: str, known_info: dict = None):
    """Use case: Enrichment Data -> Cari Data Tambahan dari Sumber Publik (<<include>>)"""
    system = (
        "Kamu adalah AI agent enrichment data B2B. Berdasarkan nama perusahaan dan info yang sudah diketahui, "
        "lengkapi perkiraan industri, estimasi ukuran perusahaan, dan ringkasan singkat bisnisnya. "
        "Jika tidak yakin, tulis 'unknown' dan turunkan confidence."
    )
    user = f"Nama perusahaan: {company_name}\nInfo yang sudah ada: {json.dumps(known_info or {}, ensure_ascii=False)}\n\n" \
           "Balas JSON: " \
           '{"industry": "...", "company_size": "...", "summary": "...", "suggested_website": "...", "confidence": 0-1}'
    return _chat_json(system, user, task_name="enrich_prospect")


# ---------- 5. Prospect Scoring ----------

def score_prospect(prospect: dict):
    """Use case: Menentukan Prioritas Prospek (Scoring)"""
    system = (
        "Kamu adalah AI agent sales intelligence. Beri skor prioritas prospek dari 0-100 berdasarkan "
        "kelengkapan data, ukuran perusahaan, relevansi industri terhadap target pasar B2B umum, dan potensi konversi."
    )
    user = f"Data prospek: {json.dumps(prospect, ensure_ascii=False)}\n\nBalas JSON: " \
           '{"score": 0-100, "segment": "Enterprise/SME/Startup/Unknown", "reason": "..."}'
    res = _chat_json(system, user, task_name="score_prospect")
    if not isinstance(res, dict):
        res = {"score": 0, "segment": "Unknown", "reason": "Output AI tidak valid"}

    raw_score = res.get("score", 0)
    score_digits = re.findall(r"\d+", str(raw_score))
    clean_score = min(100, max(0, int(score_digits[0]))) if score_digits else 0
    res["score"] = clean_score
    if not res.get("segment"):
        res["segment"] = "Unknown"
    return res


# ---------- 6. Market Analysis: Rekomendasi Potensi Produk ----------

def recommend_products(market_summary: dict):
    """Use case: Rekomendasi Potensi Produk"""
    system = (
        "Kamu adalah AI agent market intelligence. Berdasarkan ringkasan distribusi industri/wilayah/ukuran "
        "perusahaan dari database prospek, berikan rekomendasi produk/layanan yang berpotensi paling relevan "
        "untuk dipasarkan, beserta alasannya."
    )
    user = f"Ringkasan data pasar: {json.dumps(market_summary, ensure_ascii=False)}\n\nBalas JSON: " \
           '{"recommendations": [{"product_or_service": "...", "target_segment": "...", "reason": "..."}]}'
    return _chat_json(system, user, task_name="recommend_products")


# ---------- 7. Reporting: Ringkasan Laporan Market Intelligence ----------

def summarize_report(data: dict):
    """Use case: Membuat Laporan Market Intelligence (ringkasan naratif oleh AI)"""
    system = "Kamu adalah analis market intelligence. Buat ringkasan eksekutif singkat (3-6 kalimat) berbahasa Indonesia."
    user = f"Data laporan: {json.dumps(data, ensure_ascii=False)}"
    return _chat_text(system, user, task_name="summarize_report")
