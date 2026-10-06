import json
import csv
import io
from flask import Blueprint, render_template, redirect, url_for, flash, Response
from flask_login import login_required, current_user
from sqlalchemy import func

from app.extensions import db
from app.models import Prospect, Report, Campaign, RawData
from app import ai_agent
from app.utils import log_activity, roles_required

reporting_bp = Blueprint("reporting", __name__)


# ---------- Melihat Dashboard ----------

@reporting_bp.route("/")
@login_required
@roles_required("management")
def index():
    total_prospects = Prospect.query.count()
    total_campaigns = Campaign.query.count()
    total_raw = RawData.query.count()
    avg_score = db.session.query(func.avg(Prospect.score)).scalar() or 0

    industry_dist = dict(
        db.session.query(Prospect.industry, func.count(Prospect.id))
        .filter(Prospect.industry.isnot(None)).group_by(Prospect.industry).all()
    )
    reports = Report.query.order_by(Report.created_at.desc()).limit(20).all()

    return render_template(
        "reporting/index.html", total_prospects=total_prospects, total_campaigns=total_campaigns,
        total_raw=total_raw, avg_score=round(avg_score, 1), industry_dist=industry_dist, reports=reports,
    )


# ---------- Membuat Laporan Market Intelligence (ringkasan AI) ----------

@reporting_bp.route("/generate", methods=["POST"])
@login_required
@roles_required("management")
def generate_report():
    data = {
        "total_prospects": Prospect.query.count(),
        "total_campaigns": Campaign.query.count(),
        "avg_score": round(float(db.session.query(func.avg(Prospect.score)).scalar() or 0), 1),
        "industry_distribution": dict(
            db.session.query(Prospect.industry, func.count(Prospect.id))
            .filter(Prospect.industry.isnot(None)).group_by(Prospect.industry).all()
        ),
        "region_distribution": dict(
            db.session.query(Prospect.region, func.count(Prospect.id))
            .filter(Prospect.region.isnot(None)).group_by(Prospect.region).all()
        ),
    }
    try:
        summary = ai_agent.summarize_report(data)
    except Exception as e:
        summary = f"(Ringkasan AI gagal dibuat: {e})"

    report = Report(
        title="Laporan Market Intelligence", report_type="market_intelligence",
        content_json=json.dumps({"data": data, "ai_summary": summary}, default=str),
        created_by=current_user.id,
    )
    db.session.add(report)
    db.session.commit()
    log_activity("generate_report", f"Report #{report.id} dibuat")
    flash("Laporan Market Intelligence berhasil dibuat.", "success")
    return redirect(url_for("reporting.view_report", rid=report.id))


@reporting_bp.route("/<int:rid>")
@login_required
@roles_required("management")
def view_report(rid):
    report = Report.query.get_or_404(rid)
    content = json.loads(report.content_json) if report.content_json else {}
    return render_template("reporting/detail.html", report=report, content=content)


# ---------- Export Laporan ----------

@reporting_bp.route("/<int:rid>/export")
@login_required
@roles_required("management")
def export_report(rid):
    report = Report.query.get_or_404(rid)
    content = json.loads(report.content_json) if report.content_json else {}
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Metric", "Value"])
    for k, v in content.get("data", {}).items():
        writer.writerow([k, json.dumps(v) if isinstance(v, dict) else v])
    writer.writerow([])
    writer.writerow(["AI Summary", content.get("ai_summary", "")])

    log_activity("export_report", f"Export report #{rid}")
    return Response(
        output.getvalue(), mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename=report_{rid}.csv"},
    )
