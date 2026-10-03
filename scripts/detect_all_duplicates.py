import os
import sys
import json
from collections import defaultdict

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import create_app, db
from app.models import (
    Organization, Prospect, ProcurementSupplier, Event, 
    EventParticipant, DuplicateCandidate, User, DataSource, DiscoverySource
)
from sqlalchemy import text, func

app = create_app()

with app.app_context():
    print("=" * 80)
    print("ANALISIS DUPLIKASI DATA DI SETIAP TABEL / MODUL")
    print("=" * 80)

    # 1. ORGANIZATIONS
    print("\n--- 1. ORGANIZATIONS (Total:", Organization.query.count(), ") ---")
    
    # By normalized_name
    dup_org_norm = db.session.query(
        Organization.normalized_name, func.count(Organization.id)
    ).filter(Organization.normalized_name.isnot(None), Organization.normalized_name != '')\
     .group_by(Organization.normalized_name)\
     .having(func.count(Organization.id) > 1)\
     .all()
    print(f"Duplikat berdasarkan normalized_name: {len(dup_org_norm)} kelompok (Total kelebihan baris: {sum(c - 1 for _, c in dup_org_norm)})")
    for name, cnt in dup_org_norm[:10]:
        print(f"  - '{name}': {cnt} baris")

    # By exact name
    dup_org_name = db.session.query(
        func.lower(Organization.name), func.count(Organization.id)
    ).group_by(func.lower(Organization.name))\
     .having(func.count(Organization.id) > 1)\
     .all()
    print(f"Duplikat berdasarkan lower(name): {len(dup_org_name)} kelompok (Total kelebihan baris: {sum(c - 1 for _, c in dup_org_name)})")

    # By domain (non-empty, non-generic)
    dup_org_dom = db.session.query(
        Organization.domain, func.count(Organization.id)
    ).filter(Organization.domain.isnot(None), Organization.domain != '')\
     .group_by(Organization.domain)\
     .having(func.count(Organization.id) > 1)\
     .all()
    print(f"Duplikat berdasarkan domain: {len(dup_org_dom)} kelompok (Total kelebihan baris: {sum(c - 1 for _, c in dup_org_dom)})")

    # 2. PROSPECTS
    print("\n--- 2. PROSPECTS (Total:", Prospect.query.count(), ") ---")
    
    # By lower(company_name)
    dup_prospect_name = db.session.query(
        func.lower(Prospect.company_name), func.count(Prospect.id)
    ).group_by(func.lower(Prospect.company_name))\
     .having(func.count(Prospect.id) > 1)\
     .all()
    print(f"Duplikat berdasarkan lower(company_name): {len(dup_prospect_name)} kelompok (Total kelebihan baris: {sum(c - 1 for _, c in dup_prospect_name)})")
    for name, cnt in dup_prospect_name[:10]:
        print(f"  - '{name}': {cnt} baris")

    # By organization_id
    dup_prospect_org = db.session.query(
        Prospect.organization_id, func.count(Prospect.id)
    ).filter(Prospect.organization_id.isnot(None))\
     .group_by(Prospect.organization_id)\
     .having(func.count(Prospect.id) > 1)\
     .all()
    print(f"Duplikat berdasarkan organization_id (1 Org punya >1 Prospect): {len(dup_prospect_org)} orgs (Total kelebihan baris: {sum(c - 1 for _, c in dup_prospect_org)})")

    # 3. PROCUREMENT SUPPLIERS
    print("\n--- 3. PROCUREMENT SUPPLIERS (Total:", ProcurementSupplier.query.count(), ") ---")
    dup_supp_name = db.session.query(
        func.lower(ProcurementSupplier.company_name), ProcurementSupplier.product, func.count(ProcurementSupplier.id)
    ).group_by(func.lower(ProcurementSupplier.company_name), ProcurementSupplier.product)\
     .having(func.count(ProcurementSupplier.id) > 1)\
     .all()
    print(f"Duplikat supplier (lower(name) + product): {len(dup_supp_name)} kelompok (Total kelebihan: {sum(c - 1 for _, _, c in dup_supp_name)})")
    for name, prod, cnt in dup_supp_name:
        print(f"  - '{name}' (product={prod}): {cnt} baris")

    # By source_url + product
    dup_supp_url = db.session.query(
        ProcurementSupplier.source_url, ProcurementSupplier.product, func.count(ProcurementSupplier.id)
    ).filter(ProcurementSupplier.source_url.isnot(None), ProcurementSupplier.source_url != '')\
     .group_by(ProcurementSupplier.source_url, ProcurementSupplier.product)\
     .having(func.count(ProcurementSupplier.id) > 1)\
     .all()
    print(f"Duplikat supplier (source_url + product): {len(dup_supp_url)} kelompok (Total kelebihan: {sum(c - 1 for _, _, c in dup_supp_url)})")
    for url, prod, cnt in dup_supp_url[:10]:
        print(f"  - '{url}' (product={prod}): {cnt} baris")

    # 4. EVENTS
    print("\n--- 4. EVENTS (Total:", Event.query.count(), ") ---")
    dup_event_name = db.session.query(
        func.lower(Event.name), func.count(Event.id)
    ).group_by(func.lower(Event.name))\
     .having(func.count(Event.id) > 1)\
     .all()
    print(f"Duplikat event berdasarkan lower(name): {len(dup_event_name)} kelompok (Total kelebihan: {sum(c - 1 for _, c in dup_event_name)})")
    for name, cnt in dup_event_name:
        print(f"  - '{name}': {cnt} baris")

    dup_event_url = db.session.query(
        Event.website, func.count(Event.id)
    ).filter(Event.website.isnot(None), Event.website != '')\
     .group_by(Event.website)\
     .having(func.count(Event.id) > 1)\
     .all()
    print(f"Duplikat event berdasarkan website: {len(dup_event_url)} kelompok")

    # 5. EVENT PARTICIPANTS
    print("\n--- 5. EVENT PARTICIPANTS (Total:", EventParticipant.query.count(), ") ---")
    dup_part = db.session.query(
        EventParticipant.event_id, EventParticipant.organization_id, EventParticipant.role, func.count(EventParticipant.id)
    ).group_by(EventParticipant.event_id, EventParticipant.organization_id, EventParticipant.role)\
     .having(func.count(EventParticipant.id) > 1)\
     .all()
    print(f"Duplikat peserta event (event_id + org_id + role): {len(dup_part)} kelompok (Total kelebihan: {sum(c - 1 for _, _, _, c in dup_part)})")

    # 6. DUPLICATE CANDIDATES
    print("\n--- 6. DUPLICATE CANDIDATES (Total:", DuplicateCandidate.query.count(), ") ---")
    dup_cand = db.session.query(
        DuplicateCandidate.organization_id, DuplicateCandidate.candidate_name, func.count(DuplicateCandidate.id)
    ).group_by(DuplicateCandidate.organization_id, DuplicateCandidate.candidate_name)\
     .having(func.count(DuplicateCandidate.id) > 1)\
     .all()
    print(f"Duplikat candidate review (organization_id + candidate_name): {len(dup_cand)} kelompok (Total kelebihan: {sum(c - 1 for _, _, c in dup_cand)})")

    # 7. USERS
    print("\n--- 7. USERS (Total:", User.query.count(), ") ---")
    dup_users = db.session.query(
        func.lower(User.email), func.count(User.id)
    ).group_by(func.lower(User.email))\
     .having(func.count(User.id) > 1)\
     .all()
    print(f"Duplikat user email: {len(dup_users)} kelompok")

    print("\n" + "=" * 80)
