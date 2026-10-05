import os
import time
from werkzeug.utils import secure_filename
from flask import Blueprint, flash, redirect, render_template, request, url_for, current_app
from flask_login import current_user, login_required

from app.extensions import db
from app.models import ProcurementSupplier, SupplierProduct, User
from app.utils import log_activity, roles_required, allowed_file

supplier_bp = Blueprint("supplier", __name__)

ALLOWED_CATALOG_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "pdf", "docx", "xlsx"}

CATEGORY_LIST = [
    {"key": "raw material", "label": "Raw Material", "badge": "bg-primary"},
    {"key": "distributor", "label": "Distributor", "badge": "bg-success"},
    {"key": "elektrikal", "label": "Elektrikal", "badge": "bg-warning text-dark"},
    {"key": "services", "label": "Services", "badge": "bg-info text-dark"},
    {"key": "pharmaceutical", "label": "Pharmaceutical", "badge": "bg-danger"},
    {"key": "local", "label": "Local Supplier", "badge": "bg-secondary"},
    {"key": "hardware", "label": "Hardware", "badge": "bg-dark"},
    {"key": "software", "label": "Software", "badge": "bg-primary"},
]


def _get_or_create_supplier_profile(user_id):
    """Mengambil atau menginisialisasi entitas ProcurementSupplier untuk pengguna supplier."""
    supplier = ProcurementSupplier.query.filter_by(created_by=user_id).first()
    if not supplier:
        user = db.session.get(User, user_id)
        supplier = ProcurementSupplier(
            company_name=user.name if user else "Perusahaan Mitra",
            product="raw material",
            material="Katalog Produk & Pasokan B2B",
            region="Indonesia",
            contact_email=user.email if user else None,
            source_url=f"https://supplier.syamanah.id/vendor/{user_id}",
            description="Mitra rekanan B2B resmi terdaftar di portal Syamanah Tender.",
            fit_score=85,
            verification_status="verified",
            created_by=user_id,
        )
        db.session.add(supplier)
        db.session.commit()
    return supplier


def _save_uploaded_file(file_storage):
    """Menyimpan file upload (gambar produk atau brosur PDF) dengan aman."""
    if not file_storage or not file_storage.filename:
        return None
    if not allowed_file(file_storage.filename, ALLOWED_CATALOG_EXTENSIONS):
        return None
    filename = secure_filename(file_storage.filename)
    timestamp = int(time.time())
    unique_filename = f"catalog_{current_user.id}_{timestamp}_{filename}"
    upload_dir = os.path.join(current_app.config["UPLOAD_FOLDER"], "catalogs")
    os.makedirs(upload_dir, exist_ok=True)
    target_path = os.path.join(upload_dir, unique_filename)
    file_storage.save(target_path)
    return f"uploads/catalogs/{unique_filename}"


@supplier_bp.route("/")
@login_required
@roles_required("supplier", "admin")
def index():
    """Halaman beranda portal rekanan supplier."""
    return redirect(url_for("dashboard"))


@supplier_bp.route("/catalog")
@login_required
@roles_required("supplier", "admin")
def catalog():
    """Manajemen katalog produk (CRUD) untuk supplier yang login."""
    supplier = _get_or_create_supplier_profile(current_user.id)
    cat_filter = request.args.get("category", "").strip().lower()
    search_q = request.args.get("q", "").strip()

    query = SupplierProduct.query.filter_by(user_id=current_user.id)
    if cat_filter:
        query = query.filter_by(category=cat_filter)
    if search_q:
        query = query.filter(
            db.or_(
                SupplierProduct.name.ilike(f"%{search_q}%"),
                SupplierProduct.sku.ilike(f"%{search_q}%"),
                SupplierProduct.description.ilike(f"%{search_q}%"),
                SupplierProduct.specifications.ilike(f"%{search_q}%"),
            )
        )

    products = query.order_by(SupplierProduct.created_at.desc()).all()

    # Hitung distribusi per kategori dari seluruh produk user ini
    all_products = SupplierProduct.query.filter_by(user_id=current_user.id).all()
    category_counts = {}
    for p in all_products:
        category_counts[p.category] = category_counts.get(p.category, 0) + 1

    completeness = supplier.calculate_completeness()

    return render_template(
        "supplier/catalog.html",
        supplier=supplier,
        products=products,
        total_products=len(all_products),
        category_counts=category_counts,
        category_list=CATEGORY_LIST,
        active_cat=cat_filter,
        search_q=search_q,
        completeness=completeness,
    )


