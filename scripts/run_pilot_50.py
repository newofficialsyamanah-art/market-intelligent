"""Phase 4.5 Pilot 50 Runner Script.

Menjalankan enrichment pilot test pada 50 master BPS organizations dengan
completeness rendah sesuai arahan Phase 4.5.
"""

import os
import sys
import json
import time
from typing import Dict, Any, List

# Tambahkan project root ke sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app
from app.extensions import db
from app.models import Organization, Prospect, DuplicateCandidate
from app.services.company_enrichment import CompanyEnrichmentService

PILOT_IDS = [
    1165, 1166, 1167, 1168, 1169, 1170, 1171, 1172, 1173, 1174,
    1175, 1176, 1177, 1178, 1179, 1180, 1181, 1182, 1183, 1184,
    1185, 1186, 1187, 1188, 1189, 1190, 1191, 1192, 1193, 1194,
    1195, 1196, 1198, 1199, 1200, 1201, 1202, 1203, 1204, 1205,
    1206, 1207, 1208, 1209, 1210, 1211, 1212, 1213, 1214, 1215
]

FIELDS_TO_TRACK = [
    "website", "domain", "phone", "email",
    "address", "city", "province", "employee_size",
    "instagram", "facebook", "linkedin"
]


def calculate_metrics(orgs: List[Organization]) -> Dict[str, Any]:
    total = len(orgs)
    counts = {f: 0 for f in FIELDS_TO_TRACK}

    for org in orgs:
        if org.website and str(org.website).strip() not in ("", "None", "nan", "-"): counts["website"] += 1
        if org.domain and str(org.domain).strip() not in ("", "None", "nan", "-"): counts["domain"] += 1
        if org.phone and str(org.phone).strip() not in ("", "None", "nan", "-"): counts["phone"] += 1
        if org.email and str(org.email).strip() not in ("", "None", "nan", "-"): counts["email"] += 1
        if org.address and str(org.address).strip() not in ("", "None", "nan", "-"): counts["address"] += 1
        if org.city and str(org.city).strip() not in ("", "None", "nan", "-"): counts["city"] += 1
        if org.province and str(org.province).strip() not in ("", "None", "nan", "-"): counts["province"] += 1
        if org.employee_size and str(org.employee_size).strip() not in ("", "None", "nan", "-"): counts["employee_size"] += 1

        socials = {}
        if org.social_json:
            try:
                socials = json.loads(org.social_json) if isinstance(json.loads(org.social_json), dict) else {}
            except Exception:
                socials = {}
        if socials.get("instagram"): counts["instagram"] += 1
        if socials.get("facebook"): counts["facebook"] += 1
        if socials.get("linkedin"): counts["linkedin"] += 1

    pcts = {f: round(counts[f] / total * 100, 2) if total > 0 else 0.0 for f in FIELDS_TO_TRACK}
    return {"counts": counts, "percentages": pcts, "total": total}


