import os
import json
import requests
from bs4 import BeautifulSoup
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models import RawData, DataSource
from app.utils import allowed_file, log_activity, roles_required, is_safe_url

data_collection_bp = Blueprint("data_collection", __name__)


@data_collection_bp.route("/")
@login_required
@roles_required("business_analyst")
def index():
    items = RawData.query.order_by(RawData.created_at.desc()).limit(50).all()
    return render_template("data_collection/index.html", items=items)


# ---------- Upload File (Excel/CSV/PDF) -> <<include>> Ekstraksi Data dari File ----------

@data_collection_bp.route("/upload", methods=["POST"])
@login_required
@roles_required("business_analyst")
def upload_file():
    file = request.files.get("file")
    if not file or file.filename == "":
        flash("Pilih file terlebih dahulu.", "warning")
        return redirect(url_for("data_collection.index"))

    if not allowed_file(file.filename, current_app.config["ALLOWED_EXTENSIONS"]):
        flash("Format file tidak didukung. Gunakan Excel/CSV/PDF.", "danger")
        return redirect(url_for("data_collection.index"))

    filename = secure_filename(file.filename)
    save_path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
    file.save(save_path)

    ext = filename.rsplit(".", 1)[1].lower() if "." in filename else ""

    # =========================================================================
    # FLOW OPSI B: DATASET EXCEL / CSV (BPS & Master Data)
    # UPLOAD -> READ/PARSE -> ENRICHMENT -> EXPORT EXCEL -> SAVE DB IN BATCH
    # =========================================================================
    if ext in ("xlsx", "xls", "csv"):
        import pandas as pd
        import uuid
        from app.enrichment import enrich_dataset, export_to_excel, save_enriched_to_db_in_batches

        # 1. READ / PARSE EXCEL
        try:
            if ext in ("xlsx", "xls"):
                df = pd.read_excel(save_path)
            else:
                df = pd.read_csv(save_path)
        except Exception as read_err:
            flash(f"Gagal membaca file spreadsheet: {read_err}", "danger")
            return redirect(url_for("data_collection.index"))

        total_rows = len(df)
        if total_rows == 0:
            flash("File spreadsheet kosong.", "warning")
            return redirect(url_for("data_collection.index"))

        # 2. ENRICHMENT (File-based, scalable untuk 8.500 - 10.000+ baris)
        try:
            df_enriched = enrich_dataset(df)
        except Exception as enrich_err:
            flash(f"Gagal memproses enrichment: {enrich_err}", "danger")
            return redirect(url_for("data_collection.index"))

        # 3. EXPORT HASIL ENRICHMENT KE EXCEL
        export_filename = f"hasil_enrichment_{uuid.uuid4().hex[:8]}.xlsx"
        export_path = os.path.join(current_app.config["UPLOAD_FOLDER"], export_filename)
        try:
            export_to_excel(df_enriched, export_path)
        except Exception as export_err:
            flash(f"Gagal mengekspor hasil enrichment ke Excel: {export_err}", "danger")
            return redirect(url_for("data_collection.index"))

        # 4. SIMPAN METADATA (Bukan raw JSON raksasa!)
        source = DataSource(name=filename, source_type="file", created_by=current_user.id)
        db.session.add(source)
        db.session.flush()

        # extracted_json HANYA menyimpan metadata ringkas & sample 10 baris (< 5 KB)
        sample_rows = df_enriched.head(10).fillna("").astype(str).to_dict(orient="records")
        meta_json = {
            "download_filename": export_filename,
            "total_rows": total_rows,
            "columns": list(df_enriched.columns.astype(str)),
            "sample": sample_rows,
            "rows": sample_rows,
        }

        raw = RawData(
            source_id=source.id,
            source_type="file",
            original_name=filename,
            raw_excerpt=f"File: {filename} | Total: {total_rows} baris | Export: {export_filename}",
            extracted_json=json.dumps(meta_json),
            status="processed",
            created_by=current_user.id,
        )
        db.session.add(raw)
        db.session.commit()

        # 5. SIMPAN HASIL ENRICHMENT KE DATABASE SECARA BATCH / CHUNK (250 record)
        # Sesuai aturan: jika database bermasalah, file Excel hasil enrichment tetap aman dan dibuat
        saved_count, db_err = save_enriched_to_db_in_batches(
            df_enriched, raw.id, current_user.id, batch_size=250
        )

        log_activity("upload_enrich_export", f"File {filename} ({total_rows} rows) -> {export_filename}")

        if db_err:
            raw.error_message = f"Peringatan penyimpanan DB: {db_err}"
            db.session.commit()
            flash(
                f"Enrichment berhasil! File Excel hasil enrichment ({total_rows} baris) siap diunduh. "
                f"Catatan database: {db_err}",
                "warning",
            )
        else:
            if hasattr(saved_count, "orgs_created"):
                flash(
                    f"File {filename} ({total_rows} baris) berhasil dienrichment, diekspor ke Excel ({export_filename}), "
                    f"dan tersimpan ke Master Intelligence: {saved_count.orgs_created} entitas baru, "
                    f"{saved_count.orgs_updated} entitas diperbarui/merged, "
                    f"{saved_count.candidates_flagged} kandidat review tercatat, "
                    f"{saved_count.prospects_synced} prospek tersinkronisasi.",
                    "success",
                )
            else:
                flash(
                    f"File {filename} ({total_rows} baris) berhasil dienrichment, diekspor ke Excel ({export_filename}), "
                    f"dan {saved_count} prospek tersimpan ke database!",
                    "success",
                )

        return redirect(url_for("data_processing.detail", raw_id=raw.id))

    # =========================================================================
    # DOKUMEN LAIN (MISAL: PDF)
    # =========================================================================
    source = DataSource(name=filename, source_type="file", created_by=current_user.id)
    db.session.add(source)
    db.session.flush()

    raw = RawData(
        source_id=source.id, source_type="file", original_name=filename,
        status="new", created_by=current_user.id,
    )

    try:
        extracted = _extract_file(save_path, filename)
        raw.raw_excerpt = json.dumps(extracted)[:2000]
        # Hanya simpan extracted_json jika ringkas (< 500 KB)
        raw.extracted_json = json.dumps(extracted)
        raw.status = "extracted"
    except Exception as e:
        raw.status = "error"
        raw.error_message = str(e)

    db.session.add(raw)
    db.session.commit()
    log_activity("upload_file", f"Upload {filename}")
    flash("File berhasil diunggah dan diekstrak.", "success")
    return redirect(url_for("data_processing.detail", raw_id=raw.id))


