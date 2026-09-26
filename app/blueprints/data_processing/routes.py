import json
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

from app.extensions import db
from app.models import RawData, Prospect
from app import ai_agent
from app.utils import log_activity, roles_required

data_processing_bp = Blueprint("data_processing", __name__)


@data_processing_bp.route("/")
@login_required
@roles_required("business_analyst")
def index():
    items = RawData.query.order_by(RawData.created_at.desc()).limit(50).all()
    return render_template("data_processing/index.html", items=items)


@data_processing_bp.route("/<int:raw_id>")
@login_required
@roles_required("business_analyst")
def detail(raw_id):
    raw = RawData.query.get_or_404(raw_id)
    extracted = json.loads(raw.extracted_json) if raw.extracted_json else {}
    mapping = json.loads(raw.column_mapping_json) if raw.column_mapping_json else None
    return render_template("data_processing/detail.html", raw=raw, extracted=extracted, mapping=mapping)


# ---------- Klasifikasi Jenis Data (AI Agent) -> <<include>> Identifikasi Struktur Data ----------

@data_processing_bp.route("/<int:raw_id>/classify", methods=["POST"])
@login_required
@roles_required("business_analyst")
def classify(raw_id):
    raw = RawData.query.get_or_404(raw_id)
    extracted = json.loads(raw.extracted_json) if raw.extracted_json else {}
    sample_text = json.dumps(extracted)[:4000]
    try:
        result = ai_agent.classify_data(sample_text)
        raw.ai_classification = result.get("data_category", "unknown")
        raw.status = "classified"
        db.session.commit()
        log_activity("classify_data", f"raw_data #{raw.id} -> {raw.ai_classification}")
        flash(f"Klasifikasi AI: {raw.ai_classification}", "success")
    except Exception as e:
        flash(f"Gagal klasifikasi AI: {e}", "danger")
    return redirect(url_for("data_processing.detail", raw_id=raw.id))


# ---------- Mapping Kolom (AI Agent) -> <<include>> Rekomendasi Mapping Kolom ----------

@data_processing_bp.route("/<int:raw_id>/map-columns", methods=["POST"])
@login_required
@roles_required("business_analyst")
def map_columns(raw_id):
    raw = RawData.query.get_or_404(raw_id)
    extracted = json.loads(raw.extracted_json) if raw.extracted_json else {}
    columns = extracted.get("columns", [])
    if not columns:
        flash("Sumber data ini tidak memiliki struktur kolom (misal PDF teks bebas).", "warning")
        return redirect(url_for("data_processing.detail", raw_id=raw.id))
    try:
        result = ai_agent.map_columns(columns)
        raw.column_mapping_json = json.dumps(result)
        raw.status = "mapped"
        db.session.commit()
        log_activity("map_columns", f"raw_data #{raw.id} mapped")
        flash("Rekomendasi mapping kolom berhasil dibuat oleh AI. Anda dapat menyesuaikannya sebelum memproses.", "success")
    except Exception as e:
        flash(f"Gagal mapping kolom: {e}", "danger")
    return redirect(url_for("data_processing.detail", raw_id=raw.id))


@data_processing_bp.route("/<int:raw_id>/save-mapping", methods=["POST"])
@login_required
@roles_required("business_analyst")
def save_mapping(raw_id):
    raw = RawData.query.get_or_404(raw_id)
    extracted = json.loads(raw.extracted_json) if raw.extracted_json else {}
    columns = extracted.get("columns", [])
    custom_mapping = {}
    for col in columns:
        target = request.form.get(f"map_{col}", "").strip()
        if target and target in ai_agent.TARGET_SCHEMA:
            custom_mapping[col] = target
        else:
            custom_mapping[col] = None

    raw.column_mapping_json = json.dumps({
        "mapping": custom_mapping,
        "unmapped_target_fields": [f for f in ai_agent.TARGET_SCHEMA if f not in custom_mapping.values()],
    })
    raw.status = "mapped"
    db.session.commit()
    log_activity("save_mapping", f"raw_data #{raw.id} pemetaan kolom disimpan manual")
    flash("Pemetaan kolom berhasil disimpan.", "success")
    return redirect(url_for("data_processing.detail", raw_id=raw.id))


# ---------- Validasi & Cleaning Data -> <<include>> Deteksi Data Tidak Valid ----------
# ---------- + Deduplication + Enrichment + Simpan ke Database (jalankan sebagai satu proses "Process to Prospects") ----------

