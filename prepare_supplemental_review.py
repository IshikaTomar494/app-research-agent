import csv
import json
import shutil
from pathlib import Path
from collections import Counter

results_path = Path("results_v2.json")
backup_path = Path("results_v2_before_metadata_correction.json")
queue_path = Path("step7_supplemental_review_queue.csv")

if not results_path.exists():
    raise SystemExit("ERROR: Run this script from the app-research-agent folder; results_v2.json was not found.")

if not backup_path.exists():
    shutil.copy2(results_path, backup_path)

with results_path.open("r", encoding="utf-8-sig") as f:
    records = json.load(f)

# Correct only the 39 evidence entries created by manual_evidence_patch.py.
# The script had populated these flags without a page-by-page strict verification.
corrected = 0
for record in records:
    if record.get("_meta", {}).get("recovery_method") == "manual_official_source_patch":
        for ev in record.get("evidence", []):
            ev["url_was_read"] = False
            ev["quote_found"] = False
            ev["quote_on_cited_page"] = False
            ev["strict_check"] = False
            corrected += 1

with results_path.open("w", encoding="utf-8") as f:
    json.dump(records, f, ensure_ascii=False, indent=2)
    f.write("\n")

# One row per record needing human review. Original queue is not modified.
field_names = [
    "id", "app", "category", "review_status", "recovery_method",
    "one_line_description", "auth_methods", "self_serve", "api_type",
    "api_breadth", "existing_mcp", "mcp_url", "buildable_verdict",
    "main_blocker", "evidence_count", "evidence_fields",
    "strict_pass_count", "quote_not_found_count", "evidence_urls",
    "review_note"
]

rows = []
for r in records:
    meta = r.get("_meta", {})
    if not meta.get("needs_human", False):
        continue

    evidence = r.get("evidence", []) or []
    strict_pass = sum(1 for e in evidence if e.get("strict_check") is True)
    quote_missing = sum(1 for e in evidence if e.get("quote_found") is False)
    fields = sorted({str(e.get("field", "")) for e in evidence if e.get("field")})
    urls = list(dict.fromkeys(
        e.get("url", "") for e in evidence if e.get("url")
    ))

    notes = []
    if not evidence:
        notes.append("No product-specific evidence attached; verify from official sources.")
    if r.get("id") == 84:
        notes.append("Paygent Connect: previous evidence was unrelated; keep claims unknown until product-specific evidence is found.")
    if meta.get("recovery_method") in (
        "manual_official_source_patch",
        "manual_recovery_from_user-reviewed_source_excerpts"
    ):
        notes.append("Manual recovery: inspect the source pages and confirm each quoted claim.")
    if any(e.get("strict_check") is not True for e in evidence):
        notes.append("At least some evidence has not passed the strict automated check.")
    if quote_missing:
        notes.append("Some evidence entries do not have a confirmed matching quote.")

    rows.append({
        "id": r.get("id", ""),
        "app": r.get("app", ""),
        "category": r.get("category", ""),
        "review_status": "pending_human_review",
        "recovery_method": meta.get("recovery_method", "original_agent"),
        "one_line_description": r.get("one_line_description", ""),
        "auth_methods": json.dumps(r.get("auth_methods", []), ensure_ascii=False),
        "self_serve": r.get("self_serve", ""),
        "api_type": r.get("api_type", ""),
        "api_breadth": r.get("api_breadth", ""),
        "existing_mcp": r.get("existing_mcp", ""),
        "mcp_url": r.get("mcp_url", ""),
        "buildable_verdict": r.get("buildable_verdict", ""),
        "main_blocker": r.get("main_blocker", ""),
        "evidence_count": len(evidence),
        "evidence_fields": "; ".join(fields),
        "strict_pass_count": strict_pass,
        "quote_not_found_count": quote_missing,
        "evidence_urls": " ; ".join(urls),
        "review_note": " ".join(notes) if notes else "Review field claims against official documentation."
    })

rows.sort(key=lambda x: int(x["id"]) if str(x["id"]).isdigit() else 999999)

with queue_path.open("w", newline="", encoding="utf-8-sig") as f:
    writer = csv.DictWriter(f, fieldnames=field_names)
    writer.writeheader()
    writer.writerows(rows)

print("Metadata correction and supplemental queue complete.")
print("Records:", len(records))
print("Manual patch evidence entries corrected:", corrected)
print("Records in supplemental human-review queue:", len(rows))
print("Evidence with strict_check=True after correction:",
      sum(1 for r in records for e in (r.get("evidence") or []) if e.get("strict_check") is True))
print("Original Step 7 queue was NOT changed.")
print("Backup:", backup_path.resolve())
print("Updated results:", results_path.resolve())
print("New queue:", queue_path.resolve())
print("Review statuses:", dict(Counter(r["review_status"] for r in rows)))
