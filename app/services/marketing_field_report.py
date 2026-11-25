"""Marketing field-intelligence datasets and Excel export helpers."""

import io
from datetime import datetime
from typing import Any, Dict, List

from sqlalchemy import or_

from app.extensions import db
from app.models import Event, EventParticipant, Organization


_SPORT_TERMS = (
    "sport center",
    "sports center",
    "sport centre",
    "sports centre",
    "sport hall",
    "sports hall",
    "gelanggang olahraga",
    "lapangan futsal",
    "futsal center",
    "soccer academy",
    "football academy",
    "sekolah sepak bola",
    "sekolah sepakbola",
    "sepak bola",
    "futsal",
)

_EO_TERMS = (
    "event organizer",
    "event organiser",
    "event management",
    "event production",
    "brand activation",
    "activation agency",
    "aktivasi brand",
    "aktivasi merek",
    "promotor event",
    "event promoter",
    "mice",
)

_EO_EVENT_TERMS = (
    "sport",
    "olahraga",
    "marathon",
    "futsal",
    "sepak bola",
    "football",
    "soccer",
    "brand activation",
    "activation",
    "aktivasi",
)

_AREA_LABELS = {
    "target_areas": "Bandung + Jabodetabek",
    "bandung": "Bandung",
    "jabodetabek": "Jabodetabek",
    "all": "Seluruh Indonesia",
}


def _text_match(columns, terms):
    return or_(*(column.ilike(f"%{term}%") for column in columns for term in terms))


def _acronym_match(columns, acronym: str):
    patterns = (acronym, f"{acronym} %", f"% {acronym} %", f"% {acronym}")
    return or_(*(column.ilike(pattern) for column in columns for pattern in patterns))


def _area_match(area: str):
    bandung = or_(
        Organization.city.ilike("%Bandung%"),
        Organization.address.ilike("%Bandung%"),
    )
    jabodetabek = or_(
        Organization.city.ilike("%Jakarta%"),
        Organization.city.ilike("%Bogor%"),
        Organization.city.ilike("%Depok%"),
        Organization.city.ilike("%Tangerang%"),
        Organization.city.ilike("%Bekasi%"),
        Organization.address.ilike("%Jakarta%"),
        Organization.address.ilike("%Bogor%"),
        Organization.address.ilike("%Depok%"),
        Organization.address.ilike("%Tangerang%"),
        Organization.address.ilike("%Bekasi%"),
        Organization.province.ilike("%DKI Jakarta%"),
    )

    if area == "bandung":
        return bandung
    if area == "jabodetabek":
        return jabodetabek
    if area == "all":
        return None
    return or_(bandung, jabodetabek)


def _event_text(event: Event) -> str:
    return " ".join(
        value or ""
        for value in (event.name, event.event_type, event.description, event.organizer)
    ).lower()


def _event_dict(event: Event) -> Dict[str, Any]:
    return {
        "id": event.id,
        "name": event.name,
        "event_type": event.event_type or "",
        "year": event.event_year or "",
        "date": event.date_display,
        "date_status": "Terkonfirmasi" if event.is_date_confirmed else "Estimasi / TBD",
        "status": event.status or "",
        "organizer": event.organizer or "",
        "city": event.city or "",
        "province": event.province or "",
        "venue": event.venue or "",
        "relevance_score": event.relevance_score or 0,
        "verification_status": event.verification_status or "",
        "website": event.clean_website or "",
        "source_url": event.clean_source_url or "",
    }


def _organization_dict(org: Organization, associated_events: str = "") -> Dict[str, Any]:
    purchasing = org.purchasing_contact
    procurement = org.procurement_contact
    community_pic = org.community_pic_contact
    hr = org.hr_contact
    return {
        "organization_id": org.id,
        "name": org.name,
        "record_source": "Master Organization",
        "organization_type": org.organization_type or "",
        "organization_subtype": org.organization_subtype or "",
        "industry": org.industry or "",
        "sport": org.sport or "",
        "city": org.city or "",
        "province": org.province or "",
        "phone": org.phone or "",
        "email": org.email or "",
        "website": org.clean_website_url or "",
        "domain": org.domain or "",
        "source_url": org.source_url or "",
        "purchasing_phone": purchasing.get("phone", ""),
        "purchasing_email": purchasing.get("email", ""),
        "procurement_phone": procurement.get("phone", ""),
        "procurement_email": procurement.get("email", ""),
        "community_pic_name": community_pic.get("name", ""),
        "community_pic_phone": community_pic.get("phone", ""),
        "community_pic_email": community_pic.get("email", ""),
        "hr_phone": hr.get("phone", ""),
        "hr_email": hr.get("email", ""),
        "opportunity_score": org.opportunity_score or 0,
        "priority_tier": org.priority_tier or "",
        "product_fit": org.product_fit or "",
        "related_events": associated_events,
        "last_seen": org.last_seen.strftime("%Y-%m-%d") if org.last_seen else "",
    }


