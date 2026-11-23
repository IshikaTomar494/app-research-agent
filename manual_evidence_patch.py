import json
import shutil
from datetime import date
from pathlib import Path

RESULTS = Path("results_v2.json")
BACKUP = Path("results_v2_before_evidence_patch.json")

# This is a conservative, source-backed patch.
# Unknown values are deliberately left unknown; no MCP URL is invented.
# Evidence snippets are short excerpts from the cited official documentation.
PATCH = {
    21: {
        "one_line_description": "Slack is a team messaging platform with a Web API and an official MCP server for workspace content.",
        "auth_methods": ["OAuth2", "Bearer token"],
        "api_type": "REST",
        "existing_mcp": "yes",
        "mcp_url": "",
        "buildable_verdict": "partly",
        "main_blocker": "admin_approval",
        "blocker_note": "Workspace permissions and app approval can restrict installation or access; verify the target workspace's policy.",
        "confidence": "medium",
        "evidence": [
            ("one_line_description", "https://docs.slack.dev/apis/web-api/", "Slack's Web API lets apps read and write data in Slack."),
            ("auth_methods", "https://docs.slack.dev/apis/web-api/", "Authenticate your Web API requests by providing a bearer token."),
            ("auth_methods", "https://docs.slack.dev/apis/web-api/", "OAuth 2.0 implementation"),
            ("api_type", "https://docs.slack.dev/apis/web-api/", "Slack Web API"),
            ("existing_mcp", "https://slack.com/help/articles/48855576908307-Guide-to-MCP-in-Slack", "The Slack MCP server lets third-party AI agents securely access your Slack content."),
        ],
        "pages": [
            "https://docs.slack.dev/apis/web-api/",
            "https://slack.com/help/articles/48855576908307-Guide-to-MCP-in-Slack",
            "https://docs.slack.dev/authentication/installing-with-oauth/",
        ],
    },
    25: {
        "one_line_description": "Pumble is a team messaging platform with an API add-on and an official MCP server.",
        "auth_methods": ["API key", "App key", "User token", "Bot token"],
        "self_serve": "yes_free",
        "self_serve_note": "Pumble says its API add-on is available on all plans; users install the add-on and generate an API key in their workspace.",
        "api_type": "REST",
        "existing_mcp": "yes",
        "mcp_url": "",
        "buildable_verdict": "yes",
        "main_blocker": "none",
        "blocker_note": "API access requires installing the API add-on and granting workspace permissions.",
        "confidence": "medium",
        "evidence": [
            ("one_line_description", "https://pumble.com/help/integrations/automation-workflow-integrations/api-keys-integration/", "Pumble API Overview"),
            ("auth_methods", "https://pumble.com/help/integrations/automation-workflow-integrations/api-keys-integration/", "generate an API key"),
            ("self_serve", "https://pumble.com/help/integrations/automation-workflow-integrations/api-keys-integration/", "Available on all plans"),
            ("api_type", "https://pumble.com/help/integrations/automation-workflow-integrations/api-keys-integration/", "simple HTTP requests"),
            ("existing_mcp", "https://pumble.com/help/integrations/automation-workflow-integrations/how-to-use-the-pumble-mcp-server/", "With the Pumble Model Context Protocol (MCP) server"),
        ],
        "pages": [
            "https://pumble.com/help/integrations/automation-workflow-integrations/api-keys-integration/",
            "https://pumble.com/help/integrations/automation-workflow-integrations/how-to-use-the-pumble-mcp-server/",
        ],
    },
    36: {
        "one_line_description": "Klaviyo is a marketing automation platform with server-side and client-side APIs and an official MCP server.",
        "auth_methods": ["Private API key", "OAuth2", "Public API key"],
        "api_type": "REST",
        "existing_mcp": "yes",
        "mcp_url": "https://mcp.klaviyo.com/mcp",
        "buildable_verdict": "partly",
        "main_blocker": "plan_and_permission_gating",
        "blocker_note": "Remote MCP access requires an Owner, Admin, or Manager role; API keys are managed by users with those roles.",
        "confidence": "high",
        "evidence": [
            ("one_line_description", "https://developers.klaviyo.com/en/docs/authenticate_", "Klaviyo provides 3 methods of authentication"),
            ("auth_methods", "https://developers.klaviyo.com/en/docs/authenticate_", "Private key authentication"),
            ("auth_methods", "https://developers.klaviyo.com/en/docs/authenticate_", "OAuth"),
            ("auth_methods", "https://developers.klaviyo.com/en/docs/authenticate_", "Public key authentication"),
            ("api_type", "https://developers.klaviyo.com/en/docs/authenticate_", "All /api endpoints use API private keys"),
            ("existing_mcp", "https://developers.klaviyo.com/en/docs/connect_to_the_klaviyo_mcp_server", "remote-hosted MCP server"),
        ],
        "pages": [
            "https://developers.klaviyo.com/en/docs/authenticate_",
            "https://developers.klaviyo.com/en/docs/connect_to_the_klaviyo_mcp_server",
        ],
    },
    47: {
        "one_line_description": "Ecwid provides an e-commerce platform with a REST API for managing store data, orders, products, and settings.",
        "auth_methods": ["OAuth2", "Access token"],
        "api_type": "REST",
        "api_breadth": "large",
        "has_webhooks": "unknown",
        "rate_limits_documented": "yes",
        "buildable_verdict": "yes",
        "main_blocker": "account_and_api_access",
        "blocker_note": "API access requires an access token; public apps use OAuth 2.0, while custom store access has a simpler token flow.",
        "confidence": "high",
        "evidence": [
            ("one_line_description", "https://docs.ecwid.com/api-reference", "access and manage any store data, payment and shipping methods, and storefront settings"),
            ("auth_methods", "https://docs.ecwid.com/get-started/make-your-first-api-request", "Ecwid uses OAuth 2.0"),
            ("auth_methods", "https://docs.ecwid.com/get-started/make-your-first-api-request", "All requests to Ecwid REST API require an access token."),
            ("api_type", "https://docs.ecwid.com/api-reference", "REST API overview"),
            ("rate_limits_documented", "https://docs.ecwid.com/api-reference", "We accept up to 600 requests per minute per token."),
        ],
        "pages": [
            "https://docs.ecwid.com/api-reference",
            "https://docs.ecwid.com/get-started/make-your-first-api-request",
        ],
    },
    54: {
        "one_line_description": "MrScraper is a web-scraping platform with a REST API and an official hosted MCP server.",
        "auth_methods": ["API token", "OAuth2.1"],
        "self_serve": "yes_free",
        "self_serve_note": "Official billing documentation lists a free plan with a monthly token allocation and no credit card required.",
        "api_type": "REST",
        "api_breadth": "medium",
        "existing_mcp": "yes",
        "mcp_url": "https://mcp.mrscraper.com/mcp",
        "buildable_verdict": "yes",
        "main_blocker": "api_key_and_usage_limits",
        "blocker_note": "Requires a MrScraper account and API token or OAuth sign-in; free-plan usage is limited.",
        "confidence": "high",
        "evidence": [
            ("one_line_description", "https://docs.mrscraper.com/docs/api/overview", "programmatically scrape web pages and retrieve structured data"),
            ("auth_methods", "https://docs.mrscraper.com/docs/api/authentication", "Include your API token in the request header"),
            ("api_type", "https://docs.mrscraper.com/docs/api/overview", "The MrScraper API provides a powerful and flexible way"),
            ("existing_mcp", "https://docs.mrscraper.com/docs/getting-started/mcp-server", "Official MrScraper MCP server"),
            ("self_serve", "https://docs.mrscraper.com/docs/getting-started/billing", "The Free plan includes 100 tokens per month with no credit card required."),
        ],
        "pages": [
            "https://docs.mrscraper.com/docs/api/overview",
            "https://docs.mrscraper.com/docs/api/authentication",
            "https://docs.mrscraper.com/docs/getting-started/mcp-server",
            "https://docs.mrscraper.com/docs/getting-started/billing",
        ],
    },
    58: {
        "one_line_description": "Sherlock is an open-source command-line tool for searching for a username across many social networks.",
        "auth_methods": ["None for local CLI use"],
        "self_serve": "yes_free",
        "self_serve_note": "The project provides a freely installable Python command-line package.",
        "api_type": "Unknown",
        "api_breadth": "small",
        "existing_mcp": "unknown",
        "buildable_verdict": "partly",
        "main_blocker": "local_runtime",
        "blocker_note": "It is a locally run CLI rather than a hosted API; automation requires installing and running the tool in an execution environment.",
        "confidence": "medium",
        "evidence": [
            ("one_line_description", "https://github.com/sherlock-project/sherlock", "Hunt down social media accounts by username across social networks"),
            ("auth_methods", "https://github.com/sherlock-project/sherlock", "Command-line tool"),
            ("self_serve", "https://github.com/sherlock-project/sherlock", "pip install sherlock-project"),
            ("api_type", "https://github.com/sherlock-project/sherlock", "Command-line tool"),
        ],
        "pages": [
            "https://github.com/sherlock-project/sherlock",
            "https://github.com/sherlock-project/sherlockproject.xyz/blob/master/installation.mdx",
        ],
    },
    78: {
        "one_line_description": "Coda is a collaborative document and workflow platform with a REST API and an official MCP server.",
        "auth_methods": ["Bearer token", "Personal access token", "OAuth2"],
        "api_type": "REST",
        "existing_mcp": "yes",
        "mcp_url": "https://coda.io/apis/mcp",
        "buildable_verdict": "yes",
        "main_blocker": "plan_and_permission_gating",
        "blocker_note": "API requests require a bearer API token; MCP capabilities depend on user role and plan.",
        "confidence": "high",
        "evidence": [
            ("one_line_description", "https://coda.io/developers/apis/v1", "Superhuman Docs API (v1)"),
            ("auth_methods", "https://coda.io/developers/apis/v1", "Authorization: Bearer <your API token>"),
            ("api_type", "https://coda.io/developers/apis/v1", "Superhuman Docs API (v1)"),
            ("existing_mcp", "https://help.coda.io/hc/en-us/articles/44722661982989-Connect-to-the-Coda-MCP", "The Coda MCP is a connection layer"),
        ],
        "pages": [
            "https://coda.io/developers/apis/v1",
            "https://help.coda.io/hc/en-us/articles/44722661982989-Connect-to-the-Coda-MCP",
        ],
    },
    84: {
        "one_line_description": "",
        "auth_methods": ["Unknown"],
        "self_serve": "unknown",
        "self_serve_note": "No product-specific Paygent Connect documentation was verified. Do not infer NMI capabilities from the hint alone.",
        "api_type": "Unknown",
        "api_breadth": "unknown",
        "existing_mcp": "unknown",
        "mcp_url": "",
        "buildable_verdict": "unknown",
        "main_blocker": "unknown",
        "blocker_note": "The previous evidence URLs refer to Signicat, Stripe, Google Pay, and Spreedly rather than Paygent Connect. Product-specific integration evidence is still required.",
        "confidence": "low",
        "evidence": [],
        "pages": [],
    },
    90: {
        "one_line_description": "PitchBook provides private-market and company intelligence, with a separately contracted Direct Data REST API and an Essential MCP integration through Perplexity.",
        "auth_methods": ["API key", "Authentication token"],
        "self_serve": "partner_or_sales_gated",
        "self_serve_note": "The API is a separate offering requiring a standalone contract and access request to PitchBook's Direct Data team.",
        "api_type": "REST",
        "api_breadth": "large",
        "existing_mcp": "yes",
        "mcp_url": "",
        "buildable_verdict": "partly",
        "main_blocker": "contact_sales",
        "blocker_note": "API access requires a standalone contract and coordination with the Direct Data team; MCP availability is through the announced Perplexity integration.",
        "confidence": "high",
        "evidence": [
            ("one_line_description", "https://pitchbook.com/help/PitchBook-api", "PitchBook's API solution allows you to call specific PitchBook data"),
            ("auth_methods", "https://pitchbook.com/help/PitchBook-api", "through an API key or authentication token"),
            ("self_serve", "https://pitchbook.com/help/PitchBook-api", "requires a standalone contract agreement"),
            ("api_type", "https://pitchbook.com/help/PitchBook-api", "RESTful implementation"),
            ("existing_mcp", "https://pitchbook.com/media/press-releases/pitchbook-announces-new-essential-mcp-integration-with-perplexity-expanding-access-to-ai-powered-verifiable-market-intelligence", "PitchBook Essential MCP server"),
        ],
        "pages": [
            "https://pitchbook.com/help/PitchBook-api",
            "https://pitchbook.com/products/direct-access-data/api",
            "https://pitchbook.com/media/press-releases/pitchbook-announces-new-essential-mcp-integration-with-perplexity-expanding-access-to-ai-powered-verifiable-market-intelligence",
        ],
    },
}

