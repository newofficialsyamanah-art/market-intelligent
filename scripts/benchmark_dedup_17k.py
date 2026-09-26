import os
import sys
import time
import json
from collections import Counter
from datetime import datetime

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

def run_benchmark():
    print("=== STARTING PHASE 2 BENCHMARK ON ACTUAL 17,152 DATASET ===")
    
    with app.app_context():
        # 1. Load all records from prospects
        t0 = time.time()
        print("1. Loading records from `prospects` table...")
        prospects = Prospect.query.order_by(Prospect.id.asc()).all()
        total_records = len(prospects)
        load_time = time.time() - t0
        print(f"   Loaded {total_records} records in {load_time:.2f}s.")
        
        if total_records == 0:
            print("   No records in prospects table.")
            return
            
        # 2. Initialize IdentityResolutionEngine
        engine = IdentityResolutionEngine()
        
        # Stats tracking
        tier_counts = Counter()
        decision_counts = Counter()
        review_reasons = []
        matching_examples = []
        
        # 3. Process records through Deduplication Engine
        t_start = time.time()
        
        virtual_master_orgs = {}
        prospect_to_master = {}
        next_org_id = 1
        
        for idx, p in enumerate(prospects):
            # Parse region into city and province
            region = p.region or ""
            parts = [part.strip() for part in region.split(",") if part.strip()]
            city = parts[0] if len(parts) > 0 else ""
            province = parts[1] if len(parts) > 1 else ""
            
            # Evaluate against current master index
            match_res = engine.evaluate_candidate(
                name=p.company_name,
                website=p.website,
                email=p.contact_email,
                phone=p.contact_phone,
                city=city,
                province=province
            )
            
            decision_counts[match_res.decision] += 1
            if match_res.tier:
                tier_counts[match_res.tier] += 1
                
            if match_res.decision == "auto_match":
                # Safe merge into matched master
                master = match_res.matched_org
                incoming_data = {
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
                safe_merge_organization(master, incoming_data, match_res)
                prospect_to_master[p.id] = master
                
                # Keep examples (up to 3 per tier)
                if len([ex for ex in matching_examples if ex['tier'] == match_res.tier]) < 3:
                    matching_examples.append({
                        'tier': match_res.tier,
                        'decision': match_res.decision,
                        'confidence': match_res.confidence,
                        'incoming_name': p.company_name,
                        'matched_master_name': master.name,
                        'reason': match_res.reason
                    })
                    
            elif match_res.decision == "review_candidate":
                master = match_res.matched_org
                if len(review_reasons) < 5:
                    review_reasons.append({
                        'incoming_name': p.company_name,
                        'master_name': master.name if master else None,
                        'tier': match_res.tier,
                        'confidence': match_res.confidence,
                        'reason': match_res.reason
                    })
                    
            else: # unmatched -> creates new virtual master entity
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
                }, initial_id=next_org_id)
                next_org_id += 1
                # Index into engine so subsequent records can deduplicate against it!
                engine.index_organization(new_org)
                prospect_to_master[p.id] = new_org
                
        elapsed = time.time() - t_start
        throughput = total_records / elapsed if elapsed > 0 else 0
        
        print(f"\n2. Deduplication Processing Results:")
        print(f"   Total Records Processed : {total_records}")
        print(f"   Total Elapsed Time      : {elapsed:.2f} seconds")
        print(f"   Throughput              : {throughput:.1f} records/sec")
        print(f"\n3. Decision Breakdown:")
        print(f"   - Unique Master Entities (Unmatched) : {decision_counts['unmatched']:,} ({decision_counts['unmatched']/total_records*100:.1f}%)")
        print(f"   - Auto-Matched (Merged)               : {decision_counts['auto_match']:,} ({decision_counts['auto_match']/total_records*100:.1f}%)")
        print(f"   - Review Candidates (Flagged)         : {decision_counts['review_candidate']:,} ({decision_counts['review_candidate']/total_records*100:.1f}%)")
        
        print(f"\n4. Matching Tier Breakdown (Sinyal Kecocokan):")
        for tier, count in tier_counts.most_common():
            print(f"   - {tier:<30} : {count:,} ({count/total_records*100:.2f}%)")
            
        print(f"\n5. Real-World Matching Examples (Contoh Kasus Nyata):")
        for ex in matching_examples:
            print(f"   [{ex['tier']}] ({ex['confidence']}): '{ex['incoming_name']}' MATCHED TO '{ex['matched_master_name']}'")
            print(f"      Reason: {ex['reason']}")
            
        print(f"\n6. Review Candidates Examples (Kandidat Butuh Review Manual):")
        for rev in review_reasons:
            print(f"   [{rev['tier']}] ({rev['confidence']}): '{rev['incoming_name']}' VS '{rev['master_name']}'")
            print(f"      Reason: {rev['reason']}")
            
        # 4. Idempotency Test
        print("\n7. Idempotency Verification Test:")
        print("   Running 500 records a second time through safe_merge...")
        sample_prospects = prospects[:500]
        re_merged_count = 0
        idempotent_skips = 0
        
        for p in sample_prospects:
            master = prospect_to_master.get(p.id)
            if master:
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
                inc = {"source_type": "prospects_legacy", "source_id": p.id, "name": p.company_name}
                modified, msg = safe_merge_organization(master, inc, m_res)
                if not modified:
                    idempotent_skips += 1
                else:
                    re_merged_count += 1
            else:
                idempotent_skips += 1
                    
        print(f"   - Total Idempotent Skips (Zero Changes) : {idempotent_skips}")
        print(f"   - Unintended Modifications              : {re_merged_count}")
        assert re_merged_count == 0, f"Idempotency test failed: {re_merged_count} state changed on second run!"
        print("   [PASS] 100% IDEMPOTENT: Re-running duplicate resolution produces ZERO state changes.")

if __name__ == '__main__':
    run_benchmark()
