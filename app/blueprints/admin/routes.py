import json
from datetime import datetime, timezone

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user

from app.extensions import db
from app.models import (
    User, DataSource, RawData, CronJob, ActivityLog, AIAgentConfig,
    DiscoverySource, Organization, Event, EventParticipant, DuplicateCandidate,
    Prospect, Campaign
)
from app.utils import roles_required, log_activity
from app.scheduler import (
    TASK_TYPES, schedule_job, unschedule_job, validate_schedule,
    execute_job, is_scheduler_running
)
from app.discovery import run_discovery
from app.services.discovery_service import DiscoveryPipelineService


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)

admin_bp = Blueprint("admin", __name__)

CRUD_RESOURCES = {
    "data-sources": {
        "title": "Sumber Data",
        "model": DataSource,
        "fields": ["name", "source_type", "config_json"],
        "required": ["name", "source_type"],
    },
    "discovery-sources": {
        "title": "Discovery Sources",
        "model": DiscoverySource,
        "fields": ["name", "source_kind", "category", "query_text", "region", "source_urls_json", "is_active"],
        "required": ["name", "source_kind"],
    },
    "organizations": {
        "title": "Organisasi",
        "model": Organization,
        "fields": ["name", "organization_type", "industry", "address", "city", "province", "phone", "email", "website", "product_fit", "priority_tier", "source_url", "description", "opportunity_score", "relevance_score", "verification_status"],
        "required": ["name", "organization_type"],
    },
    "events": {
        "title": "Event",
        "model": Event,
        "fields": ["name", "event_type", "organizer", "status", "venue", "city", "province", "address", "website", "source_url", "description", "relevance_notes", "relevance_score", "verification_status"],
        "required": ["name"],
    },
    "event-participants": {
        "title": "Peserta Event",
        "model": EventParticipant,
        "fields": ["event_id", "organization_id", "role", "booth_number", "notes"],
        "required": ["event_id", "organization_id", "role"],
    },
    "cron-jobs": {
        "title": "Cron Jobs",
        "model": CronJob,
        "fields": ["name", "task_type", "schedule_cron", "is_active"],
        "required": ["name", "task_type", "schedule_cron"],
    },
    "ai-configs": {
        "title": "Konfigurasi AI",
        "model": AIAgentConfig,
        "fields": ["agent_task", "model_name", "prompt_template", "is_active"],
        "required": ["agent_task"],
    },
}


def _crud_resource(resource):
    config = CRUD_RESOURCES.get(resource)
    if not config:
        from flask import abort
        abort(404)
    return config


def _crud_value(field, value):
    if field in {"is_active", "is_active_flag"}:
        return value in {"1", "true", "on", "yes"}
    if field in {"relevance_score", "opportunity_score"}:
        try:
            return int(value or 0)
        except ValueError:
            return 0
    if field in {"event_id", "organization_id"}:
        try:
            return int(value) if value is not None and str(value).strip() != "" else None
        except ValueError:
            return None
    return value or None


@admin_bp.route("/")
@login_required
@roles_required("admin")
def index():
    return render_template("admin/index.html")


# ---------- Kelola Pengguna dan Hak Akses ----------

@admin_bp.route("/users")
@login_required
@roles_required("admin")
def users():
    all_users = User.query.order_by(User.created_at.desc()).all()
    return render_template("admin/users.html", users=all_users)


@admin_bp.route("/users/new", methods=["POST"])
@login_required
@roles_required("admin")
def create_user():
    name = request.form.get("name")
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password")
    role = request.form.get("role", "business_analyst")
    if User.query.filter_by(email=email).first():
        flash("Email sudah terdaftar.", "danger")
    else:
        u = User(name=name, email=email, role=role)
        u.set_password(password)
        db.session.add(u)
        db.session.commit()
        log_activity("admin_create_user", f"Buat user {email} ({role})")
        flash("Pengguna berhasil dibuat.", "success")
    return redirect(url_for("admin.users"))


@admin_bp.route("/users/<int:uid>/toggle", methods=["POST"])
@login_required
@roles_required("admin")
def toggle_user(uid):
    u = User.query.get_or_404(uid)
    u.is_active_flag = not u.is_active_flag
    db.session.commit()
    log_activity("admin_toggle_user", f"Toggle user #{uid} -> {u.is_active_flag}")
    flash("Status pengguna diperbarui.", "success")
    return redirect(url_for("admin.users"))


@admin_bp.route("/users/<int:uid>/role", methods=["POST"])
@login_required
@roles_required("admin")
def change_role(uid):
    u = User.query.get_or_404(uid)
    u.role = request.form.get("role", u.role)
    db.session.commit()
    log_activity("admin_change_role", f"User #{uid} -> role {u.role}")
    flash("Role pengguna diperbarui.", "success")
    return redirect(url_for("admin.users"))


