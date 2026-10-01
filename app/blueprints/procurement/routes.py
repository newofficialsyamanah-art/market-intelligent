import json
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models import ProcurementSupplier
from app.services.procurement_service import scrape_supplier_direct, search_suppliers
from app.utils import log_activity, roles_required

procurement_bp = Blueprint("procurement", __name__)


def _ensure_table():
    ProcurementSupplier.__table__.create(bind=db.engine, checkfirst=True)


@procurement_bp.route("/")
@login_required
@roles_required("admin", "business_analyst", "marketing", "management", "procurement")
def index():
    _ensure_table()
    product = request.args.get("product", "").strip()
    material = request.args.get("material", "").strip()
    query = ProcurementSupplier.query
    if product:
        query = query.filter_by(product=product)
    if material:
        query = query.filter(ProcurementSupplier.material.ilike(f"%{material}%"))
    suppliers = (
        query.order_by(ProcurementSupplier.fit_score.desc(), ProcurementSupplier.created_at.desc())
        .limit(100)
        .all()
    )
    return render_template(
        "procurement/index.html",
        suppliers=suppliers,
        filters={"product": product, "material": material},
    )


@procurement_bp.route("/search", methods=["POST"])
@login_required
@roles_required("admin", "business_analyst", "marketing", "procurement")
def search():
    _ensure_table()
    product = request.form.get("product", "").strip().lower()
    material = request.form.get("material", "").strip()
    region = request.form.get("region", "Indonesia").strip() or "Indonesia"
    custom_prompt = request.form.get("custom_prompt", "").strip()
    if product not in {"jersey", "kemeja", "polo", "kaos", "jaket"}:
        flash("Pilih jenis produk yang valid.", "warning")
        return redirect(url_for("procurement.index"))
    try:
        limit = max(1, min(50, int(request.form.get("limit", 20))))
        mode = request.form.get("mode", "ai_pipeline")
        use_ai = (mode == "ai_pipeline")
        query, suppliers = search_suppliers(
            product, material, region, limit, current_user.id, use_ai_pipeline=use_ai, custom_prompt=custom_prompt
        )
        log_activity("procurement_search", f"Pencarian supplier ({mode}): {query}; prompt={custom_prompt[:50]}; hasil={len(suppliers)}")
        flash(f"AI Pipeline selesai: {len(suppliers)} supplier kain terverifikasi & disimpan ke database.", "success")
    except Exception as error:
        db.session.rollback()
        flash(f"Pencarian procurement gagal: {error}", "danger")
    return redirect(url_for("procurement.index", product=product, material=material))


@procurement_bp.route("/add_direct", methods=["POST"])
@login_required
@roles_required("admin", "business_analyst", "marketing", "procurement")
def add_direct():
    _ensure_table()
    url = request.form.get("url", "").strip()
    product = request.form.get("product", "jersey").strip().lower()
    material = request.form.get("material", "").strip()
    region = request.form.get("region", "Indonesia").strip() or "Indonesia"
    if not url:
        flash("Masukkan URL website supplier.", "warning")
        return redirect(url_for("procurement.index"))
    try:
        supplier = scrape_supplier_direct(url, product, material, region, current_user.id)
        log_activity("procurement_add_direct", f"Input supplier manual: {supplier.company_name} ({url})")
        flash(f"Supplier '{supplier.company_name}' berhasil ditambahkan dan dianalisis AI (Fit Score: {supplier.fit_score}/100).", "success")
    except Exception as error:
        db.session.rollback()
        flash(f"Gagal memproses URL supplier: {error}", "danger")
    return redirect(url_for("procurement.index", product=product, material=material))


@procurement_bp.route("/<int:supplier_id>/delete", methods=["POST"])
@login_required
@roles_required("admin", "business_analyst", "marketing", "procurement")
def delete(supplier_id):
    _ensure_table()
    supplier = db.session.get(ProcurementSupplier, supplier_id)
    if not supplier:
        flash("Supplier tidak ditemukan.", "warning")
        return redirect(url_for("procurement.index"))
    name = supplier.company_name
    db.session.delete(supplier)
    db.session.commit()
    log_activity("procurement_delete", f"Hapus supplier: {name}")
    flash(f"Supplier '{name}' berhasil dihapus.", "success")
    return redirect(url_for("procurement.index"))


@procurement_bp.route("/<int:supplier_id>")
@login_required
@roles_required("admin", "business_analyst", "marketing", "management", "procurement")
def detail(supplier_id):
    _ensure_table()
    supplier = db.session.get(ProcurementSupplier, supplier_id) or ProcurementSupplier.query.get_or_404(supplier_id)
    try:
        recommendation = json.loads(supplier.recommendation_json or "{}")
    except (TypeError, ValueError):
        recommendation = {}
    return render_template("procurement/detail.html", supplier=supplier, recommendation=recommendation)
