import ipaddress
import socket
from functools import wraps
from urllib.parse import urlparse
from flask import abort
from flask_login import current_user
from app.extensions import db
from app.models import ActivityLog


def log_activity(action: str, detail: str = ""):
    """Dipakai oleh berbagai use case untuk mengisi modul '7. System Management -> Melihat Log Aktivitas'."""
    try:
        entry = ActivityLog(
            user_id=current_user.id if current_user.is_authenticated else None,
            action=action,
            detail=detail,
        )
        db.session.add(entry)
        db.session.commit()
    except Exception:
        db.session.rollback()


def roles_required(*roles):
    """Memeriksa role pengguna. Role 'admin' bertindak sebagai superuser dengan akses penuh."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if current_user.role != "admin" and current_user.role not in roles:
                abort(403)
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def allowed_file(filename, allowed_extensions):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed_extensions


def is_safe_url(url: str) -> bool:
    """Mencegah SSRF dengan memvalidasi skema http/https dan memblokir IP privat/loopback."""
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        hostname = parsed.hostname
        if not hostname:
            return False
        if hostname.lower() in ("localhost", "127.0.0.1", "::1"):
            return False
        addr_info = socket.getaddrinfo(hostname, None)
        for _, _, _, _, sockaddr in addr_info:
            ip_str = sockaddr[0]
            ip = ipaddress.ip_address(ip_str)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
                return False
        return True
    except Exception:
        return False

