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


def parse_whatsapp(phone, company_name=None):
    """
    Menganalisis nomor telepon untuk WhatsApp:
    1. Membersihkan karakter non-digit.
    2. Menormalisasi format Indonesia:
       - 08xxx -> 628xxx
       - 6208xxx -> 628xxx
       - +62 8xxx -> 628xxx
       - 8xxx (panjang 9-13) -> 628xxx
    3. Mengidentifikasi tipe:
       - 'mobile' (awalan 628xxx, panjang 10-15 digit): Potensi nomor WhatsApp aktif / seluler.
       - 'landline' (awalan 021, 022, 024, 031, dll / PSTN): Telepon kantor kabel, BUKAN WhatsApp.
       - 'invalid' / 'none': Nomor kosong, rusak, atau di luar standar.
    4. Menyusun template pesan pembuka bisnis yang dipersonalisasi.
    5. Mengembalikan dictionary terstruktur untuk UI rendering & tombol aksi.
    """
    import re
    import urllib.parse

    if not phone or str(phone).strip().lower() in ("none", "nan", "-", "", "null"):
        return {
            "raw": "",
            "clean": "",
            "is_valid_wa": False,
            "type": "none",
            "type_label": "Tidak Ada Nomor",
            "tooltip": "Nomor telepon belum tersedia.",
            "wa_number": None,
            "wa_url": None,
            "formatted_display": "-",
            "default_message": "",
        }

    p_str = str(phone).strip()
    digits = re.sub(r"\D", "", p_str)

    # Deteksi dan normalisasi format nomor Indonesia
    normalized = digits
    if normalized.startswith("6208"):
        normalized = "628" + normalized[4:]
    elif normalized.startswith("08"):
        normalized = "628" + normalized[2:]
    elif normalized.startswith("8") and 9 <= len(normalized) <= 13:
        normalized = "628" + normalized[1:]

    is_mobile = normalized.startswith("628") and 10 <= len(normalized) <= 15
    is_landline = (
        digits.startswith(("02", "03", "04", "05", "06", "07", "09"))
        or digits.startswith(("622", "623", "624", "625", "627", "629"))
    ) and not is_mobile

    company = company_name.strip() if company_name else "Bapak/Ibu"
    default_msg = (
        f"Halo Tim {company},\n\n"
        f"Perkenalkan kami dari Syamanah Market Intelligence. "
        f"Kami tertarik untuk berdiskusi terkait potensi kolaborasi bisnis dengan {company}.\n\n"
        f"Apakah kami dapat terhubung dengan perwakilan terkait? Terima kasih banyak."
    )
    encoded_msg = urllib.parse.quote(default_msg)

    if is_mobile:
        wa_num = normalized
        body = wa_num[2:]
        if len(body) >= 10:
            formatted_display = f"+62 {body[:3]}-{body[3:7]}-{body[7:]}"
        else:
            formatted_display = f"+62 {body[:3]}-{body[3:]}"

        return {
            "raw": p_str,
            "clean": digits,
            "is_valid_wa": True,
            "type": "mobile",
            "type_label": "WhatsApp Seluler",
            "tooltip": f"Nomor WhatsApp Seluler Aktif ({formatted_display}). Klik untuk kirim pesan otomatis.",
            "wa_number": wa_num,
            "wa_url": f"https://wa.me/{wa_num}?text={encoded_msg}",
            "formatted_display": formatted_display,
            "default_message": default_msg,
        }
    elif is_landline:
        return {
            "raw": p_str,
            "clean": digits,
            "is_valid_wa": False,
            "type": "landline",
            "type_label": "Telepon Kantor (PSTN)",
            "tooltip": f"Nomor ini adalah telepon kantor PSTN ({p_str}), bukan nomor seluler WhatsApp. Tidak disarankan kirim WA.",
            "wa_number": None,
            "wa_url": None,
            "formatted_display": p_str,
            "default_message": default_msg,
        }
    else:
        return {
            "raw": p_str,
            "clean": digits,
            "is_valid_wa": False,
            "type": "invalid",
            "type_label": "Format Tidak Valid",
            "tooltip": f"Format nomor ({p_str}) tidak valid untuk pengiriman WhatsApp.",
            "wa_number": None,
            "wa_url": None,
            "formatted_display": p_str,
            "default_message": default_msg,
        }


# 38 Provinsi Resmi Republik Indonesia
INDONESIA_PROVINCES = [
    # Sumatera
    "Aceh", "Sumatera Utara", "Sumatera Barat", "Riau", "Kepulauan Riau", "Jambi",
    "Sumatera Selatan", "Kepulauan Bangka Belitung", "Bengkulu", "Lampung",
    # Jawa
    "DKI Jakarta", "Jawa Barat", "Banten", "Jawa Tengah", "DI Yogyakarta", "Jawa Timur",
    # Bali & Nusa Tenggara
    "Bali", "Nusa Tenggara Barat", "Nusa Tenggara Timur",
    # Kalimantan
    "Kalimantan Barat", "Kalimantan Tengah", "Kalimantan Selatan", "Kalimantan Timur", "Kalimantan Utara",
    # Sulawesi
    "Sulawesi Utara", "Gorontalo", "Sulawesi Tengah", "Sulawesi Barat", "Sulawesi Selatan", "Sulawesi Tenggara",
    # Maluku & Papua
    "Maluku", "Maluku Utara", "Papua", "Papua Barat", "Papua Selatan", "Papua Tengah", "Papua Pegunungan", "Papua Barat Daya"
]


def get_all_indonesia_provinces(existing_provinces: list = None) -> list:
    """Menggabungkan 38 provinsi resmi Indonesia dengan provinsi yang ada di database."""
    base_set = set(INDONESIA_PROVINCES)
    if existing_provinces:
        for p in existing_provinces:
            if p and p.strip() and p.lower() != "nan":
                base_set.add(p.strip())
    return sorted(list(base_set))


