#!/usr/bin/env python3
"""
Build the hand-verification sheet and score it.

  python make_sheet.py                           # 25-app sample from results_v1.json -> verification/sheet_v1.csv
  python make_sheet.py --score verification/sheet_v1.csv      # accuracy after you fill the marks
  python make_sheet.py --fresh 12 --src results_v2.json       # 12 NEW apps (not in the 25) -> verification/sheet_fresh.csv

How to fill the sheet: for each field open the real docs, type what you found in "__truth",
and put Correct / Wrong / Unclear in "__mark". If Wrong, say why in notes_why_wrong
(old docs, mixed up two products, guessed, docs unreadable, ...).
"""
import argparse
import csv
import json
import random
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).parent
OUT_DIR = ROOT / "verification"
FIELDS = ["auth_methods", "self_serve", "api_type", "existing_mcp", "buildable_verdict"]
SEED = 7   # fixed, so the sample is reproducible and you can say it was not cherry-picked

FAMOUS = {
    "Salesforce", "HubSpot", "Zendesk", "Intercom", "Slack", "Twilio", "Discord", "Telegram",
    "Google Ads", "Meta Ads", "Mailchimp", "SendGrid", "Shopify", "WooCommerce", "GitHub",
    "Vercel", "Cloudflare", "Datadog", "Supabase", "Snowflake", "Notion", "Airtable", "Jira",
    "Asana", "Linear", "Stripe", "Plaid", "QuickBooks", "Xero", "Zoho CRM", "Pipedrive",
}


def pick_sample(recs, n=25):
    rnd = random.Random(SEED)
    by_cat = defaultdict(list)
    for r in recs:
        by_cat[r["category"]].append(r)
    chosen = []
    for cat in sorted(by_cat):
        rs = by_cat[cat]
        fam = [r for r in rs if r["app"] in FAMOUS]
        obs = [r for r in rs if r["app"] not in FAMOUS]
        if fam:
            chosen.append(rnd.choice(fam))
        if obs:
            chosen.append(rnd.choice(obs))
    ids = {r["id"] for r in chosen}
    rest = [r for r in recs if r["id"] not in ids]
    while len(chosen) < n and rest:
        chosen.append(rest.pop(rnd.randrange(len(rest))))
    return chosen[:n]


def row_for(r):
    row = {
        "id": r["id"], "app": r["app"], "category": r["category"], "hint_url": r.get("hint_url", ""),
        "agent_flagged_needs_human": r.get("_meta", {}).get("needs_human", ""),
    }
    for f in FIELDS:
        val = r.get(f, "")
        if isinstance(val, list):
            val = ", ".join(val)
        urls = " | ".join(e.get("url", "") for e in r.get("evidence", []) if e.get("field") == f)
        row[f"{f}__agent"] = val
        row[f"{f}__evidence"] = urls
        row[f"{f}__truth"] = ""
        row[f"{f}__mark"] = ""   # Correct / Wrong / Unclear
    row["notes_why_wrong"] = ""
    return row


def write_sheet(recs, path):
    OUT_DIR.mkdir(exist_ok=True)
    rows = [row_for(r) for r in recs]
    with open(path, "w", newline="", encoding="utf-8-sig") as f:   # utf-8-sig so Excel opens it cleanly
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote {len(rows)} apps -> {path}")


def score(path):
    per_field = {f: {"Correct": 0, "Wrong": 0, "Unclear": 0, "blank": 0} for f in FIELDS}
    wrong = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            for fld in FIELDS:
                m = (row.get(f"{fld}__mark") or "").strip().capitalize()
                per_field[fld][m if m in ("Correct", "Wrong", "Unclear") else "blank"] += 1
                if m == "Wrong":
                    wrong.append((row["app"], fld, row.get(f"{fld}__agent", ""), row.get(f"{fld}__truth", "")))
    tot = {"Correct": 0, "Wrong": 0, "Unclear": 0, "blank": 0}
    print(f"{'field':<20}{'correct':>8}{'wrong':>7}{'unclear':>9}{'accuracy':>10}")
    for fld, c in per_field.items():
        n = c["Correct"] + c["Wrong"] + c["Unclear"]
        acc = f"{100 * c['Correct'] / n:.0f}%" if n else "-"
        print(f"{fld:<20}{c['Correct']:>8}{c['Wrong']:>7}{c['Unclear']:>9}{acc:>10}")
        for k in tot:
            tot[k] += c[k]
    n = tot["Correct"] + tot["Wrong"] + tot["Unclear"]
    if n:
        print(f"\nOVERALL: {tot['Correct']}/{n} = {100 * tot['Correct'] / n:.1f}%  (Unclear counted as not correct)")
        m = tot["Correct"] + tot["Wrong"]
        if m:
            print(f"Excluding Unclear: {tot['Correct']}/{m} = {100 * tot['Correct'] / m:.1f}%")
    if tot["blank"]:
        print(f"WARNING: {tot['blank']} cells still unmarked")
    print("\nMistakes:")
    for app, fld, agent, truth in wrong:
        print(f"  {app} / {fld}: agent said '{agent}', truth '{truth}'")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="results_v1.json")
    ap.add_argument("--score", help="score a filled sheet")
    ap.add_argument("--fresh", type=int, help="pick N new apps that are not in the saved 25-app sample")
    args = ap.parse_args()

    if args.score:
        score(args.score)
        return

    recs = json.loads((ROOT / args.src).read_text(encoding="utf-8"))
    ids_file = OUT_DIR / "sample_ids.json"

    if args.fresh:
        if not ids_file.exists():
            raise SystemExit("Run without --fresh first, so the 25-app sample exists.")
        used = set(json.loads(ids_file.read_text()))
        pool = [r for r in recs if r["id"] not in used]
        pick = random.Random(SEED + 1).sample(pool, min(args.fresh, len(pool)))
        write_sheet(pick, OUT_DIR / "sheet_fresh.csv")
        return

    sample = pick_sample(recs)
    OUT_DIR.mkdir(exist_ok=True)
    ids_file.write_text(json.dumps(sorted(r["id"] for r in sample)))
    write_sheet(sample, OUT_DIR / "sheet_v1.csv")
    print("Sample:", ", ".join(r["app"] for r in sample))


if __name__ == "__main__":
    main()