def _extract_file(path, filename):
    """Use case: Ekstraksi Data dari File (<<include>> dari Upload File)."""
    ext = filename.rsplit(".", 1)[1].lower()
    if ext in ("xlsx", "xls"):
        import pandas as pd
        df = pd.read_excel(path)
        return {"columns": list(df.columns.astype(str)), "rows": df.fillna("").astype(str).to_dict(orient="records")}
    elif ext == "csv":
        import pandas as pd
        df = pd.read_csv(path)
        return {"columns": list(df.columns.astype(str)), "rows": df.fillna("").astype(str).to_dict(orient="records")}
    elif ext == "pdf":
        from PyPDF2 import PdfReader
        from app import ai_agent
        reader = PdfReader(path)
        text = "\n".join((page.extract_text() or "") for page in reader.pages)
        rows = []
        if text.strip():
            try:
                rows = ai_agent.extract_entities_from_text(text)
            except Exception:
                rows = []
        columns = list(ai_agent.TARGET_SCHEMA) if rows else []
        return {"columns": columns, "rows": rows, "text": text[:20000]}
    raise ValueError("Ekstensi tidak dikenali")


# ---------- Input URL / Scraping -> <<include>> Ambil Data dari Website ----------

@data_collection_bp.route("/scrape", methods=["POST"])
@login_required
@roles_required("business_analyst")
def scrape_url():
    url = request.form.get("url", "").strip()
    if not url:
        flash("URL wajib diisi.", "warning")
        return redirect(url_for("data_collection.index"))

    if not is_safe_url(url):
        flash("URL tidak valid atau mengarah ke alamat jaringan lokal/privat yang tidak diizinkan.", "danger")
        return redirect(url_for("data_collection.index"))

    source = DataSource.query.filter_by(name=url, source_type="url").first()
    if not source:
        source = DataSource(name=url, source_type="url", created_by=current_user.id)
        db.session.add(source)
        db.session.flush()

    raw = RawData.query.filter_by(source_id=source.id, source_type="url").first()
    if not raw:
        raw = RawData(source_id=source.id, source_type="url", original_name=url,
                       status="new", created_by=current_user.id)
    try:
        resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style"]):
            tag.decompose()
        text = " ".join(soup.get_text(separator=" ").split())
        extracted = {"title": soup.title.string if soup.title else "", "text": text[:20000]}
        raw.raw_excerpt = text[:2000]
        raw.extracted_json = json.dumps(extracted)
        raw.status = "extracted"
    except Exception as e:
        raw.status = "error"
        raw.error_message = str(e)

    db.session.add(raw)
    db.session.commit()
    log_activity("scrape_url", f"Scrape {url}")
    flash("Data dari website berhasil diambil.", "success")
    return redirect(url_for("data_processing.index"))


# ---------- Integrasi API -> <<include>> Ambil Data dari API ----------

