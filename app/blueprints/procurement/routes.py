import os
import json
import time
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import Blueprint, flash, redirect, render_template, request, url_for, current_app
from flask_login import current_user, login_required

from app.extensions import db
from app.models import ProcurementSupplier, SupplierProduct, QuotationRequest, User, utc_now
from app.services.procurement_service import scrape_supplier_direct, search_suppliers
from app.utils import log_activity, roles_required, allowed_file

procurement_bp = Blueprint("procurement", __name__)

ALLOWED_RFQ_EXTENSIONS = {"pdf", "docx", "doc", "xlsx", "xls", "png", "jpg", "jpeg", "zip"}


def _save_rfq_file(file_storage, prefix="rfq"):
    """Menyimpan file lampiran RFQ (TOR, spesifikasi, atau quotation resmi)."""
    if not file_storage or not file_storage.filename:
        return None
    if not allowed_file(file_storage.filename, ALLOWED_RFQ_EXTENSIONS):
        return None
    filename = secure_filename(file_storage.filename)
    timestamp = int(time.time())
    unique_filename = f"{prefix}_{current_user.id}_{timestamp}_{filename}"
    upload_dir = os.path.join(current_app.config["UPLOAD_FOLDER"], "rfq")
    os.makedirs(upload_dir, exist_ok=True)
    target_path = os.path.join(upload_dir, unique_filename)
    file_storage.save(target_path)
    return f"uploads/rfq/{unique_filename}"


def _generate_rfq_code():
    """Menghasilkan kode unik RFQ dengan format RFQ-YYYYMM-XXXX."""
    now_str = datetime.now().strftime("%Y%m")
    count = QuotationRequest.query.filter(QuotationRequest.rfq_code.like(f"RFQ-{now_str}-%")).count() + 1
    return f"RFQ-{now_str}-{count:04d}"


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


# ==============================================================================
# 5. E-KATALOG PASOKAN & B2B MARKETPLACE PENGADAAN (INTERNAL PROCUREMENT ONLY)
# ==============================================================================
@procurement_bp.route("/marketplace")
@procurement_bp.route("/catalog")
@login_required
@roles_required("admin", "business_analyst", "marketing", "management", "procurement")
def marketplace():
    """Etalase B2B Marketplace & e-Katalog internal untuk tim procurement memantau seluruh produk pasokan supplier."""
    _ensure_table()
    from sqlalchemy import func
    from app.models import SupplierProduct, User

    search_q = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip().lower()
    stock_status = request.args.get("stock_status", "").strip().lower()
    supplier_id = request.args.get("supplier_id", type=int)
    min_price = request.args.get("min_price", type=float)
    max_price = request.args.get("max_price", type=float)
    sort_by = request.args.get("sort", "newest").strip().lower()
    view_mode = request.args.get("view", "grid").strip().lower()
    page = request.args.get("page", 1, type=int)

    query = SupplierProduct.query.join(ProcurementSupplier, SupplierProduct.supplier_id == ProcurementSupplier.id, isouter=True)

    # Filter keyword (Product Name, SKU, Specs, Desc, Vendor Name)
    if search_q:
        query = query.filter(
            db.or_(
                SupplierProduct.name.ilike(f"%{search_q}%"),
                SupplierProduct.sku.ilike(f"%{search_q}%"),
                SupplierProduct.description.ilike(f"%{search_q}%"),
                SupplierProduct.specifications.ilike(f"%{search_q}%"),
                ProcurementSupplier.company_name.ilike(f"%{search_q}%"),
            )
        )

    # Filter category
    if category:
        query = query.filter(SupplierProduct.category == category)

    # Filter stock status
    if stock_status:
        query = query.filter(SupplierProduct.stock_status == stock_status)

    # Filter specific supplier
    if supplier_id:
        query = query.filter(SupplierProduct.supplier_id == supplier_id)

    # Filter price range
    if min_price is not None:
        query = query.filter(SupplierProduct.price >= min_price)
    if max_price is not None:
        query = query.filter(SupplierProduct.price <= max_price)

    # Sorting
    if sort_by == "price_asc":
        query = query.order_by(SupplierProduct.price.asc())
    elif sort_by == "price_desc":
        query = query.order_by(SupplierProduct.price.desc())
    elif sort_by == "name_asc":
        query = query.order_by(SupplierProduct.name.asc())
    else:  # newest
        query = query.order_by(SupplierProduct.created_at.desc())

    per_page = 16 if view_mode == "grid" else 20
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    products = pagination.items

    # KPI & Metrik Summary
    total_products = SupplierProduct.query.count()
    ready_products_count = SupplierProduct.query.filter_by(stock_status="ready").count()
    
    # Hitung jumlah vendor unik yang telah mengunggah produk
    supplier_count = db.session.query(func.count(func.distinct(SupplierProduct.supplier_id))).scalar() or 0

    # Distribusi kategori
    category_counts_tuples = db.session.query(SupplierProduct.category, func.count(SupplierProduct.id)).group_by(SupplierProduct.category).all()
    category_counts = {str(k).lower(): v for k, v in category_counts_tuples if k}

    # Daftar supplier yang aktif untuk filter dropdown
    active_supplier_ids = [r[0] for r in db.session.query(SupplierProduct.supplier_id).distinct().all() if r[0]]
    active_suppliers = ProcurementSupplier.query.filter(ProcurementSupplier.id.in_(active_supplier_ids)).order_by(ProcurementSupplier.company_name.asc()).all() if active_supplier_ids else []

    # Format produk dengan data supplier fallback jika p.supplier_id null tapi user_id ada
    product_items = []
    for p in products:
        sup = p.supplier
        if not sup and p.user_id:
            sup = ProcurementSupplier.query.filter_by(created_by=p.user_id).first()
        product_items.append({
            "product": p,
            "supplier": sup
        })

    return render_template(
        "procurement/marketplace.html",
        product_items=product_items,
        pagination=pagination,
        filters={
            "q": search_q,
            "category": category,
            "stock_status": stock_status,
            "supplier_id": supplier_id,
            "min_price": min_price,
            "max_price": max_price,
            "sort": sort_by,
            "view": view_mode,
        },
        category_list=CATEGORY_LIST,
        category_counts=category_counts,
        total_products=total_products,
        ready_products_count=ready_products_count,
        supplier_count=supplier_count,
        active_suppliers=active_suppliers,
    )


