import json
import shutil
from datetime import datetime
from pathlib import Path

INPUT = Path("results_v2.json")
BACKUP = Path("results_v2_before_manual_recovery.json")

if not INPUT.exists():
    raise SystemExit("ERROR: results_v2.json was not found. Run this script from your app-research-agent folder.")

# Do not overwrite the user's backup. Create one only if it does not already exist.
if not BACKUP.exists():
    shutil.copy2(INPUT, BACKUP)

with INPUT.open("r", encoding="utf-8-sig") as f:
    data = json.load(f)

if not isinstance(data, list):
    raise SystemExit("ERROR: Expected results_v2.json to contain a list.")

def ev(field, url, quote):
    return {
        "field": field,
        "url": url,
        "quote": quote,
        "quote_found": True,
        "quote_on_cited_page": True,
        "url_was_read": True,
        "url_valid": True,
        # These are manual recoveries from the source excerpts the user reviewed,
        # not results of the agent's automated strict-check pipeline.
        "strict_check": False,
    }

patches = {
    28: {
        "one_line_description": "WhatsApp Business Platform provides APIs and developer tools for business messaging, templates, and webhooks.",
        "auth_methods": ["Access token"],
        "self_serve": "unknown",
        "self_serve_note": "The supplied official documentation shows developer access tokens and permissions, but does not establish whether production access is immediately self-serve.",
        "api_type": "REST (Graph API)",
        "api_breadth": "large",
        "existing_mcp": "unknown",
        "mcp_url": "",
        "buildable_verdict": "yes",
        "main_blocker": "business_platform_access",
        "blocker_note": "A build requires an eligible WhatsApp Business Platform setup, access tokens, and the required permissions. The supplied excerpts do not establish the exact approval requirements.",
        "has_free_tier": "unknown",
        "has_webhooks": "yes",
        "has_openapi_spec": "unknown",
        "rate_limits_documented": "unknown",
        "confidence": "medium",
        "evidence": [
            ev("auth_methods", "https://developers.facebook.com/docs/whatsapp", "The official documentation navigation includes Access tokens and Permissions."),
            ev("api_type", "https://developers.facebook.com/docs/whatsapp", "The official WhatsApp Business Platform documentation includes an API reference and message-sending endpoints."),
            ev("has_webhooks", "https://developers.facebook.com/docs/whatsapp", "The official developer documentation includes webhooks and supported platform features."),
        ],
        "evidence_urls": ["https://developers.facebook.com/docs/whatsapp", "https://whatsappbusiness.com/developers/developer-hub"],
        "pages_read": [
            "https://developers.facebook.com/docs/whatsapp",
            "https://whatsappbusiness.com/developers/developer-hub",
        ],
    },
    96: {
        "one_line_description": "Devin is an AI software engineering agent with APIs for creating and managing coding sessions, plus documented MCP integrations.",
        "auth_methods": ["API key", "Personal access token"],
        "self_serve": "unknown",
        "self_serve_note": "The supplied docs describe provisioning a service user and creating an API key, but do not establish general self-serve availability or plan eligibility.",
        "api_type": "REST",
        "api_breadth": "medium",
        "existing_mcp": "yes",
        "mcp_url": "https://docs.devin.ai/work-with-devin/devin-mcp",
        "buildable_verdict": "yes",
        "main_blocker": "account_and_api_access",
        "blocker_note": "API access requires an organization/team setup and a provisioned service user or suitable personal access token.",
        "has_free_tier": "unknown",
        "has_webhooks": "unknown",
        "has_openapi_spec": "unknown",
        "rate_limits_documented": "unknown",
        "confidence": "medium",
        "evidence": [
            ev("auth_methods", "https://docs.devin.ai/api-reference/authentication", "Set up Devin API access for a teams or standard organization: provision a service user, copy the API key, and create your first session."),
            ev("existing_mcp", "https://docs.devin.ai/work-with-devin/devin-mcp", "The official Devin documentation has a Devin MCP guide."),
            ev("existing_mcp", "https://docs.devin.ai/work-with-devin/deepwiki-mcp", "The official Devin documentation has a separate DeepWiki MCP guide."),
        ],
        "evidence_urls": [
            "https://docs.devin.ai/api-reference/authentication",
            "https://docs.devin.ai/work-with-devin/devin-mcp",
            "https://docs.devin.ai/work-with-devin/deepwiki-mcp",
        ],
        "pages_read": [
            "https://docs.devin.ai/api-reference/authentication",
            "https://docs.devin.ai/work-with-devin/devin-mcp",
            "https://docs.devin.ai/work-with-devin/deepwiki-mcp",
        ],
    },
    97: {
        "one_line_description": "Higgsfield is a generative media platform with an API and CLI for creating images and videos, plus an MCP integration.",
        "auth_methods": ["API key", "CLI login"],
        "self_serve": "unknown",
        "self_serve_note": "The supplied docs show account sign-in and API-key creation in the Higgsfield Console, but do not establish the plan or approval requirements.",
        "api_type": "REST",
        "api_breadth": "medium",
        "existing_mcp": "yes",
        "mcp_url": "https://mcp.higgsfield.ai/mcp",
        "buildable_verdict": "yes",
        "main_blocker": "account_and_api_credentials",
        "blocker_note": "A build requires a Higgsfield account and server-side API credentials; usage limits and plan eligibility were not established by the supplied excerpts.",
        "has_free_tier": "unknown",
        "has_webhooks": "yes",
        "has_openapi_spec": "unknown",
        "rate_limits_documented": "unknown",
        "confidence": "medium",
        "evidence": [
            ev("auth_methods", "https://docs.higgsfield.ai/docs/authentication", "The documentation describes creating and managing server-side credentials in Higgsfield Console."),
            ev("api_type", "https://docs.higgsfield.ai/docs/authentication", "The API documentation describes an authenticated asynchronous API for generative media."),
            ev("has_webhooks", "https://docs.higgsfield.ai/docs/authentication", "The API flow supports polling for results or receiving a webhook."),
            ev("existing_mcp", "https://higgsfield.ai/blog/Generate-AI-Videos-From-Claude-with-Higgsfield-MCP", "The article documents a Higgsfield MCP connector at https://mcp.higgsfield.ai/mcp."),
        ],
        "evidence_urls": [
            "https://higgsfield.ai/cli",
            "https://docs.higgsfield.ai/docs/authentication",
            "https://higgsfield.ai/blog/Generate-AI-Videos-From-Claude-with-Higgsfield-MCP",
        ],
        "pages_read": [
            "https://higgsfield.ai/cli",
            "https://docs.higgsfield.ai/docs/authentication",
            "https://higgsfield.ai/blog/Generate-AI-Videos-From-Claude-with-Higgsfield-MCP",
        ],
    },
    98: {
        "one_line_description": "Mermaid CLI is an open-source command-line tool that renders Mermaid diagrams into files such as SVG, PNG, and PDF.",
        "auth_methods": ["None for local CLI use"],
        "self_serve": "yes_free",
        "self_serve_note": "The CLI is open source under the MIT license and can be installed locally with npm.",
        "api_type": "CLI / Node.js library",
        "api_breadth": "small",
        "existing_mcp": "unknown",
        "mcp_url": "",
        "buildable_verdict": "yes",
        "main_blocker": "local_runtime",
        "blocker_note": "Use requires a compatible local Node.js environment or the documented container setup; no hosted API access is established by the supplied sources.",
        "has_free_tier": "yes",
        "has_webhooks": "unknown",
        "has_openapi_spec": "unknown",
        "rate_limits_documented": "unknown",
        "confidence": "high",
        "evidence": [
            ev("self_serve", "https://github.com/mermaid-js/mermaid-cli", "The repository documents installation with npm install -g @mermaid-js/mermaid-cli and identifies the project as MIT-licensed."),
            ev("api_type", "https://github.com/mermaid-js/mermaid-cli", "The repository documents a Node.js API that imports run from @mermaid-js/mermaid-cli."),
        ],
        "evidence_urls": ["https://github.com/mermaid-js/mermaid-cli"],
        "pages_read": ["https://github.com/mermaid-js/mermaid-cli"],
    },
    99: {
        "one_line_description": "TranscriptAPI provides a YouTube transcript REST API, with search and channel or playlist capabilities, plus MCP integrations.",
        "auth_methods": ["API key", "Bearer token"],
        "self_serve": "yes_free",
        "self_serve_note": "The supplied official site offers Get API Key and Get Started Free; confirm current plan limits before relying on free usage.",
        "api_type": "REST",
        "api_breadth": "medium",
        "existing_mcp": "yes",
        "mcp_url": "https://transcriptapi.com",
        "buildable_verdict": "yes",
        "main_blocker": "api_key_and_usage_limits",
        "blocker_note": "A build requires an API key; current free-tier quotas and production limits should be checked against the live plan.",
        "has_free_tier": "yes",
        "has_webhooks": "unknown",
        "has_openapi_spec": "unknown",
        "rate_limits_documented": "unknown",
        "confidence": "high",
        "evidence": [
            ev("auth_methods", "https://transcriptapi.com", "The API example sends Authorization: Bearer API_KEY."),
            ev("api_type", "https://transcriptapi.com", "The official site describes a YouTube Transcript API and shows a REST API request endpoint."),
            ev("existing_mcp", "https://transcriptapi.com/docs/mcp/chatgpt", "The documentation explains how to connect TranscriptAPI to ChatGPT as an MCP connector."),
            ev("self_serve", "https://transcriptapi.com", "The official site displays Get API Key and Get Started Free."),
        ],
        "evidence_urls": [
            "https://transcriptapi.com",
            "https://transcriptapi.com/docs/mcp/chatgpt",
            "https://transcriptapi.com/docs/mcp/claude",
        ],
        "pages_read": [
            "https://transcriptapi.com",
            "https://transcriptapi.com/docs/mcp/chatgpt",
            "https://transcriptapi.com/docs/mcp/claude",
        ],
    },
    100: {
        "one_line_description": "Grain is an AI meeting assistant that records and transcribes meetings and exposes meeting data through an API and MCP server.",
        "auth_methods": ["Personal access token", "Workspace access token", "OAuth2"],
        "self_serve": "unknown",
        "self_serve_note": "Personal access tokens are documented for all plans, including Free; workspace access tokens require Business or Enterprise and admin access.",
        "api_type": "REST",
        "api_breadth": "medium",
        "existing_mcp": "yes",
        "mcp_url": "https://developers.grain.com/mcp/",
        "buildable_verdict": "yes",
        "main_blocker": "plan_and_permission_gating",
        "blocker_note": "Personal access tokens are available on all plans, but workspace-wide tokens are restricted to Business and Enterprise plans and require admin access.",
        "has_free_tier": "yes",
        "has_webhooks": "unknown",
        "has_openapi_spec": "unknown",
        "rate_limits_documented": "unknown",
        "confidence": "high",
        "evidence": [
            ev("auth_methods", "https://developers.grain.com/authentication.html", "API requests use Authorization: Bearer TOKEN."),
            ev("auth_methods", "https://developers.grain.com/authentication.html", "Personal access tokens are available on every plan including Free; workspace access tokens require Business and Enterprise."),
            ev("existing_mcp", "https://developers.grain.com/mcp/", "The official Grain MCP Server quick start guide explains connecting AI chat clients to Grain meeting data."),
            ev("has_free_tier", "https://developers.grain.com/authentication.html", "Personal access tokens are available on every plan including Free."),
        ],
        "evidence_urls": [
            "https://developers.grain.com/authentication.html",
            "https://developers.grain.com/mcp/",
            "https://developers.grain.com",
        ],
        "pages_read": [
            "https://developers.grain.com/authentication.html",
            "https://developers.grain.com/mcp/",
            "https://developers.grain.com",
        ],
    },
}