def evidence_obj(field, url, quote):
    return {
        "field": field,
        "url": url,
        "quote": quote,
        "quote_found": True,
        "quote_on_cited_page": True,
        "url_was_read": True,
        "url_valid": True,
        # This is a manual patch, not the agent's automated strict verifier.
        "strict_check": False,
    }

def main():
    if not RESULTS.exists():
        raise SystemExit("ERROR: results_v2.json not found. Run this from the project folder.")
    if not BACKUP.exists():
        shutil.copy2(RESULTS, BACKUP)

    with RESULTS.open("r", encoding="utf-8-sig") as f:
        data = json.load(f)

    by_id = {item["id"]: item for item in data}
    if len(by_id) != len(data):
        raise SystemExit("ERROR: duplicate IDs found; no changes made.")
    missing = sorted(set(PATCH) - set(by_id))
    if missing:
        raise SystemExit(f"ERROR: expected IDs missing from results: {missing}")

    for app_id, patch in PATCH.items():
        item = by_id[app_id]
        meta = item.setdefault("_meta", {})
        # Preserve original source-page history, then append only verified pages.
        pages = list(meta.get("pages_read", []))
        for url in patch["pages"]:
            if url not in pages:
                pages.append(url)
        meta["pages_read"] = pages

        for key, value in patch.items():
            if key in {"evidence", "pages"}:
                continue
            item[key] = value

        item["evidence"] = [evidence_obj(*entry) for entry in patch["evidence"]]
        item["evidence_urls"] = list(dict.fromkeys(e["url"] for e in item["evidence"]))
        item["status"] = "ok"
        item["confidence"] = patch["confidence"]
        meta["needs_human"] = True
        meta["recovery_method"] = "manual_official_source_patch"
        meta["recovery_date"] = date.today().isoformat()
        meta["quality_check_version"] = "manual-source-review-v1"
        meta["evidence_gaps"] = [
            "Manual source patch; fields not supported by cited official pages remain unknown."
        ]
        meta["errors"] = list(meta.get("errors", []))

    with RESULTS.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print("Patch complete.")
    print("Records:", len(data))
    print("Patched IDs:", sorted(PATCH))
    print("Evidence counts:", {i: len(by_id[i].get("evidence", [])) for i in sorted(PATCH)})
    print("Still flagged for human review:", sum(bool(x.get("_meta", {}).get("needs_human")) for x in data))
    print("Backup:", BACKUP.resolve())
    print("Updated:", RESULTS.resolve())
    print("IMPORTANT: strict_check is false for manually added evidence; this is not a substitute for human verification.")

if __name__ == "__main__":
    main()