# ==============================================================================
# 5. MODUL REQUEST FOR QUOTATION (RFQ) / PERMINTAAN PENAWARAN HARGA
# ==============================================================================

@procurement_bp.route("/rfq")
@login_required
@roles_required("admin", "business_analyst", "marketing", "management", "procurement")
def rfq_list():
    """Daftar seluruh Request for Quotation (RFQ) yang dibuat oleh tim Procurement."""
    search_q = request.args.get("q", "").strip()
    status_filter = request.args.get("status", "all").strip().lower()
    category_filter = request.args.get("category", "").strip().lower()
    page = request.args.get("page", 1, type=int)

    query = QuotationRequest.query

    if search_q:
        query = query.join(ProcurementSupplier).filter(
            db.or_(
                QuotationRequest.rfq_code.ilike(f"%{search_q}%"),
                QuotationRequest.title.ilike(f"%{search_q}%"),
                QuotationRequest.specifications.ilike(f"%{search_q}%"),
                ProcurementSupplier.company_name.ilike(f"%{search_q}%"),
            )
        )

    if status_filter and status_filter != "all":
        query = query.filter(QuotationRequest.status == status_filter)

    if category_filter:
        query = query.filter(QuotationRequest.category == category_filter)

    pagination = query.order_by(QuotationRequest.created_at.desc()).paginate(page=page, per_page=15, error_out=False)
    rfqs = pagination.items

    # Ringkasan Metrik
    total_rfq = QuotationRequest.query.count()
    requested_count = QuotationRequest.query.filter_by(status="requested").count()
    submitted_count = QuotationRequest.query.filter_by(status="submitted").count()
    accepted_count = QuotationRequest.query.filter_by(status="accepted").count()
    rejected_count = QuotationRequest.query.filter_by(status="rejected").count()

    # Daftar Supplier untuk modal Create RFQ
    suppliers = ProcurementSupplier.query.order_by(ProcurementSupplier.company_name.asc()).all()

    # Pre-select supplier_id atau product_id jika dipicu dari halaman lain
    selected_supplier_id = request.args.get("supplier_id", type=int)
    selected_product_id = request.args.get("product_id", type=int)

    return render_template(
        "procurement/rfq_list.html",
        rfqs=rfqs,
        pagination=pagination,
        suppliers=suppliers,
        selected_supplier_id=selected_supplier_id,
        selected_product_id=selected_product_id,
        category_list=CATEGORY_LIST,
        metrics={
            "total": total_rfq,
            "requested": requested_count,
            "submitted": submitted_count,
            "accepted": accepted_count,
            "rejected": rejected_count,
        },
        current_status=status_filter,
        current_category=category_filter,
        search_q=search_q,
    )