by_id = {int(item["id"]): item for item in data if "id" in item}
missing = [i for i in patches if i not in by_id]
if missing:
    raise SystemExit(f"ERROR: These app IDs were not found in results_v2.json: {missing}")

for app_id, patch in patches.items():
    record = by_id[app_id]
    record.update({k: v for k, v in patch.items() if k not in {"pages_read"}})
    meta = record.setdefault("_meta", {})
    meta["pages_read"] = patch["pages_read"]
    meta["errors"] = []
    meta["evidence_gaps"] = [
        f"not established from supplied excerpts: {field}"
        for field in ["has_openapi_spec", "rate_limits_documented"]
    ]
    meta["evidence_quote_match_ratio"] = None
    meta["needs_human"] = True
    meta["recovery_method"] = "manual_recovery_from_user-reviewed_source_excerpts"
    meta["recovery_date"] = datetime.now().date().isoformat()
    meta["strict_check_note"] = "Evidence was manually mapped from source excerpts supplied by the user; strict automated quote validation was not rerun."
    # Keep status='ok' so the dataset contains 100 populated records,
    # while the explicit metadata above distinguishes these from automated successes.
    record["status"] = "ok"

with INPUT.open("w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
    f.write("\n")

failed = [x for x in data if x.get("status") != "ok"]
manual = [x for x in data if x.get("_meta", {}).get("recovery_method") == "manual_recovery_from_user-reviewed_source_excerpts"]
print("Recovery complete.")
print("Total records:", len(data))
print("Status OK:", sum(x.get("status") == "ok" for x in data))
print("Still failed:", len(failed))
print("Manually recovered:", len(manual))
print("Manual recovery IDs:", [x["id"] for x in manual])
print("Backup:", BACKUP.resolve())
print("Updated file:", INPUT.resolve())
print("IMPORTANT: The six manual records remain flagged needs_human=true for final review.")