def get_marketing_field_intelligence(area: str = "target_areas") -> Dict[str, Any]:
    """Return current database records for sports, EO, and 2027 event targets."""
    if area not in _AREA_LABELS:
        area = "target_areas"

    org_text_columns = (
        Organization.name,
        Organization.organization_type,
        Organization.organization_subtype,
        Organization.industry,
        Organization.sport,
        Organization.product_fit,
        Organization.description,
    )
    area_filter = _area_match(area)

    ssb_filter = _acronym_match(
        (Organization.name, Organization.organization_type, Organization.organization_subtype, Organization.industry),
        "SSB",
    )
    sport_query = Organization.query.filter(
        or_(_text_match(org_text_columns, _SPORT_TERMS), ssb_filter)
    )
    eo_text_filter = _text_match(org_text_columns, _EO_TERMS)
    eo_abbreviation_filter = _acronym_match(
        (Organization.name, Organization.organization_type, Organization.organization_subtype),
        "EO",
    )

    events = Event.query.order_by(Event.start_date.asc(), Event.name.asc()).all()
    events_2027 = [_event_dict(event) for event in events if event.event_year == 2027]

    relevant_organizer_events = [
        event for event in events
        if event.organizer and any(term in _event_text(event) for term in _EO_EVENT_TERMS)
    ]
    eo_event_ids = [event.id for event in relevant_organizer_events]
    organization_event_names: Dict[int, List[str]] = {}
    if eo_event_ids:
        organizer_event_rows = (
            db.session.query(
                EventParticipant.organization_id,
                Event.name,
            )
            .join(Event, Event.id == EventParticipant.event_id)
            .filter(
                EventParticipant.event_id.in_(eo_event_ids),
                EventParticipant.role == "organizer",
            )
            .all()
        )
        for row in organizer_event_rows:
            organization_event_names.setdefault(row.organization_id, []).append(row.name)

    organizer_org_ids = list(organization_event_names)
    eo_query = Organization.query.filter(
        or_(
            eo_text_filter,
            eo_abbreviation_filter,
            Organization.id.in_(organizer_org_ids),
        )
    )

    if area_filter is not None:
        sport_query = sport_query.filter(area_filter)
        eo_query = eo_query.filter(area_filter)

    sport_orgs = sport_query.order_by(Organization.opportunity_score.desc(), Organization.name).all()
    sport_targets = [_organization_dict(org) for org in sport_orgs]

    eo_accounts = []
    eo_names = set()
    for org in eo_query.order_by(Organization.opportunity_score.desc(), Organization.name).all():
        name_key = (org.name or "").strip().casefold()
        eo_names.add(name_key)
        related_events = ", ".join(organization_event_names.get(org.id, []))
        record = _organization_dict(org, related_events)
        record["match_type"] = "Master Organization"
        eo_accounts.append(record)

    for event in relevant_organizer_events:
        organizer_name = (event.organizer or "").strip()
        name_key = organizer_name.casefold()
        if not organizer_name or name_key in eo_names:
            continue
        eo_names.add(name_key)
        eo_accounts.append({
            "name": organizer_name,
            "record_source": "Event Intelligence",
            "organization_type": "Event Organizer",
            "organization_subtype": "",
            "industry": event.event_type or "",
            "sport": "",
            "city": event.city or "",
            "province": event.province or "",
            "phone": "",
            "email": "",
            "website": event.clean_website or "",
            "domain": "",
            "source_url": event.clean_source_url or "",
            "opportunity_score": 0,
            "priority_tier": "",
            "product_fit": "",
            "related_events": event.name,
            "last_seen": "",
            "match_type": "Organizer dari event olahraga/aktivasi",
        })

    from app.services.google_trends_service import get_comparative_apparel_trends

    comparative_trends = get_comparative_apparel_trends()
    trend_keys = ("jersey", "jaket", "seragam")
    trend_summary = []
    trend_rows = []
    for key in trend_keys:
        values = comparative_trends["series"][key]
        peak_value = max(values)
        peak_month = comparative_trends["months"][values.index(peak_value)]
        trend_summary.append({
            "product": comparative_trends["labels"][key],
            "peak_month": peak_month,
            "peak_index": peak_value,
            "average_index": round(sum(values) / len(values), 1),
            "relative_share": comparative_trends["shares"][key],
        })
        for month, value in zip(comparative_trends["months"], values):
            trend_rows.append({
                "product": comparative_trends["labels"][key],
                "month": month,
                "interest_index": value,
                "peak_month": peak_month,
                "peak_index": peak_value,
                "average_index": round(sum(values) / len(values), 1),
                "relative_share": comparative_trends["shares"][key],
            })

    return {
        "area": area,
        "area_label": _AREA_LABELS[area],
        "generated_at": datetime.now(),
        "sport_targets": sport_targets,
        "eo_accounts": eo_accounts,
        "trend_summary": trend_summary,
        "trend_rows": trend_rows,
        "events_2027": events_2027,
        "trend_disclaimer": (
            "Indeks tren ini berasal dari seri indikatif yang tertanam pada modul saat ini. "
            "Bukan data Google Trends aktual dan bukan hasil pengukuran tren tahun 2027."
        ),
    }