@procurement_bp.route("/rfq/create", methods=["POST"])
@login_required
@roles_required("admin", "business_analyst", "management", "procurement")
def create_rfq():
    """Membuat Request for Quotation baru dari Procurement ke Supplier."""
    title = request.form.get("title", "").strip()
    supplier_id = request.form.get("supplier_id", type=int)
    category = request.form.get("category", "raw material").strip().lower()
    product_id = request.form.get("product_id", type=int)
    target_quantity = request.form.get("target_quantity", 1, type=int)
    unit = request.form.get("unit", "pcs").strip()
    target_budget_unit = request.form.get("target_budget_unit", type=float)
    target_delivery_str = request.form.get("target_delivery_date", "").strip()
    specifications = request.form.get("specifications", "").strip()
    notes = request.form.get("notes", "").strip()

    if not title or not supplier_id:
        flash("Judul permintaan dan supplier target wajib diisi.", "danger")
        return redirect(url_for("procurement.rfq_list"))

    supplier = ProcurementSupplier.query.get_or_404(supplier_id)

    target_delivery_date = None
    if target_delivery_str:
        try:
            target_delivery_date = datetime.strptime(target_delivery_str, "%Y-%m-%d").date()
        except ValueError:
            target_delivery_date = None

    # Handle file lampiran spesifikasi / TOR jika ada
    attachment_file = request.files.get("attachment")
    attachment_url = _save_rfq_file(attachment_file, prefix="rfq_spec") if attachment_file else None

    rfq_code = _generate_rfq_code()

    rfq = QuotationRequest(
        rfq_code=rfq_code,
        title=title,
        category=category,
        procurement_user_id=current_user.id,
        supplier_id=supplier.id,
        supplier_user_id=supplier.created_by,
        product_id=product_id,
        target_quantity=max(1, target_quantity),
        unit=unit or "pcs",
        target_budget_unit=target_budget_unit,
        target_delivery_date=target_delivery_date,
        specifications=specifications,
        notes=notes,
        rfq_attachment_url=attachment_url,
        status="requested",
    )
    db.session.add(rfq)
    db.session.commit()

    log_activity("create_rfq", f"Procurement {current_user.name} membuat {rfq.rfq_code} untuk {supplier.company_name}")
    flash(f"Permintaan Quotation {rfq.rfq_code} berhasil dibuat dan dikirim ke {supplier.company_name}!", "success")
    return redirect(url_for("procurement.rfq_detail", rfq_id=rfq.id))


@procurement_bp.route("/rfq/<int:rfq_id>")
@login_required
@roles_required("admin", "business_analyst", "marketing", "management", "procurement")
def rfq_detail(rfq_id):
    """Melihat detail lengkap Request for Quotation dan penawaran dari Supplier."""
    rfq = QuotationRequest.query.get_or_404(rfq_id)
    return render_template("procurement/rfq_detail.html", rfq=rfq, category_list=CATEGORY_LIST)


@procurement_bp.route("/rfq/<int:rfq_id>/decision", methods=["POST"])
@login_required
@roles_required("admin", "management", "procurement")
def rfq_decision(rfq_id):
    """Menerima (Accept), Menolak (Reject), atau Membatalkan (Cancel) penawaran harga supplier."""
    rfq = QuotationRequest.query.get_or_404(rfq_id)
    action = request.form.get("action", "").strip().lower()
    decision_notes = request.form.get("decision_notes", "").strip()

    if action == "accept":
        rfq.status = "accepted"
        rfq.decision_notes = decision_notes or "Penawaran harga disetujui oleh tim Procurement Syamanah."
        rfq.decided_at = utc_now()
        rfq.decided_by_id = current_user.id
        db.session.commit()
        log_activity("accept_rfq", f"Procurement menyetujui penawaran {rfq.rfq_code} dari {rfq.supplier.company_name}")
        flash(f"Penawaran harga dari {rfq.supplier.company_name} resmi DISETUJUI!", "success")

    elif action == "reject":
        rfq.status = "rejected"
        rfq.decision_notes = decision_notes or "Penawaran harga belum memenuhi kualifikasi atau anggaran pengadaan."
        rfq.decided_at = utc_now()
        rfq.decided_by_id = current_user.id
        db.session.commit()
        log_activity("reject_rfq", f"Procurement menolak penawaran {rfq.rfq_code} dari {rfq.supplier.company_name}")
        flash(f"Penawaran harga dari {rfq.supplier.company_name} DITOLAK.", "warning")

    elif action == "cancel":
        rfq.status = "cancelled"
        rfq.decision_notes = decision_notes or "Permintaan penawaran dibatalkan oleh Procurement."
        db.session.commit()
        log_activity("cancel_rfq", f"Procurement membatalkan {rfq.rfq_code}")
        flash(f"Permintaan penawaran {rfq.rfq_code} dibatalkan.", "secondary")

    return redirect(url_for("procurement.rfq_detail", rfq_id=rfq.id))


