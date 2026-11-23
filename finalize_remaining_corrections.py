
import json
import shutil

FILE = "results_v2.json"
BACKUP = "results_v2_before_last_five.json"

shutil.copy2(FILE, BACKUP)

with open(FILE, "r", encoding="utf-8-sig") as f:
    data = json.load(f)

corrections = {
    68: {
        "auth_methods": ["OAuth2", "API key"]
    },
    41: {
        "auth_methods": ["OAuth2", "Access token"]
    },
    19: {
        "auth_methods": [
            "Basic",
            "API key",
            "OAuth2 (public apps)"
        ]
    },
    38: {
        "self_serve": "admin_approval"
    },
    97: {
        "self_serve": "unknown"
    }
}

for record in data:
    app_id = int(record["id"])
    if app_id in corrections:
        record.update(corrections[app_id])

        if app_id == 97:
            meta = record.setdefault("_meta", {})
            meta["needs_human"] = True
            meta.setdefault("evidence_gaps", []).append(
                "Pay-as-you-go with minimum balance does not fit "
                "the available self_serve categories; human classification required."
            )

with open(FILE, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print("Final corrections applied.")
print("Records:", len(data))
print("Corrected IDs:", sorted(corrections))
print("Backup:", BACKUP)
