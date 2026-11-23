import json
from collections import Counter, defaultdict

with open("results_v2.json", encoding="utf-8-sig") as f:
    apps = json.load(f)

print("=" * 55)
print("APP RESEARCH - PATTERN ANALYSIS")
print("=" * 55)

print("\n1. TOTAL APPS")
print(len(apps))

print("\n2. AUTHENTICATION METHODS")
auth = Counter()
for app in apps:
    methods = app.get("auth_methods", [])
    if isinstance(methods, str):
        methods = [methods]
    for method in methods:
        auth[str(method).strip()] += 1
for k, v in auth.most_common():
    print(f"{k}: {v}")

print("\n3. SELF-SERVE ACCESS")
selfserve = Counter(str(a.get("self_serve", "unknown")) for a in apps)
for k, v in selfserve.most_common():
    print(f"{k}: {v} ({v/len(apps)*100:.1f}%)")

print("\n4. API TYPES")
api = Counter(str(a.get("api_type", "unknown")) for a in apps)
for k, v in api.most_common():
    print(f"{k}: {v}")

print("\n5. BUILDABILITY")
build = Counter(str(a.get("buildable_verdict", "unknown")) for a in apps)
for k, v in build.most_common():
    print(f"{k}: {v} ({v/len(apps)*100:.1f}%)")

print("\n6. EXISTING MCP")
mcp = Counter(str(a.get("existing_mcp", "unknown")) for a in apps)
for k, v in mcp.most_common():
    print(f"{k}: {v}")

print("\n7. CATEGORIES")
cats = Counter(str(a.get("category", "unknown")) for a in apps)
for k, v in cats.most_common():
    print(f"{k}: {v}")

print("\n8. MAIN BLOCKERS")
blockers = Counter(str(a.get("main_blocker", "unknown")) for a in apps)
for k, v in blockers.most_common(20):
    print(f"{k}: {v}")

print("\n9. EASY WIN CANDIDATES")
for a in apps:
    access = str(a.get("self_serve", "")).lower()
    api_type = str(a.get("api_type", "")).lower()
    verdict = str(a.get("buildable_verdict", "")).lower()
    if access in ("yes_free", "yes_trial") and ("rest" in api_type or "graphql" in api_type) and verdict in ("yes", "partly"):
        print("-", a.get("app"), "|", access, "|", api_type, "|", verdict)

print("\n10. NEEDS HUMAN REVIEW")
review = [a for a in apps if a.get("_meta", {}).get("needs_human")]
print("Records flagged:", len(review))
for a in review:
    print("-", a.get("app"), "(ID:", a.get("id"), ")")

print("\n11. RECORDS WITHOUT EVIDENCE")
for a in apps:
    if not a.get("evidence"):
        print("-", a.get("app"), "(ID:", a.get("id"), ")")

print("\nANALYSIS COMPLETE")