@procurement_bp.route("/rfq/<int:rfq_id>/edit", methods=["POST"])
@login_required
@roles_required("admin", "business_analyst", "management", "procurement")
def edit_rfq(rfq_id):
    """Memperbarui rincian spesifikasi, target kuantitas, budget, atau lampiran TOR RFQ."""
    rfq = QuotationRequest.query.get_or_404(rfq_id)

    title = request.form.get("title", "").strip()
    category = request.form.get("category", rfq.category).strip().lower()
    target_quantity = request.form.get("target_quantity", rfq.target_quantity, type=int)
    unit = request.form.get("unit", rfq.unit).strip()
    target_budget_str = request.form.get("target_budget_unit", "").strip()
    target_delivery_str = request.form.get("target_delivery_date", "").strip()
    specifications = request.form.get("specifications", "").strip()
    notes = request.form.get("notes", "").strip()

    if not title:
        flash("Judul permintaan pengadaan wajib diisi.", "danger")
        return redirect(request.referrer or url_for("procurement.rfq_detail", rfq_id=rfq.id))

    target_budget_unit = None
    if target_budget_str:
        try:
            cleaned_budget = target_budget_str.replace("Rp", "").replace("rp", "").replace(".", "").replace(",", ".").strip()
            target_budget_unit = float(cleaned_budget)
        except ValueError:
            try:
                target_budget_unit = float(target_budget_str)
            except ValueError:
                target_budget_unit = None

    rfq.title = title
    if category in VALID_CATEGORIES:
        rfq.category = category
    rfq.target_quantity = max(1, target_quantity or 1)
    rfq.unit = unit or "pcs"
    rfq.target_budget_unit = target_budget_unit
    rfq.specifications = specifications
    rfq.notes = notes

    # Sinkronisasi total penawaran jika supplier sudah pernah input harga satuan
    if rfq.quotation_price_unit:
        rfq.quotation_total_price = rfq.quotation_price_unit * rfq.target_quantity

    if target_delivery_str:
        try:
            rfq.target_delivery_date = datetime.strptime(target_delivery_str, "%Y-%m-%d").date()
        except ValueError:
            pass
    else:
        rfq.target_delivery_date = None

    # Handle update file lampiran TOR jika ada file baru diunggah
    attachment_file = request.files.get("attachment")
    if attachment_file and attachment_file.filename:
        new_url = _save_rfq_file(attachment_file, prefix="rfq_spec")
        if new_url:
            rfq.rfq_attachment_url = new_url

    rfq.updated_at = utc_now()
    db.session.commit()

    log_activity("edit_rfq", f"Procurement memperbarui data RFQ {rfq.rfq_code}")
    flash(f"Permintaan RFQ {rfq.rfq_code} berhasil diperbarui!", "success")
    return redirect(request.referrer or url_for("procurement.rfq_detail", rfq_id=rfq.id))


@procurement_bp.route("/rfq/<int:rfq_id>/delete", methods=["POST"])
@login_required
@roles_required("admin", "management", "procurement")
def delete_rfq(rfq_id):
    """Menghapus permintaan RFQ secara permanen beserta lampiran berkas terkait."""
    rfq = QuotationRequest.query.get_or_404(rfq_id)
    rfq_code = rfq.rfq_code

    # Hapus file attachment dari static storage jika ada
    static_root = os.path.join(current_app.root_path, "static")
    if rfq.rfq_attachment_url:
        file_path = os.path.join(static_root, rfq.rfq_attachment_url)
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass

    if rfq.quotation_attachment_url:
        file_path = os.path.join(static_root, rfq.quotation_attachment_url)
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass

    db.session.delete(rfq)
    db.session.commit()

    log_activity("delete_rfq", f"Procurement menghapus permanen RFQ {rfq_code}")
    flash(f"Permintaan RFQ {rfq_code} berhasil dihapus permanen.", "success")
    return redirect(url_for("procurement.rfq_list"))

