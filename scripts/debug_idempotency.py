import os
import sys
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import create_app, db
from app.models import Prospect, Organization
from app.services.dedup_engine import (
    normalize_company_name,
    extract_domain,
    normalize_phone,
    normalize_location,
    IdentityResolutionEngine,
    safe_merge_organization,
    create_organization_from_source,
    MatchResult
)

app = create_app()

with app.app_context():
    prospects = Prospect.query.order_by(Prospect.id.asc()).limit(500).all()
    engine = IdentityResolutionEngine()
    
    # Run loop 1
    for p in prospects:
        region = p.region or ""
        parts = [part.strip() for part in region.split(",") if part.strip()]
        city = parts[0] if len(parts) > 0 else ""
        province = parts[1] if len(parts) > 1 else ""
        
        m_res = engine.evaluate_candidate(
            name=p.company_name,
            website=p.website,
            email=p.contact_email,
            phone=p.contact_phone,
            city=city,
            province=province
        )
        if m_res.decision == "auto_match":
            master = m_res.matched_org
            inc = {
                "name": p.company_name,
                "source_type": "prospects_legacy",
                "source_id": p.id,
                "industry": p.industry,
                "city": city,
                "province": province,
                "phone": p.contact_phone,
                "email": p.contact_email,
                "website": p.website,
                "opportunity_score": p.score,
                "priority_tier": p.segment
            }
            safe_merge_organization(master, inc, m_res)
        else:
            new_org = create_organization_from_source({
                "name": p.company_name,
                "industry": p.industry,
                "city": city,
                "province": province,
                "phone": p.contact_phone,
                "email": p.contact_email,
                "website": p.website,
                "opportunity_score": p.score or 0,
                "priority_tier": p.segment,
                "source_type": "prospects_legacy",
                "source_id": p.id
            })
            engine.index_organization(new_org)
            
    # Now run loop 2 and inspect any that return True
    print("\n--- LOOP 2 DEBUG ---")
    modified_records = []
    for p in prospects:
        region = p.region or ""
        parts = [part.strip() for part in region.split(",") if part.strip()]
        city = parts[0] if len(parts) > 0 else ""
        province = parts[1] if len(parts) > 1 else ""
        
        m_res = engine.evaluate_candidate(
            name=p.company_name,
            website=p.website,
            email=p.contact_email,
            phone=p.contact_phone,
            city=city,
            province=province
        )
        if m_res.matched_org:
            master = m_res.matched_org
            inc = {
                "name": p.company_name,
                "source_type": "prospects_legacy",
                "source_id": p.id,
                "industry": p.industry,
                "city": city,
                "province": province,
                "phone": p.contact_phone,
                "email": p.contact_email,
                "website": p.website,
                "opportunity_score": p.score,
                "priority_tier": p.segment
            }
            mod, msg = safe_merge_organization(master, inc, m_res)
            if mod:
                print(f"MODIFIED: Prospect #{p.id} ('{p.company_name}') -> Master '{master.name}' (ID {master.id})")
                print(f"  Decision: {m_res.decision}, Tier: {m_res.tier}, Conf: {m_res.confidence}")
                print(f"  Provenance: {master.provenance_json}")
                print(f"  Msg: {msg}")
                modified_records.append(p)
                
    print(f"\nTotal modified in loop 2: {len(modified_records)}")
