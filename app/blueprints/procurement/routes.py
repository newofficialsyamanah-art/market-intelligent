import json
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models import ProcurementSupplier, SupplierProduct, User
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
@roles_required("admin", "business_analyst", "marketing", "management", "procurement")
def index():
    """Halaman indeks procurement - secara default mengarahkan ke daftar Mitra Terdaftar (Web)."""
    target = request.args.get("tab", "").strip().lower()
    if target == "ai" or target == "ai_discovery":
        return redirect(url_for("procurement.ai_discovery"))
    return redirect(url_for("procurement.registered_suppliers"))


# ==============================================================================
# 1. HALAMAN KHUSUS: MITRA SUPPLIER TERDAFTAR VIA WEB (PORTAL SYAMANAH TENDER)
# ==============================================================================
@procurement_bp.route("/registered")
@login_required
@roles_required("admin", "business_analyst", "marketing", "management", "procurement")
def registered_suppliers():
    """Halaman direktori supplier yang mendaftar mandiri via web (Syamanah Tender)."""
    _ensure_table()
    from sqlalchemy import func

    search_q = request.args.get("q", "").strip()
    product = request.args.get("product", "").strip().lower()
    status = request.args.get("status", "all").strip().lower()
    sort_by = request.args.get("sort", "newest").strip().lower()
    page = request.args.get("page", 1, type=int)

    # KHUSUS Mitra yang mendaftar via web (created_by NOT NULL)
    query = ProcurementSupplier.query.filter(ProcurementSupplier.created_by.isnot(None))

    # Filter Keyword
    if search_q:
        query = query.filter(
            db.or_(
                ProcurementSupplier.company_name.ilike(f"%{search_q}%"),
                ProcurementSupplier.material.ilike(f"%{search_q}%"),
                ProcurementSupplier.description.ilike(f"%{search_q}%"),
                ProcurementSupplier.region.ilike(f"%{search_q}%"),
                ProcurementSupplier.contact_phone.ilike(f"%{search_q}%"),
                ProcurementSupplier.contact_email.ilike(f"%{search_q}%"),
            )
        )

    # Filter Kategori
    if product:
        query = query.filter_by(product=product)

    # Filter Status Verifikasi
    if status == "verified":
        query = query.filter_by(verification_status="verified")
    elif status == "pending" or status == "discovered":
        query = query.filter(ProcurementSupplier.verification_status != "verified")

    # Sorting
    if sort_by == "name_asc":
        query = query.order_by(ProcurementSupplier.company_name.asc())
    elif sort_by == "fit_desc":
        query = query.order_by(ProcurementSupplier.fit_score.desc(), ProcurementSupplier.created_at.desc())
    else:  # newest
        query = query.order_by(ProcurementSupplier.created_at.desc())

    # Pagination (12 rekanan per halaman untuk kenyamanan inspeksi)
    per_page = 12
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    suppliers = pagination.items

    # KPI & Metrik Rekanan Terdaftar
    base_registered = ProcurementSupplier.query.filter(ProcurementSupplier.created_by.isnot(None))
    total_registered = base_registered.count()
    verified_registered_count = base_registered.filter_by(verification_status="verified").count()
    pending_registered_count = total_registered - verified_registered_count
    total_catalog_items = SupplierProduct.query.count()

    # Hitung jumlah temuan AI untuk badge tab
    ai_count = ProcurementSupplier.query.filter(ProcurementSupplier.created_by.is_(None)).count()

    # Enrich supplier items dengan data user pendaftar & kelengkapan profil
    supplier_items = []
    for s in suppliers:
        creator = db.session.get(User, s.created_by) if s.created_by else None
        p_data = s.get_profile_data()
        c_score = s.calculate_completeness()
        cat_count = len(s.catalog_products) if s.catalog_products else 0
        supplier_items.append({
            "supplier": s,
            "creator": creator,
            "profile": p_data,
            "completeness": c_score,
            "catalog_count": cat_count,
        })

    return render_template(
        "procurement/registered.html",
        supplier_items=supplier_items,
        pagination=pagination,
        filters={
            "q": search_q,
            "product": product,
            "status": status,
            "sort": sort_by,
        },
        category_list=CATEGORY_LIST,
        total_registered=total_registered,
        verified_registered_count=verified_registered_count,
        pending_registered_count=pending_registered_count,
        total_catalog_items=total_catalog_items,
        ai_count=ai_count,
    )


