from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user
from app.extensions import db
from app.models import User
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