# ---------- Kelola Sumber Data ----------

@admin_bp.route("/data-sources")
@login_required
@roles_required("admin")
def data_sources():
    sources = DataSource.query.order_by(DataSource.created_at.desc()).all()
    return render_template("admin/data_sources.html", sources=sources)


# ---------- CRUD data administratif ----------

@admin_bp.route("/data-manager/<resource>")
@login_required
@roles_required("admin")
def data_manager(resource):
    config = _crud_resource(resource)
    records = config["model"].query.order_by(config["model"].id.desc()).limit(300).all()
    return render_template("admin/data_manager.html", resource=resource, config=config, records=records)


@admin_bp.route("/data-manager/<resource>/new", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def data_manager_new(resource):
    config = _crud_resource(resource)
    if request.method == "POST":
        values = {field: _crud_value(field, request.form.get(field)) for field in config["fields"]}
        missing = [field for field in config["required"] if not values.get(field)]
        if resource == "cron-jobs":
            try:
                validate_schedule(values.get("schedule_cron", ""))
            except (ValueError, TypeError):
                missing.append("schedule_cron (format cron tidak valid)")
        if missing:
            flash(f"Field wajib belum diisi: {', '.join(missing)}", "danger")
        else:
            record = config["model"](**values)
            db.session.add(record)
            db.session.commit()
            if resource == "cron-jobs" and record.is_active:
                schedule_job(current_app, record)
            log_activity("admin_create_record", f"{resource} #{record.id} dibuat")
            flash("Data berhasil dibuat.", "success")
            return redirect(url_for("admin.data_manager", resource=resource))
    return render_template("admin/data_manager_form.html", resource=resource, config=config, record=None)


@admin_bp.route("/data-manager/<resource>/<int:record_id>/edit", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def data_manager_edit(resource, record_id):
    config = _crud_resource(resource)
    record = db.session.get(config["model"], record_id)
    if not record:
        from flask import abort
        abort(404)
    if request.method == "POST":
        values = {field: _crud_value(field, request.form.get(field)) for field in config["fields"]}
        missing = [field for field in config["required"] if not values.get(field)]
        if resource == "cron-jobs":
            try:
                validate_schedule(values.get("schedule_cron", ""))
            except (ValueError, TypeError):
                missing.append("schedule_cron (format cron tidak valid)")
        if missing:
            flash(f"Field wajib belum diisi: {', '.join(missing)}", "danger")
        else:
            if resource == "cron-jobs":
                unschedule_job(record.id)
            for field, value in values.items():
                setattr(record, field, value)
            db.session.commit()
            if resource == "cron-jobs" and record.is_active:
                schedule_job(current_app, record)
            log_activity("admin_edit_record", f"{resource} #{record.id} diperbarui")
            flash("Data berhasil diperbarui.", "success")
            return redirect(url_for("admin.data_manager", resource=resource))
    return render_template("admin/data_manager_form.html", resource=resource, config=config, record=record)


@admin_bp.route("/data-manager/<resource>/<int:record_id>/delete", methods=["POST"])
@login_required
@roles_required("admin")
def data_manager_delete(resource, record_id):
    config = _crud_resource(resource)
    record = db.session.get(config["model"], record_id)
    if not record:
        from flask import abort
        abort(404)
    if resource == "cron-jobs":
        unschedule_job(record.id)
    db.session.delete(record)
    db.session.commit()
    log_activity("admin_delete_record", f"{resource} #{record_id} dihapus")
    flash("Data berhasil dihapus.", "success")
    return redirect(url_for("admin.data_manager", resource=resource))


# ---------- Discovery organisasi dan event ----------

@admin_bp.route("/discovery")
@login_required
@roles_required("admin", "business_analyst")
def discovery():
    sources = DiscoverySource.query.order_by(DiscoverySource.created_at.desc()).all()
    organizations = Organization.query.order_by(Organization.last_seen.desc()).limit(100).all()
    events = Event.query.order_by(Event.last_seen.desc()).limit(100).all()
    return render_template("admin/discovery.html", sources=sources, organizations=organizations, events=events)


@admin_bp.route("/discovery/sources/new", methods=["POST"])
@login_required
@roles_required("admin", "business_analyst")
def create_discovery_source():
    raw_urls = request.form.get("source_urls", "")
    urls = [line.strip() for line in raw_urls.splitlines() if line.strip()]
    source = DiscoverySource(
        name=request.form.get("name", "Discovery source").strip(),
        source_kind=request.form.get("source_kind", "organization"),
        category=request.form.get("category", "").strip(),
        query_text=request.form.get("query_text", "").strip(),
        region=request.form.get("region", "Indonesia").strip(),
        source_urls_json=json.dumps(urls),
        created_by=current_user.id,
    )
    db.session.add(source)
    db.session.commit()
    log_activity("create_discovery_source", f"Discovery source '{source.name}' dibuat")
    flash("Discovery source berhasil dibuat.", "success")
    return redirect(url_for("admin.discovery"))


@admin_bp.route("/discovery/sources/<int:sid>/sync", methods=["POST"])
@login_required
@roles_required("admin", "business_analyst")
def sync_discovery_source(sid):
    source = DiscoverySource.query.get_or_404(sid)
    try:
        result = run_discovery(source.id)
        log_activity("run_discovery", f"{source.name}: {result}")
        flash(result, "success")
    except Exception as error:
        source.last_run = _now()
        source.last_status = f"error: {str(error)[:180]}"
        db.session.commit()
        flash(f"Discovery gagal: {error}", "danger")
    return redirect(url_for("admin.discovery"))


@admin_bp.route("/discovery/sources/<int:sid>/toggle", methods=["POST"])
@login_required
@roles_required("admin", "business_analyst")
def toggle_discovery_source(sid):
    source = DiscoverySource.query.get_or_404(sid)
    source.is_active = not source.is_active
    db.session.commit()
    flash("Status discovery source diperbarui.", "success")
    return redirect(url_for("admin.discovery"))


# ---------- Monitoring Proses (Scraping/AI) ----------

@admin_bp.route("/monitoring")
@login_required
@roles_required("admin")
def monitoring():
    items = RawData.query.order_by(RawData.created_at.desc()).limit(100).all()
    jobs = CronJob.query.order_by(CronJob.created_at.desc()).all()
    status_counts = {}
    for s in ["new", "extracted", "classified", "mapped", "validated", "processed", "error"]:
        status_counts[s] = RawData.query.filter_by(status=s).count()

    system_metrics = {
        "scheduler_running": is_scheduler_running(),
        "total_orgs": Organization.query.count(),
        "total_prospects": Prospect.query.count(),
        "total_events": Event.query.count(),
        "pending_duplicates": DuplicateCandidate.query.filter_by(status="pending").count(),
        "ai_scored_orgs": Organization.query.filter(Organization.ai_scoring_json.isnot(None)).count(),
        "failed_jobs_count": CronJob.query.filter(CronJob.last_status.like("error:%")).count(),
        "active_jobs_count": CronJob.query.filter_by(is_active=True).count(),
    }
    return render_template("admin/monitoring.html", items=items, jobs=jobs, status_counts=status_counts, system_metrics=system_metrics)


# ---------- Mengatur Jadwal & Eksekusi Cron Job ----------

@admin_bp.route("/cron-jobs")
@login_required
@roles_required("admin")
def cron_jobs():
    jobs = CronJob.query.order_by(CronJob.created_at.desc()).all()
    return render_template("admin/cron_jobs.html", jobs=jobs)


@admin_bp.route("/cron-jobs/new", methods=["POST"])
@login_required
@roles_required("admin")
def create_cron_job():
    task_type = request.form.get("task_type", "")
    schedule_cron = request.form.get("schedule_cron", "").strip()
    if task_type not in TASK_TYPES:
        flash("Tipe task tidak didukung.", "danger")
        return redirect(url_for("admin.cron_jobs"))
    try:
        validate_schedule(schedule_cron)
    except (ValueError, TypeError):
        flash("Ekspresi cron tidak valid. Gunakan format 5 kolom, misalnya: 0 6 * * *.", "danger")
        return redirect(url_for("admin.cron_jobs"))

    job = CronJob(
        name=request.form.get("name"),
        task_type=task_type,
        schedule_cron=schedule_cron,
        is_active=True,
    )
    db.session.add(job)
    db.session.commit()
    schedule_job(current_app, job)
    log_activity("create_cron_job", f"Cron job '{job.name}' dibuat")
    flash("Jadwal cron job aktif dan sudah didaftarkan ke scheduler.", "success")
    return redirect(url_for("admin.cron_jobs"))


@admin_bp.route("/cron-jobs/<int:jid>/toggle", methods=["POST"])
@login_required
@roles_required("admin")
def toggle_cron_job(jid):
    job = CronJob.query.get_or_404(jid)
    job.is_active = not job.is_active
    db.session.commit()
    if job.is_active:
        try:
            schedule_job(current_app, job)
        except (ValueError, TypeError):
            job.is_active = False
            job.last_status = "error: cron expression tidak valid"
            db.session.commit()
            flash("Jadwal tidak valid, job tetap dinonaktifkan.", "danger")
            return redirect(url_for("admin.cron_jobs"))
    else:
        unschedule_job(job.id)
    flash("Status cron job diperbarui.", "success")
    return redirect(url_for("admin.cron_jobs"))


@admin_bp.route("/cron-jobs/<int:jid>/run", methods=["POST"])
@login_required
@roles_required("admin")
def run_cron_job(jid):
    job = CronJob.query.get_or_404(jid)
    try:
        app_obj = current_app._get_current_object()
        execute_job(app_obj, job.id, force=True)
        job = db.session.get(CronJob, jid)
        if job.last_status == "success":
            flash(f"Cron job '{job.name}' berhasil dijalankan ({job.duration_seconds}s, {job.records_processed} data diproses).", "success")
        else:
            flash(f"Cron job '{job.name}' selesai dengan status: {job.last_status}", "warning")
    except Exception as e:
        flash(f"Gagal menjalankan cron job: {e}", "danger")
    return redirect(url_for("admin.cron_jobs"))


@admin_bp.route("/cron-jobs/<int:jid>/retry", methods=["POST"])
@login_required
@roles_required("admin")
def retry_cron_job(jid):
    job = CronJob.query.get_or_404(jid)
    try:
        app_obj = current_app._get_current_object()
        execute_job(app_obj, job.id, force=True)
        job = db.session.get(CronJob, jid)
        if job.last_status == "success":
            flash(f"Cron job '{job.name}' berhasil diretry.", "success")
        else:
            flash(f"Retry cron job '{job.name}' menghasilkan status: {job.last_status}", "warning")
    except Exception as e:
        flash(f"Gagal me-retry cron job: {e}", "danger")
    return redirect(url_for("admin.cron_jobs"))


# ---------- Discovery Triggers (Education, Community, Social) ----------

@admin_bp.route("/discovery/education/trigger", methods=["POST"])
@login_required
@roles_required("admin", "business_analyst")
def trigger_education_discovery():
    province = request.form.get("province", "Jawa Barat")
    city = request.form.get("city", "Bandung")
    limit = int(request.form.get("limit", 10))
    try:
        res = DiscoveryPipelineService.discover_education_institutions(province=province, city=city, limit_per_level=limit)
        flash(f"Discovery Pendidikan ({city}, {province}) selesai: {res['total_ingested']} diproses ({res['new_organizations']} organisasi baru, {res['matched_organizations']} matched).", "success")
    except Exception as e:
        flash(f"Discovery Pendidikan gagal: {e}", "danger")
    return redirect(url_for("admin.discovery"))


@admin_bp.route("/discovery/community/trigger", methods=["POST"])
@login_required
@roles_required("admin", "business_analyst")
def trigger_community_discovery():
    category = request.form.get("category", "futsal")
    city = request.form.get("city", "Bandung")
    limit = int(request.form.get("limit", 15))
    try:
        res = DiscoveryPipelineService.discover_communities(category=category, city=city, limit=limit)
        flash(f"Discovery Komunitas ({category} - {city}) selesai: {res['total_ingested']} diproses ({res['new_organizations']} organisasi baru).", "success")
    except Exception as e:
        flash(f"Discovery Komunitas gagal: {e}", "danger")
    return redirect(url_for("admin.discovery"))


@admin_bp.route("/discovery/social/trigger", methods=["POST"])
@login_required
@roles_required("admin", "business_analyst")
def trigger_social_discovery():
    platform = request.form.get("platform", "instagram")
    keyword = request.form.get("keyword", "jersey futsal bandung")
    limit = int(request.form.get("limit", 10))
    try:
        res = DiscoveryPipelineService.discover_social_media(platform=platform, query=keyword, limit=limit)
        flash(f"Discovery Media Sosial ({platform.upper()}) selesai: {res['total_ingested']} diproses ({res['new_organizations']} organisasi baru).", "success")
    except Exception as e:
        flash(f"Discovery Media Sosial gagal: {e}", "danger")
    return redirect(url_for("admin.discovery"))


# ---------- Melihat Log Aktivitas ----------

@admin_bp.route("/logs")
@login_required
@roles_required("admin")
def logs():
    entries = ActivityLog.query.order_by(ActivityLog.created_at.desc()).limit(300).all()
    return render_template("admin/logs.html", entries=entries)


# ---------- Mengelola Konfigurasi AI Agent ----------

@admin_bp.route("/ai-config")
@login_required
@roles_required("admin")
def ai_config():
    configs = AIAgentConfig.query.all()
    return render_template("admin/ai_config.html", configs=configs)


@admin_bp.route("/ai-config/new", methods=["POST"])
@login_required
@roles_required("admin")
def create_ai_config():
    cfg = AIAgentConfig(
        agent_task=request.form.get("agent_task"),
        model_name=request.form.get("model_name", "llama-3.3-70b-versatile"),
        prompt_template=request.form.get("prompt_template"),
        is_active=True,
    )
    db.session.add(cfg)
    db.session.commit()
    log_activity("create_ai_config", f"AI config untuk task {cfg.agent_task}")
    flash("Konfigurasi AI Agent disimpan.", "success")
    return redirect(url_for("admin.ai_config"))