@data_processing_bp.route("/<int:raw_id>/process", methods=["POST"])
@login_required
@roles_required("business_analyst")
def process_to_prospects(raw_id):
    raw = RawData.query.get_or_404(raw_id)
    extracted = json.loads(raw.extracted_json) if raw.extracted_json else {}

    if extracted.get("download_filename") and raw.status == "processed":
        flash("Data dari file ini sudah selesai diproses dan tersimpan ke katalog prospek saat upload & enrichment.", "info")
        return redirect(url_for("prospect.list_prospects"))

    mapping = json.loads(raw.column_mapping_json).get("mapping", {}) if raw.column_mapping_json else {}
    rows = extracted.get("rows", [])

    do_enrich = request.form.get("enrich") == "on"
    enrich_count = 0
    max_live_enrichment = 15  # Batasi perulangan synchronous LLM agar tidak timeout / 429 rate limit

    created, skipped_duplicates, invalid = 0, 0, 0
    seen_companies = set()
    seen_emails = set()

    for row in rows:
        record = {}
        if mapping:
            for src_col, target_field in mapping.items():
                if target_field and src_col in row:
                    val = str(row[src_col]).strip() if row[src_col] is not None else ""
                    record[target_field] = val
        else:
            record = {k: str(v).strip() for k, v in row.items() if k in ai_agent.TARGET_SCHEMA and v is not None}

        company_name = (record.get("company_name") or "").strip()
        # Validasi dasar: nama perusahaan wajib ada dan bukan placeholder
        if not company_name or len(company_name) < 2 or company_name.lower() in {"test", "n/a", "unknown", "-", "null", "none"}:
            invalid += 1
            continue

        company_key = company_name.lower()
        contact_email = (record.get("contact_email") or "").strip().lower()

        # Validasi email sederhana jika ada
        if contact_email and ("@" not in contact_email or "." not in contact_email):
            contact_email = ""
            record["contact_email"] = ""

        # ---- Deduplication: Cek dalam batch saat ini ----
        if company_key in seen_companies or (contact_email and contact_email in seen_emails):
            skipped_duplicates += 1
            continue

        # ---- Deduplication: Cek database yang sudah tersimpan ----
        existing = Prospect.query.filter(
            db.or_(
                Prospect.company_name.ilike(company_name),
                Prospect.contact_email == contact_email if contact_email else False,
            )
        ).first()
        if existing:
            skipped_duplicates += 1
            continue

        seen_companies.add(company_key)
        if contact_email:
            seen_emails.add(contact_email)

        cleaned = record

        # ---- Enrichment Data (opsional, AI) ----
        if do_enrich and enrich_count < max_live_enrichment:
            if not cleaned.get("industry") or not cleaned.get("company_size"):
                try:
                    enrich = ai_agent.enrich_prospect(company_name, cleaned)
                    if not cleaned.get("industry"):
                        cleaned["industry"] = enrich.get("industry")
                    if not cleaned.get("company_size"):
                        cleaned["company_size"] = enrich.get("company_size")
                    if not cleaned.get("description"):
                        cleaned["description"] = enrich.get("summary")
                    enrich_count += 1
                except Exception:
                    pass

        # ---- Simpan ke Database ----
        prospect = Prospect(
            company_name=cleaned.get("company_name", company_name),
            industry=cleaned.get("industry") or None,
            region=cleaned.get("region") or None,
            company_size=cleaned.get("company_size") or None,
            website=cleaned.get("website") or None,
            contact_name=cleaned.get("contact_name") or None,
            contact_email=cleaned.get("contact_email") or None,
            contact_phone=cleaned.get("contact_phone") or None,
            description=cleaned.get("description") or None,
            raw_data_id=raw.id,
            created_by=current_user.id,
        )
        db.session.add(prospect)
        created += 1

    raw.status = "processed"
    db.session.commit()
    log_activity("process_to_prospects", f"raw_data #{raw.id}: created={created}, dup={skipped_duplicates}, invalid={invalid}, enriched={enrich_count}")

    msg = f"Selesai diproses. Prospek baru: {created}, duplikat dilewati: {skipped_duplicates}, tidak valid: {invalid}."
    if do_enrich and enrich_count > 0:
        msg += f" {enrich_count} data diperkaya oleh AI."
    flash(msg, "success")
    return redirect(url_for("prospect.list_prospects"))
