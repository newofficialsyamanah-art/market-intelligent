from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy import distinct

from app.extensions import db
from app.models import Prospect
from app import ai_agent
from app.utils import log_activity, roles_required

prospect_bp = Blueprint("prospect", __name__)


# ---------- Melihat Daftar Prospek + Filter & Pencarian Prospek ----------

@prospect_bp.route("/")
@login_required
@roles_required("admin", "business_analyst", "marketing", "management")
def list_prospects():
    q = request.args.get("q", "").strip()
    industry = request.args.get("industry", "").strip()
    region = request.args.get("region", "").strip()
    segment = request.args.get("segment", "").strip()
    status = request.args.get("status", "").strip()

    query = Prospect.query
    if q:
        like = f"%{q}%"
        query = query.filter(
            db.or_(
                Prospect.company_name.ilike(like),
                Prospect.contact_email.ilike(like),
                Prospect.region.ilike(like),
                Prospect.industry.ilike(like)
            )
        )
    if industry:
        query = query.filter(Prospect.industry == industry)
    if region:
        query = query.filter(Prospect.region.ilike(f"%{region}%"))
    if segment:
        query = query.filter(Prospect.segment == segment)
    if status:
        query = query.filter(Prospect.status == status)

    prospects = query.order_by(Prospect.score.desc(), Prospect.created_at.desc()).limit(300).all()

    from app.utils import get_all_indonesia_provinces
    industries = [r[0] for r in db.session.query(distinct(Prospect.industry)).filter(Prospect.industry.isnot(None)).all()]
    db_regions = [r[0] for r in db.session.query(distinct(Prospect.region)).filter(Prospect.region.isnot(None), Prospect.region != "", Prospect.region != "nan, nan").all()]
    regions = sorted(list(set(get_all_indonesia_provinces() + db_regions)))
    segments = [r[0] for r in db.session.query(distinct(Prospect.segment)).filter(Prospect.segment.isnot(None)).all()]

    return render_template(
        "prospect/list.html", prospects=prospects,
        industries=industries, regions=regions, segments=segments,
        filters={"q": q, "industry": industry, "region": region, "segment": segment, "status": status},
    )


@prospect_bp.route("/<int:pid>")
@login_required
@roles_required("admin", "business_analyst", "marketing", "management")
def detail(pid):
    p = Prospect.query.get_or_404(pid)
    return render_template("prospect/detail.html", p=p)


# ---------- Kelola Data Prospek (CRUD) ----------

@prospect_bp.route("/new", methods=["GET", "POST"])
@login_required
@roles_required("business_analyst")
def create():
    if request.method == "POST":
        p = Prospect(
            company_name=request.form["company_name"],
            industry=request.form.get("industry"),
            region=request.form.get("region"),
            company_size=request.form.get("company_size"),
            website=request.form.get("website"),
            contact_name=request.form.get("contact_name"),
            contact_email=request.form.get("contact_email"),
            contact_phone=request.form.get("contact_phone"),
            description=request.form.get("description"),
            created_by=current_user.id,
        )
        db.session.add(p)
        db.session.commit()
        log_activity("create_prospect", f"Buat prospek {p.company_name}")
        flash("Prospek berhasil dibuat.", "success")
        return redirect(url_for("prospect.detail", pid=p.id))
    return render_template("prospect/form.html", p=None)


@prospect_bp.route("/<int:pid>/edit", methods=["GET", "POST"])
@login_required
@roles_required("business_analyst")
def edit(pid):
    p = Prospect.query.get_or_404(pid)
    if request.method == "POST":
        for field in ["company_name", "industry", "region", "company_size", "website",
                      "contact_name", "contact_email", "contact_phone", "description", "status"]:
            setattr(p, field, request.form.get(field, getattr(p, field)))
        db.session.commit()
        log_activity("edit_prospect", f"Edit prospek #{p.id}")
        flash("Prospek berhasil diperbarui.", "success")
        return redirect(url_for("prospect.detail", pid=p.id))
    return render_template("prospect/form.html", p=p)


@prospect_bp.route("/<int:pid>/delete", methods=["POST"])
@login_required
@roles_required("business_analyst")
def delete(pid):
    p = Prospect.query.get_or_404(pid)
    db.session.delete(p)
    db.session.commit()
    log_activity("delete_prospect", f"Hapus prospek #{pid}")
    flash("Prospek berhasil dihapus.", "success")
    return redirect(url_for("prospect.list_prospects"))


# ---------- Menentukan Prioritas Prospek (Scoring) ----------

@prospect_bp.route("/<int:pid>/score", methods=["POST"])
@login_required
@roles_required("business_analyst")
def score(pid):
    p = Prospect.query.get_or_404(pid)
    data = {
        "company_name": p.company_name, "industry": p.industry, "region": p.region,
        "company_size": p.company_size, "website": p.website,
        "contact_email": p.contact_email, "description": p.description,
    }
    try:
        result = ai_agent.score_prospect(data)
        raw_score = result.get("score", 0)
        p.score = int(raw_score) if isinstance(raw_score, (int, float)) else 0
        p.segment = result.get("segment") or "Unknown"
        p.score_reason = result.get("reason") or ""
        db.session.commit()
        log_activity("score_prospect", f"Score prospek #{p.id} -> {p.score}")
        flash(f"Skor prospek: {p.score} ({p.segment})", "success")
    except Exception as e:
        flash(f"Gagal menghitung skor: {e}", "danger")
    return redirect(url_for("prospect.detail", pid=p.id))


# ---------- Segmentasi Prospek (batch, untuk semua prospek yang belum ada segmen) ----------

@prospect_bp.route("/segment-all", methods=["POST"])
@login_required
@roles_required("business_analyst")
def segment_all():
    prospects = Prospect.query.filter(Prospect.segment.is_(None)).limit(30).all()
    count = 0
    for p in prospects:
        data = {
            "company_name": p.company_name, "industry": p.industry, "region": p.region,
            "company_size": p.company_size, "description": p.description,
        }
        try:
            result = ai_agent.score_prospect(data)
            raw_score = result.get("score", 0)
            p.score = int(raw_score) if isinstance(raw_score, (int, float)) else 0
            p.segment = result.get("segment") or "Unknown"
            p.score_reason = result.get("reason") or ""
            count += 1
        except Exception:
            continue
    db.session.commit()
    log_activity("segment_all", f"Segmentasi batch {count} prospek")
    flash(f"{count} prospek berhasil disegmentasi/diberi skor.", "success")
    return redirect(url_for("prospect.list_prospects"))