# ==============================================================================
# 2. HALAMAN KHUSUS: SUPPLIER HASIL TEMUAN AI & WEB SOURCING
# ==============================================================================
@procurement_bp.route("/ai-discovery")
@login_required
@roles_required("admin", "business_analyst", "marketing", "management", "procurement")
def ai_discovery():
    """Halaman hasil penelusuran kandidat supplier secara otonom oleh AI & web scraping."""
    _ensure_table()
    from sqlalchemy import func

    search_q = request.args.get("q", "").strip()
    product = request.args.get("product", "").strip().lower()
    material = request.args.get("material", "").strip()
    fit_tier = request.args.get("fit_tier", "all").strip().lower()
    contact = request.args.get("contact", "all").strip().lower()
    status = request.args.get("status", "all").strip().lower()
    sort_by = request.args.get("sort", "fit_desc").strip().lower()
    page = request.args.get("page", 1, type=int)

    # KHUSUS Hasil Temuan AI / Crawler (created_by IS NULL)
    query = ProcurementSupplier.query.filter(ProcurementSupplier.created_by.is_(None))

    # Filter Keyword
    if search_q:
        query = query.filter(
            db.or_(
                ProcurementSupplier.company_name.ilike(f"%{search_q}%"),
                ProcurementSupplier.material.ilike(f"%{search_q}%"),
                ProcurementSupplier.description.ilike(f"%{search_q}%"),
                ProcurementSupplier.region.ilike(f"%{search_q}%"),
                ProcurementSupplier.contact_phone.ilike(f"%{search_q}%"),
                ProcurementSupplier.contact_email.ilike(f"%{search_q}%"),
            )
        )

    # Filter Kategori
    if product:
        query = query.filter_by(product=product)

    # Filter Material
    if material:
        query = query.filter(ProcurementSupplier.material.ilike(f"%{material}%"))

    # Filter AI Fit Score
    if fit_tier == "high":
        query = query.filter(ProcurementSupplier.fit_score >= 80)
    elif fit_tier == "medium":
        query = query.filter(ProcurementSupplier.fit_score >= 50, ProcurementSupplier.fit_score < 80)
    elif fit_tier == "low":
        query = query.filter(ProcurementSupplier.fit_score < 50)

    # Filter Ketersediaan Kontak
    if contact == "with_phone":
        query = query.filter(
            ProcurementSupplier.contact_phone.isnot(None),
            ProcurementSupplier.contact_phone != ""
        )

    # Filter Status Verifikasi
    if status == "verified":
        query = query.filter_by(verification_status="verified")
    elif status == "discovered":
        query = query.filter(ProcurementSupplier.verification_status != "verified")

    # Sorting
    if sort_by == "newest":
        query = query.order_by(ProcurementSupplier.created_at.desc())
    elif sort_by == "name_asc":
        query = query.order_by(ProcurementSupplier.company_name.asc())
    else:  # fit_desc
        query = query.order_by(ProcurementSupplier.fit_score.desc(), ProcurementSupplier.created_at.desc())

    # Pagination (15 items per page)
    per_page = 15
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    suppliers = pagination.items

    # KPI & Metrik Temuan AI
    base_ai = ProcurementSupplier.query.filter(ProcurementSupplier.created_by.is_(None))
    total_ai = base_ai.count()
    high_fit_count = base_ai.filter(ProcurementSupplier.fit_score >= 80).count()
    with_phone_count = base_ai.filter(ProcurementSupplier.contact_phone.isnot(None), ProcurementSupplier.contact_phone != "").count()
    verified_ai_count = base_ai.filter_by(verification_status="verified").count()

    # Hitung jumlah mitra terdaftar untuk badge tab
    registered_count = ProcurementSupplier.query.filter(ProcurementSupplier.created_by.isnot(None)).count()

    return render_template(
        "procurement/ai_discovery.html",
        suppliers=suppliers,
        pagination=pagination,
        filters={
            "q": search_q,
            "product": product,
            "material": material,
            "fit_tier": fit_tier,
            "contact": contact,
            "status": status,
            "sort": sort_by,
        },
        category_list=CATEGORY_LIST,
        total_ai=total_ai,
        high_fit_count=high_fit_count,
        with_phone_count=with_phone_count,
        verified_ai_count=verified_ai_count,
        registered_count=registered_count,
    )


# ==============================================================================
# 3. ACTIONS & SOURCING PIPELINE
# ==============================================================================
@procurement_bp.route("/search", methods=["POST"])
@login_required
@roles_required("admin", "business_analyst", "marketing", "procurement")
def search():
    """Menjalankan AI Autonomous Supplier Sourcing Pipeline."""
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
        return redirect(url_for("procurement.ai_discovery"))

    try:
        limit = max(1, min(50, int(request.form.get("limit", 20))))
        mode = request.form.get("mode", "ai_pipeline")
        use_ai = (mode == "ai_pipeline")
        query, suppliers = search_suppliers(
            norm_product, material, region, limit, current_user.id, use_ai_pipeline=use_ai, custom_prompt=custom_prompt
        )
        log_activity("procurement_search", f"Pencarian supplier ({mode}): {query}; prompt={custom_prompt[:50]}; hasil={len(suppliers)}")
        flash(f"AI Pipeline selesai: {len(suppliers)} calon supplier teridentifikasi & disimpan ke daftar Temuan AI.", "success")
    except Exception as error:
        db.session.rollback()
        flash(f"Pencarian AI gagal: {error}", "danger")

    return redirect(url_for("procurement.ai_discovery", product=norm_product, material=material))