@supplier_bp.route("/catalog/add", methods=["POST"])
@login_required
@roles_required("supplier", "admin")
def catalog_add():
    """Menambahkan item produk baru ke katalog."""
    supplier = _get_or_create_supplier_profile(current_user.id)
    name = request.form.get("name", "").strip()
    if not name:
        flash("Nama produk/material wajib diisi.", "warning")
        return redirect(url_for("supplier.catalog"))

    sku = request.form.get("sku", "").strip()
    if not sku:
        sku = f"SKU-{current_user.id}-{int(time.time()) % 100000:05d}"

    category = request.form.get("category", "raw material").strip().lower()
    price_raw = request.form.get("price", "0").strip()
    try:
        price = float(price_raw) if price_raw else 0.0
    except ValueError:
        price = 0.0

    unit = request.form.get("unit", "pcs").strip() or "pcs"
    min_order = request.form.get("min_order", "1").strip() or "1"
    lead_time = request.form.get("lead_time", "Ready Stock").strip() or "Ready Stock"
    stock_status = request.form.get("stock_status", "ready").strip() or "ready"
    description = request.form.get("description", "").strip()
    specifications = request.form.get("specifications", "").strip()

    file_storage = request.files.get("catalog_file")
    file_path = _save_uploaded_file(file_storage)

    product = SupplierProduct(
        supplier_id=supplier.id,
        user_id=current_user.id,
        sku=sku,
        name=name,
        category=category,
        description=description,
        specifications=specifications,
        price=price,
        unit=unit,
        min_order=min_order,
        lead_time=lead_time,
        stock_status=stock_status,
        file_path=file_path,
    )
    db.session.add(product)
    db.session.commit()

    log_activity("supplier_add_product", f"Supplier {current_user.name} menambahkan produk {name} ({sku})")
    flash(f"Produk '{name}' berhasil ditambahkan ke katalog Syamanah Tender.", "success")
    return redirect(url_for("supplier.catalog"))


@supplier_bp.route("/catalog/<int:product_id>/edit", methods=["POST"])
@login_required
@roles_required("supplier", "admin")
def catalog_edit(product_id):
    """Memperbarui informasi produk katalog."""
    product = db.session.get(SupplierProduct, product_id)
    if not product:
        flash("Produk tidak ditemukan.", "warning")
        return redirect(url_for("supplier.catalog"))

    if current_user.role != "admin" and product.user_id != current_user.id:
        flash("Anda tidak memiliki hak akses mengubah produk ini.", "danger")
        return redirect(url_for("supplier.catalog"))

    name = request.form.get("name", "").strip()
    if name:
        product.name = name
    product.sku = request.form.get("sku", product.sku).strip()
    product.category = request.form.get("category", product.category).strip().lower()

    price_raw = request.form.get("price", "").strip()
    if price_raw:
        try:
            product.price = float(price_raw)
        except ValueError:
            pass

    product.unit = request.form.get("unit", product.unit).strip() or "pcs"
    product.min_order = request.form.get("min_order", product.min_order).strip() or "1"
    product.lead_time = request.form.get("lead_time", product.lead_time).strip() or "Ready Stock"
    product.stock_status = request.form.get("stock_status", product.stock_status).strip() or "ready"
    product.description = request.form.get("description", product.description).strip()
    product.specifications = request.form.get("specifications", product.specifications).strip()

    file_storage = request.files.get("catalog_file")
    new_file_path = _save_uploaded_file(file_storage)
    if new_file_path:
        product.file_path = new_file_path

    db.session.commit()
    log_activity("supplier_edit_product", f"Supplier {current_user.name} mengubah produk {product.name} ({product.sku})")
    flash(f"Informasi produk '{product.name}' berhasil diperbarui.", "success")
    return redirect(url_for("supplier.catalog"))


