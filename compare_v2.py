#!/usr/bin/env python3
"""Compare a new results_v2.json run against the 25-app Step 6 verification sample."""
import json, csv, argparse
from pathlib import Path

FIELDS = ["auth_methods", "self_serve", "api_type", "existing_mcp", "buildable_verdict"]


def canon(field, value):
    import re

    if isinstance(value, list):
        text = ", ".join(str(x) for x in value)
    else:
        text = str(value or "")

    text = text.lower().strip()
    text = text.replace(";", ",")
    text = text.replace("/", ",")
    text = re.sub(r"\s*\([^)]*\)", "", text)
    text = re.sub(r"\s+", " ", text)

    if field == "auth_methods":
        # Normalize common equivalent authentication labels.
        text = text.replace("oauth2", "oauth")
        text = text.replace("access token", "access tokens")
        items = [x.strip() for x in text.split(",") if x.strip()]
        return ", ".join(sorted(set(items)))

    if field == "self_serve":
        # Do not collapse distinct access requirements.
        return text

    return text
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--v2", default="results_v2.json")
    ap.add_argument("--verification", default="step6_verification_completed.csv")
    ap.add_argument("--out", default="step7_v2_comparison.csv")
    args = ap.parse_args()
    records = json.loads(Path(args.v2).read_text(encoding="utf-8"))
    by_id = {int(x["id"]): x for x in records}
    rows = []
    with open(args.verification, newline="", encoding="utf-8") as f:
        for truth in csv.DictReader(f):
            rid = int(truth["id"])
            rec = by_id.get(rid)
            if not rec:
                continue
            for field in FIELDS:
                expected = truth.get(f"{field}__truth", "")
                actual = rec.get(field, "")
                # Unknown/Unclear truth is not scored as a correct or incorrect prediction.
                known = str(truth.get(f"{field}__mark","")).strip().lower() != "unclear"
                rows.append({
                    "id": rid, "app": truth["app"], "field": field,
                    "v1_agent": truth.get(f"{field}__agent",""),
                    "v2_agent": actual,
                    "human_reference": expected,
                    "human_mark_for_v1": truth.get(f"{field}__mark",""),
                    "v2_matches_reference": (
                        canon(field, actual) == canon(field, expected) if known else "not_scored"
                    ),
                    "v2_needs_human": rec.get("_meta",{}).get("needs_human", True),
                    "v2_evidence_gaps": "; ".join(rec.get("_meta",{}).get("evidence_gaps",[])),
                })
    with open(args.out,"w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]) if rows else ["id","app","field"])
        w.writeheader(); w.writerows(rows)
    scored=[r for r in rows if r["v2_matches_reference"] != "not_scored"]
    correct=sum(r["v2_matches_reference"] is True for r in scored)
    print(f"Compared {len(rows)} field rows across {len(set(r['id'] for r in rows))} apps.")
    print(f"Determinate v2 agreement: {correct}/{len(scored)} = {correct/len(scored):.1%}" if scored else "No determinate fields.")
    print(f"Saved {args.out}. Review all mismatches and every v2_needs_human=True row.")

if __name__ == "__main__":
    main()