@procurement_bp.route("/add_direct", methods=["POST"])
@login_required
@roles_required("admin", "business_analyst", "marketing", "procurement")
def add_direct():
    """Scraping URL vendor secara manual ke database Temuan AI."""
    _ensure_table()
    url = request.form.get("url", "").strip()
    product = request.form.get("product", "raw material").strip().lower()
    material = request.form.get("material", "").strip()
    region = request.form.get("region", "Indonesia").strip() or "Indonesia"

    if not url:
        flash("URL website supplier wajib diisi.", "warning")
        return redirect(url_for("procurement.ai_discovery"))

    if product not in VALID_CATEGORIES:
        flash("Kategori supplier tidak valid.", "warning")
        return redirect(url_for("procurement.ai_discovery"))

    try:
        supplier = scrape_supplier_direct(url, product, material, region, current_user.id)
        log_activity("procurement_add_direct", f"Input supplier manual: {supplier.company_name} ({url})")
        flash(f"Vendor '{supplier.company_name}' berhasil dianalisis AI (Fit Score: {supplier.fit_score}/100) dan ditambahkan ke Temuan AI.", "success")
    except Exception as error:
        db.session.rollback()
        flash(f"Gagal memproses URL supplier: {error}", "danger")

    return redirect(url_for("procurement.ai_discovery", product=product, material=material))


@procurement_bp.route("/<int:supplier_id>/verify", methods=["POST"])
@login_required
@roles_required("admin", "business_analyst", "management", "procurement")
def verify_supplier(supplier_id):
    """Toggle verifikasi supplier (Verified vs Pending/Discovered)."""
    _ensure_table()
    supplier = db.session.get(ProcurementSupplier, supplier_id)
    if not supplier:
        flash("Supplier tidak ditemukan.", "warning")
        return redirect(url_for("procurement.registered_suppliers"))

    current_status = supplier.verification_status
    if current_status == "verified":
        supplier.verification_status = "discovered"
        flash(f"Status verifikasi '{supplier.company_name}' diubah menjadi Pending/Discovered.", "info")
    else:
        supplier.verification_status = "verified"
        if supplier.fit_score < 75:
            supplier.fit_score = 85
        flash(f"Supplier '{supplier.company_name}' berhasil diverifikasi sebagai Rekanan Resmi.", "success")

    db.session.commit()
    log_activity("procurement_verify_supplier", f"Ubah status verifikasi {supplier.company_name} -> {supplier.verification_status}")

    next_url = request.form.get("next") or request.referrer
    if not next_url:
        next_url = url_for("procurement.registered_suppliers") if supplier.created_by else url_for("procurement.ai_discovery")
    return redirect(next_url)


@procurement_bp.route("/<int:supplier_id>/delete", methods=["POST"])
@login_required
@roles_required("admin", "business_analyst", "marketing", "procurement")
def delete(supplier_id):
    """Menghapus entitas supplier."""
    _ensure_table()
    supplier = db.session.get(ProcurementSupplier, supplier_id)
    if not supplier:
        flash("Supplier tidak ditemukan.", "warning")
        return redirect(url_for("procurement.registered_suppliers"))

    is_registered = bool(supplier.created_by)
    name = supplier.company_name
    db.session.delete(supplier)
    db.session.commit()
    log_activity("procurement_delete", f"Hapus supplier: {name}")
    flash(f"Supplier '{name}' berhasil dihapus.", "success")

    next_url = request.form.get("next") or request.referrer
    if not next_url:
        next_url = url_for("procurement.registered_suppliers") if is_registered else url_for("procurement.ai_discovery")
    return redirect(next_url)


# ==============================================================================
# 4. DETAIL SUPPLIER & INSPEKSI KATALOG
# ==============================================================================
@procurement_bp.route("/<int:supplier_id>")
@login_required
@roles_required("admin", "business_analyst", "marketing", "management", "procurement")
def detail(supplier_id):
    """Halaman detail profil lengkap, legalitas, evaluasi AI, dan katalog produk supplier."""
    _ensure_table()
    supplier = db.session.get(ProcurementSupplier, supplier_id) or ProcurementSupplier.query.get_or_404(supplier_id)

    try:
        recommendation = json.loads(supplier.recommendation_json or "{}")
    except (TypeError, ValueError):
        recommendation = {}

    company_profile = supplier.get_profile_data()
    completeness = supplier.calculate_completeness()

    # Dapatkan katalog produk yang diunggah oleh supplier ini
    products = []
    if supplier.catalog_products:
        products = supplier.catalog_products
    elif supplier.created_by:
        products = SupplierProduct.query.filter_by(user_id=supplier.created_by).order_by(SupplierProduct.created_at.desc()).all()

    creator_user = None
    if supplier.created_by:
        creator_user = db.session.get(User, supplier.created_by)

    return render_template(
        "procurement/detail.html",
        supplier=supplier,
        recommendation=recommendation,
        company_profile=company_profile,
        completeness=completeness,
        products=products,
        creator_user=creator_user,
    )