def create_marketing_field_intelligence_workbook(report: Dict[str, Any]) -> io.BytesIO:
    """Build an Excel workbook containing the four requested marketing datasets."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    info = wb.active
    info.title = "Petunjuk"
    info.append(["Laporan Marketing Intelligence"])
    info.append(["Wilayah akun", report["area_label"]])
    info.append(["Dibuat pada", report["generated_at"].strftime("%Y-%m-%d %H:%M")])
    info.append(["Sumber akun dan event", "Data yang saat ini tersimpan di Master Organization dan Event Intelligence"])
    info.append(["Catatan tren", report["trend_disclaimer"]])
    info["A1"].font = Font(bold=True, size=14, color="FFFFFF")
    info["A1"].fill = PatternFill("solid", fgColor="17365D")
    info.column_dimensions["A"].width = 28
    info.column_dimensions["B"].width = 110
    info.freeze_panes = "A2"

    sheets = (
        (
            "Sport Center & SSB",
            report["sport_targets"],
            (
                "organization_id", "name", "record_source", "organization_type", "organization_subtype", "sport",
                "industry", "city", "province", "phone", "email", "purchasing_phone",
                "purchasing_email", "community_pic_name", "community_pic_phone",
                "community_pic_email", "website", "domain", "source_url",
                "opportunity_score", "priority_tier", "product_fit", "last_seen",
            ),
        ),
        (
            "EO & Activation",
            report["eo_accounts"],
            (
                "name", "record_source", "match_type", "organization_type", "industry",
                "city", "province", "phone", "email", "purchasing_phone", "purchasing_email",
                "community_pic_name", "community_pic_phone", "community_pic_email",
                "website", "source_url", "related_events",
                "opportunity_score", "priority_tier",
            ),
        ),
        (
            "Tren Produk",
            report["trend_rows"],
            (
                "product", "month", "interest_index", "peak_month", "peak_index",
                "average_index", "relative_share",
            ),
        ),
        (
            "Event 2027",
            report["events_2027"],
            (
                "id", "name", "event_type", "year", "date", "date_status", "status", "organizer",
                "city", "province", "venue", "relevance_score", "verification_status",
                "website", "source_url",
            ),
        ),
    )

    for title, records, fields in sheets:
        ws = wb.create_sheet(title=title)
        ws.append(list(fields))
        for record in records:
            ws.append([_safe_spreadsheet_value(record.get(field, "")) for field in fields])
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions
        for cell in ws[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="17365D")
        for column_index, field in enumerate(fields, start=1):
            values = [str(field)] + [
                str(record.get(field, "") or "") for record in records[:100]
            ]
            width = min(max(max((len(value) for value in values), default=12) + 2, 12), 48)
            ws.column_dimensions[get_column_letter(column_index)].width = width

    stream = io.BytesIO()
    wb.save(stream)
    stream.seek(0)
    return stream


def _safe_spreadsheet_value(value: Any) -> Any:
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
        return "'" + value
    return value
