import json
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user
from app.extensions import db
from app.models import User, ProcurementSupplier
from app.utils import log_activity

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password) and user.is_active:
            login_user(user)
            log_activity("login", f"User {user.email} login")
            return redirect(url_for("dashboard"))
        flash("Email atau password salah.", "danger")
    return render_template("auth/login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    log_activity("logout", f"User {current_user.email} logout")
    logout_user()
    return redirect(url_for("auth.login"))


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    # Registrasi pertama kali dipakai untuk membuat akun admin awal.
    if User.query.count() > 0 and not (current_user.is_authenticated and current_user.role == "admin"):
        flash("Registrasi mandiri dinonaktifkan. Hubungi Admin/IT.", "warning")
        return redirect(url_for("auth.login"))
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password")
        role = request.form.get("role", "business_analyst")
        if User.query.filter_by(email=email).first():
            flash("Email sudah terdaftar.", "danger")
        else:
            user = User(name=name, email=email, role=role)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            flash("Akun berhasil dibuat, silakan login.", "success")
            return redirect(url_for("auth.login"))
    return render_template("auth/register.html")


@auth_bp.route("/register-supplier", methods=["GET", "POST"])
def register_supplier():
    """Portal Registrasi Rekanan Supplier Bahan Apparel.
    Setiap pendaftar melalui rute ini otomatis mendapatkan role 'supplier'.
    """
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        company_name = request.form.get("company_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        phone = request.form.get("phone", "").strip()
        product = request.form.get("product", "raw material").strip().lower()
        if product in {"jersey", "kaos", "polo", "kemeja", "jaket"}:
            product = "raw material"
        material = request.form.get("material", "").strip()
        region = request.form.get("region", "").strip()
        website = request.form.get("website", "").strip()

        if not email or not password or not name or not company_name:
            flash("Nama PIC, Nama Perusahaan/Supplier, Email, dan Password wajib diisi.", "warning")
            return render_template("auth/register_supplier.html", form=request.form)

        if User.query.filter(db.func.lower(User.email) == email).first():
            flash("Email sudah terdaftar. Silakan login atau gunakan email lain.", "danger")
            return render_template("auth/register_supplier.html", form=request.form)

        try:
            # 1. Pastikan role SELALU 'supplier'
            user = User(name=name, email=email, role="supplier")
            user.set_password(password)
            db.session.add(user)
            db.session.flush()

            # 2. Buat profil di ProcurementSupplier
            clean_source_url = website.rstrip("/") if website else f"https://supplier.portal/reg/{user.id}"
            existing_sup = ProcurementSupplier.query.filter(
                ProcurementSupplier.product == product,
                ProcurementSupplier.source_url == clean_source_url
            ).first()

            if not existing_sup:
                rec_data = {
                    "fit_score": 88,
                    "recommendation": f"Mitra supplier/vendor B2B terdaftar: {company_name} ({product}).",
                    "next_steps": ["Verifikasi katalog produk/layanan & legalitas", "Hubungi nomor WhatsApp/kontak supplier", "Evaluasi kesesuaian harga & SLA"],
                    "confidence": "high"
                }
                supplier = ProcurementSupplier(
                    company_name=company_name,
                    product=product,
                    material=material or "Katalog Produk & Layanan B2B",
                    region=region or "Indonesia",
                    website=website or None,
                    source_url=clean_source_url,
                    contact_email=email,
                    contact_phone=phone or None,
                    description=f"Mitra rekanan B2B resmi terdaftar melalui portal supplier. Spesialisasi: {material or product}.",
                    fit_score=88,
                    recommendation_json=json.dumps(rec_data, ensure_ascii=False),
                    verification_status="verified",
                    created_by=user.id,
                )
                db.session.add(supplier)

            db.session.commit()
            log_activity("register_supplier", f"Supplier {company_name} ({email}) berhasil mendaftar")
            flash("Registrasi supplier berhasil! Akun Anda aktif dengan hak akses Rekanan Supplier. Silakan login.", "success")
            return redirect(url_for("auth.login"))
        except Exception as e:
            db.session.rollback()
            flash(f"Gagal melakukan registrasi supplier: {e}", "danger")

    return render_template("auth/register_supplier.html")
