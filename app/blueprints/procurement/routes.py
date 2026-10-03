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


VALID_CATEGORIES = {
    "raw material",
    "distributor",
    "elektrikal",
    "services",
    "pharmaceutical",
    "local",
    "hardware",
    "software",
    # Legacy aliases
    "jersey", "kemeja", "polo", "kaos", "jaket"
}

CATEGORY_LIST = [
    {"key": "raw material", "label": "Raw Material", "desc": "Bahan Baku Industri & Manufaktur", "icon": "bi-boxes", "badge": "bg-primary"},
    {"key": "distributor", "label": "Distributor", "desc": "Distributor & Supply Chain B2B", "icon": "bi-truck", "badge": "bg-success"},
    {"key": "elektrikal", "label": "Elektrikal", "desc": "Kelistrikan, Trafo, Panel & Kabel", "icon": "bi-lightning-charge", "badge": "bg-warning text-dark"},
    {"key": "services", "label": "Services", "desc": "Jasa, Facility Mgmt & Logistik", "icon": "bi-gear-wide-connected", "badge": "bg-info text-dark"},
    {"key": "pharmaceutical", "label": "Pharmaceutical", "desc": "Farmasi, Medis, Obat & Alkes", "icon": "bi-capsule", "badge": "bg-danger"},
    {"key": "local", "label": "Local Supplier", "desc": "Pemasok Lokal & UMKM Daerah", "icon": "bi-geo-alt", "badge": "bg-secondary"},
    {"key": "hardware", "label": "Hardware", "desc": "Perkakas, Mesin Teknik & Alat", "icon": "bi-tools", "badge": "bg-dark"},
    {"key": "software", "label": "Software", "desc": "Software B2B, Cloud, ERP & SaaS", "icon": "bi-cpu", "badge": "bg-primary"},
]


@procurement_bp.route("/")
@login_required
@roles_required("admin", "business_analyst", "marketing", "management", "procurement", "supplier")
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
    from sqlalchemy import func
    category_counts = dict(
        db.session.query(ProcurementSupplier.product, func.count(ProcurementSupplier.id))
        .group_by(ProcurementSupplier.product)
        .all()
    )
    total_suppliers = sum(category_counts.values())

    return render_template(
        "procurement/index.html",
        suppliers=suppliers,
        filters={"product": product, "material": material},
        category_counts=category_counts,
        category_list=CATEGORY_LIST,
        total_suppliers=total_suppliers,
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
    if product in {"jersey", "kemeja", "polo", "kaos", "jaket"}:
        norm_product = "raw material"
        if not material:
            material = product
    else:
        norm_product = product

    if norm_product not in VALID_CATEGORIES:
        flash("Pilih kategori supplier yang valid (Raw Material, Distributor, Elektrikal, Services, Pharmaceutical, Local, Hardware, Software).", "warning")
        return redirect(url_for("procurement.index"))
    try:
        limit = max(1, min(50, int(request.form.get("limit", 20))))
        mode = request.form.get("mode", "ai_pipeline")
        use_ai = (mode == "ai_pipeline")
        query, suppliers = search_suppliers(
            norm_product, material, region, limit, current_user.id, use_ai_pipeline=use_ai, custom_prompt=custom_prompt
        )
        log_activity("procurement_search", f"Pencarian supplier ({mode}): {query}; prompt={custom_prompt[:50]}; hasil={len(suppliers)}")
        flash(f"AI Pipeline selesai: {len(suppliers)} supplier/vendor terverifikasi & disimpan ke database.", "success")
    except Exception as error:
        db.session.rollback()
        flash(f"Pencarian procurement gagal: {error}", "danger")
    return redirect(url_for("procurement.index", product=norm_product, material=material))


@procurement_bp.route("/add_direct", methods=["POST"])
@login_required
@roles_required("admin", "business_analyst", "marketing", "procurement")
def add_direct():
    _ensure_table()
    url = request.form.get("url", "").strip()
    product = request.form.get("product", "raw material").strip().lower()
    if product in {"jersey", "kemeja", "polo", "kaos", "jaket"}:
        product = "raw material"
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