def main():
    app = create_app()
    with app.app_context():
        print("=" * 60)
        print("PHASE 4.5 PILOT 50 RUNNER")
        print("=" * 60)

        # 1. Baseline Invariant Checks
        init_org_count = Organization.query.count()
        init_prospect_count = Prospect.query.count()
        init_dup_count = DuplicateCandidate.query.count()

        print(f"Master Baseline Invariants:")
        print(f"  Organizations       : {init_org_count} (must be 8,474)")
        print(f"  Prospects           : {init_prospect_count} (must be 17,152)")
        print(f"  DuplicateCandidates : {init_dup_count} (must be 408)")

        assert init_org_count == 8474, f"Organization count mismatch: {init_org_count}"
        assert init_prospect_count == 17152, f"Prospect count mismatch: {init_prospect_count}"
        assert init_dup_count == 408, f"DuplicateCandidate count mismatch: {init_dup_count}"

        # 2. Pilot 50 Baseline Metrics
        pilot_orgs = Organization.query.filter(Organization.id.in_(PILOT_IDS)).order_by(Organization.id).all()
        assert len(pilot_orgs) == 50, f"Expected 50 pilot orgs, got {len(pilot_orgs)}"
        baseline_metrics = calculate_metrics(pilot_orgs)
        print("\nBaseline Metrics (50 Orgs BEFORE Pilot):")
        for f in FIELDS_TO_TRACK:
            print(f"  - {f:15}: {baseline_metrics['counts'][f]}/50 ({baseline_metrics['percentages'][f]}%)")

        # 3. Dry-Run Check
        print("\nRunning DRY-RUN Pilot 50...")
        svc = CompanyEnrichmentService(rate_limit_delay=0.1, timeout=6)
        dry_result = svc.run_batch(limit=50, organization_ids=PILOT_IDS, dry_run=True, resume=False)
        print(f"Dry-run completed in {dry_result['elapsed_seconds']}s")
        print(f"  Processed : {dry_result['organizations_processed']}")
        print(f"  AutoAccept: {dry_result['auto_accepted']}")
        print(f"  Review    : {dry_result['review_candidates']}")
        print(f"  NoData    : {dry_result['no_data']}")

        # 4. Live Execution
        print("\nExecuting LIVE Pilot 50...")
        live_start = time.time()
        live_result = svc.run_batch(limit=50, organization_ids=PILOT_IDS, dry_run=False, resume=False)
        live_elapsed = round(time.time() - live_start, 2)
        print(f"Live execution completed in {live_elapsed}s (avg {round(live_elapsed/50, 3)}s/org)")
        print(f"  Processed          : {live_result['organizations_processed']}")
        print(f"  Auto Accepted      : {live_result['auto_accepted']}")
        print(f"  Review Candidates  : {live_result['review_candidates']}")
        print(f"  No Data            : {live_result['no_data']}")
        print(f"  Website Found      : {live_result['website_found']}")
        print(f"  Domain Found       : {live_result['domain_found']}")
        print(f"  Social Found       : {live_result['social_found']}")
        print(f"  Phone Found        : {live_result['phone_found']}")
        print(f"  Email Found        : {live_result['email_found']}")
        print(f"  Address Found      : {live_result['address_found']}")
        print(f"  Employee Size Found: {live_result['employee_size_found']}")
        print(f"  Errors             : {live_result['errors']}")

        # 5. Post-Pilot Completeness
        pilot_orgs_post = Organization.query.filter(Organization.id.in_(PILOT_IDS)).order_by(Organization.id).all()
        post_metrics = calculate_metrics(pilot_orgs_post)
        print("\nPost-Pilot Metrics (50 Orgs AFTER Pilot):")
        deltas = {}
        for f in FIELDS_TO_TRACK:
            delta_count = post_metrics['counts'][f] - baseline_metrics['counts'][f]
            delta_pct = round(post_metrics['percentages'][f] - baseline_metrics['percentages'][f], 2)
            deltas[f] = {"delta_count": delta_count, "delta_pct": delta_pct}
            print(f"  - {f:15}: {baseline_metrics['counts'][f]} -> {post_metrics['counts'][f]} (+{delta_count}, +{delta_pct}%)")

        # 6. Idempotency Check (Rerun on same 50)
        print("\nRunning Idempotency Verification (Rerun on exact same 50 orgs)...")
        idemp_result = svc.run_batch(limit=50, organization_ids=PILOT_IDS, dry_run=False, resume=False)
        print(f"Idempotency rerun: AutoAccepted={idemp_result['auto_accepted']}, WebsiteFound={idemp_result['website_found']}, PhoneFound={idemp_result['phone_found']}")

        pilot_orgs_idemp = Organization.query.filter(Organization.id.in_(PILOT_IDS)).order_by(Organization.id).all()
        idemp_metrics = calculate_metrics(pilot_orgs_idemp)
        assert idemp_metrics == post_metrics, "Idempotency FAILED: Metrics changed on rerun!"
        print(">> Idempotency Test PASSED: 0 delta on rerun.")

        # 7. Final Database Invariant Check
        final_org_count = Organization.query.count()
        final_prospect_count = Prospect.query.count()
        final_dup_count = DuplicateCandidate.query.count()

        print("\nFinal Master Invariant Verification:")
        print(f"  Organizations       : {final_org_count} (Delta: {final_org_count - init_org_count})")
        print(f"  Prospects           : {final_prospect_count} (Delta: {final_prospect_count - init_prospect_count})")
        print(f"  DuplicateCandidates : {final_dup_count} (Delta: +{final_dup_count - init_dup_count})")

        assert final_org_count == 8474, f"Organizations mutated! Expected 8474, got {final_org_count}"
        assert final_prospect_count == 17152, f"Prospects mutated! Expected 17152, got {final_prospect_count}"
        assert final_dup_count == init_dup_count + live_result['review_candidates'], (
            f"Duplicate candidates mismatch! Expected {init_dup_count + live_result['review_candidates']}, got {final_dup_count}"
        )
        print(">> All Invariants PASSED.")

        # 8. Save Detailed Output
        output_data = {
            "pilot_ids": PILOT_IDS,
            "baseline_metrics": baseline_metrics,
            "live_result": live_result,
            "post_metrics": post_metrics,
            "deltas": deltas,
            "invariants": {
                "organizations": final_org_count,
                "prospects": final_prospect_count,
                "duplicate_candidates": final_dup_count,
                "new_review_candidates": final_dup_count - init_dup_count
            }
        }
        os.makedirs("instance", exist_ok=True)
        with open("instance/pilot_50_results.json", "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        print("\nSaved pilot results to instance/pilot_50_results.json")


if __name__ == "__main__":
    main()