@supplier_bp.route("/catalog/<int:product_id>/delete", methods=["POST"])
@login_required
@roles_required("supplier", "admin")
def catalog_delete(product_id):
    """Menghapus item produk dari katalog."""
    product = db.session.get(SupplierProduct, product_id)
    if not product:
        flash("Produk tidak ditemukan.", "warning")
        return redirect(url_for("supplier.catalog"))

    if current_user.role != "admin" and product.user_id != current_user.id:
        flash("Anda tidak memiliki hak akses menghapus produk ini.", "danger")
        return redirect(url_for("supplier.catalog"))

    name = product.name
    db.session.delete(product)
    db.session.commit()

    log_activity("supplier_delete_product", f"Supplier {current_user.name} menghapus produk {name}")
    flash(f"Produk '{name}' berhasil dihapus dari katalog.", "success")
    return redirect(url_for("supplier.catalog"))


@supplier_bp.route("/profile", methods=["GET", "POST"])
@login_required
@roles_required("supplier", "admin")
def profile():
    """Melengkapi dan memperbarui profil perusahaan mitra rekanan."""
    supplier = _get_or_create_supplier_profile(current_user.id)

    if request.method == "POST":
        company_name = request.form.get("company_name", "").strip()
        business_entity = request.form.get("business_entity", "PT").strip()
        product = request.form.get("product", "raw material").strip().lower()
        material = request.form.get("material", "").strip()
        region = request.form.get("region", "").strip()
        city = request.form.get("city", "").strip()
        province = request.form.get("province", "").strip()
        address = request.form.get("address", "").strip()
        website = request.form.get("website", "").strip()
        contact_email = request.form.get("contact_email", "").strip().lower()
        contact_phone = request.form.get("contact_phone", "").strip()
        pic_name = request.form.get("pic_name", "").strip()
        pic_position = request.form.get("pic_position", "").strip()
        npwp = request.form.get("npwp", "").strip()
        nib = request.form.get("nib", "").strip()
        description = request.form.get("description", "").strip()

        if company_name:
            supplier.company_name = company_name
        if product:
            supplier.product = product
        supplier.material = material or supplier.material
        supplier.region = region or (f"{city}, {province}" if city and province else city or province or supplier.region)
        supplier.website = website or supplier.website
        supplier.contact_email = contact_email or supplier.contact_email
        supplier.contact_phone = contact_phone or supplier.contact_phone
        supplier.description = description or supplier.description

        # Update JSON profil lengkap
        profile_dict = {
            "business_entity": business_entity,
            "address": address,
            "city": city,
            "province": province,
            "pic_name": pic_name or current_user.name,
            "pic_position": pic_position,
            "npwp": npwp,
            "nib": nib,
        }
        supplier.update_profile_data(profile_dict)

        # Update nama user jika PIC diisi
        if pic_name and current_user.name != pic_name:
            current_user.name = pic_name

        db.session.commit()
        log_activity("supplier_update_profile", f"Supplier {supplier.company_name} memperbarui profil perusahaan")
        flash("Profil perusahaan berhasil diperbarui!", "success")
        return redirect(url_for("supplier.profile"))

    profile_data = supplier.get_profile_data()
    completeness = supplier.calculate_completeness()

    return render_template(
        "supplier/profile.html",
        supplier=supplier,
        profile_data=profile_data,
        completeness=completeness,
        category_list=CATEGORY_LIST,
    )