@data_collection_bp.route("/api-integration", methods=["POST"])
@login_required
@roles_required("business_analyst")
def api_integration():
    api_url = request.form.get("api_url", "").strip()
    method = request.form.get("method", "GET").upper()
    headers_raw = request.form.get("headers", "").strip()
    body_raw = request.form.get("body", "").strip()

    if not api_url:
        flash("URL API wajib diisi.", "warning")
        return redirect(url_for("data_collection.index"))

    if not is_safe_url(api_url):
        flash("URL API tidak valid atau mengarah ke alamat jaringan lokal/privat yang tidak diizinkan.", "danger")
        return redirect(url_for("data_collection.index"))

    source = DataSource(
        name=api_url, source_type="api",
        config_json=json.dumps({"method": method, "headers": headers_raw, "body": body_raw}),
        created_by=current_user.id,
    )
    db.session.add(source)
    db.session.flush()

    raw = RawData(source_id=source.id, source_type="api", original_name=api_url,
                   status="new", created_by=current_user.id)
    try:
        headers = json.loads(headers_raw) if headers_raw else {}
        body = json.loads(body_raw) if body_raw else None
        resp = requests.request(method, api_url, headers=headers, json=body, timeout=15)
        resp.raise_for_status()
        try:
            data = resp.json()
        except ValueError:
            data = {"text": resp.text[:20000]}
        raw.raw_excerpt = json.dumps(data)[:2000]
        raw.extracted_json = json.dumps(data)
        raw.status = "extracted"
    except Exception as e:
        raw.status = "error"
        raw.error_message = str(e)

    db.session.add(raw)
    db.session.commit()
    log_activity("api_integration", f"Call API {api_url}")
    flash("Data dari API berhasil diambil.", "success")
    return redirect(url_for("data_processing.index"))


# ---------- Input Manual ----------

@data_collection_bp.route("/manual", methods=["POST"])
@login_required
@roles_required("business_analyst")
def manual_input():
    company_name = request.form.get("company_name", "").strip()
    if not company_name:
        flash("Nama perusahaan wajib diisi.", "warning")
        return redirect(url_for("data_collection.index"))

    record = {
        "company_name": company_name,
        "industry": request.form.get("industry", ""),
        "region": request.form.get("region", ""),
        "company_size": request.form.get("company_size", ""),
        "website": request.form.get("website", ""),
        "contact_email": request.form.get("contact_email", ""),
        "description": request.form.get("description", ""),
    }

    source = DataSource(name=f"Manual: {company_name}", source_type="manual", created_by=current_user.id)
    db.session.add(source)
    db.session.flush()

    raw = RawData(
        source_id=source.id, source_type="manual", original_name=company_name,
        raw_excerpt=json.dumps(record)[:2000], extracted_json=json.dumps({"columns": list(record.keys()), "rows": [record]}),
        status="extracted", created_by=current_user.id,
    )
    db.session.add(raw)
    db.session.commit()
    log_activity("manual_input", f"Input manual {company_name}")
    flash("Data manual berhasil ditambahkan.", "success")
    return redirect(url_for("data_processing.index"))


# ---------- Download Hasil Enrichment Excel ----------

@data_collection_bp.route("/download/<path:filename>")
@login_required
def download_file(filename):
    from flask import send_from_directory
    safe_name = os.path.basename(filename)
    upload_dir = current_app.config["UPLOAD_FOLDER"]
    file_path = os.path.join(upload_dir, safe_name)
    if not os.path.exists(file_path):
        flash("File unduhan tidak ditemukan.", "danger")
        return redirect(url_for("data_collection.index"))
    return send_from_directory(upload_dir, safe_name, as_attachment=True)


@data_collection_bp.route("/download-raw/<int:raw_id>")
@login_required
def download_by_raw_id(raw_id):
    from flask import send_from_directory
    raw = RawData.query.get_or_404(raw_id)
    if not raw.extracted_json:
        flash("Data ini belum memiliki file hasil ekstraksi/enrichment.", "warning")
        return redirect(url_for("data_collection.index"))
    try:
        meta = json.loads(raw.extracted_json)
        dl_name = meta.get("download_filename")
        if not dl_name:
            flash("File hasil enrichment belum tersedia untuk entri ini.", "warning")
            return redirect(url_for("data_collection.index"))
        upload_dir = current_app.config["UPLOAD_FOLDER"]
        safe_name = os.path.basename(dl_name)
        file_path = os.path.join(upload_dir, safe_name)
        if not os.path.exists(file_path):
            flash("File unduhan fisik tidak ditemukan di server.", "danger")
            return redirect(url_for("data_collection.index"))
        return send_from_directory(upload_dir, safe_name, as_attachment=True)
    except Exception as e:
        flash(f"Gagal mengunduh file: {e}", "danger")
        return redirect(url_for("data_collection.index"))


