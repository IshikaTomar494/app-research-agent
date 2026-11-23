#!/usr/bin/env python3
"""
App research agent (Composio Search + Gemini).

For each app in apps.csv it:
  1. SEARCH  - runs 3 searches through Composio's search toolkit
  2. READ    - fetches the best 5 pages (official docs first)
  3. EXTRACT - asks Gemini for a strict JSON answer with a URL + quote per claim
  4. CHECK   - verifies that every quote really appears in the fetched page
  5. SAVE    - writes results JSON + raw pages (so you can show your work)

Usage:
  python agent.py --app "Stripe"                 # one app (test first!)
  python agent.py --all --out results_v1.json    # all 100 apps
  python agent.py --all --out results_v1.json --resume   # continue after a crash
"""
import argparse
import csv
import json
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).parent
RAW_DIR = ROOT / "raw"
LOG_FILE = ROOT / "agent_log.jsonl"

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
COMPOSIO_USER_ID = os.getenv("COMPOSIO_USER_ID", "default")
MAX_PAGES = 5            # pages read per app
MAX_CHARS_PER_PAGE = 15000
RESULTS_PER_SEARCH = 6

# Composio slugs change between versions, so we try several and remember the one that works.
SEARCH_SLUGS = [
    "COMPOSIO_SEARCH_WEB",
    "COMPOSIO_SEARCH_TAVILY_SEARCH",
    "COMPOSIO_SEARCH_DUCK_DUCK_GO",
    "COMPOSIO_SEARCH_DUCK_DUCK_GO_SEARCH",
    "COMPOSIO_SEARCH_SEARCH",
]
FETCH_SLUG = "COMPOSIO_SEARCH_FETCH_URL_CONTENT"

SKIP_DOMAINS = (
    "youtube.com", "reddit.com", "medium.com", "quora.com", "facebook.com",
    "twitter.com", "x.com", "linkedin.com/pulse", "pinterest.com", "tiktok.com",
)

AUTH_VALUES = ["OAuth2", "API key", "Basic", "Bearer token", "JWT", "Other", "None", "Unknown"]
SELF_SERVE_VALUES = [
    "yes_free", "yes_trial", "paid_plan_needed", "admin_approval",
    "partner_or_sales_gated", "not_applicable", "unknown",
]
API_TYPE_VALUES = ["REST", "GraphQL", "REST+GraphQL", "SDK/CLI only", "None", "Unknown"]
BREADTH_VALUES = ["small", "medium", "large", "unknown"]
VERDICT_VALUES = ["yes", "partly", "no", "unknown"]
BLOCKER_VALUES = [
    "none", "partner_approval", "paid_plan", "contact_sales", "admin_approval",
    "no_public_api", "cli_only", "poor_docs", "unclear_auth", "needs_review_process",
    "other", "unknown",
]

_log_lock = threading.Lock()
_save_lock = threading.Lock()


def log(event: str, **kw):
    """Append one line to agent_log.jsonl. This is your 'where the agent got stuck' record."""
    rec = {"t": time.strftime("%Y-%m-%d %H:%M:%S"), "event": event, **kw}
    with _log_lock:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


# ----------------------------------------------------------------------------
# helpers for reading messy tool responses
# ----------------------------------------------------------------------------
def walk(obj):
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from walk(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from walk(v)


def extract_results(resp):
    """Pull {url,title,snippet} items out of any search response shape."""
    out, seen = [], set()
    for d in walk(resp):
        u = d.get("url") or d.get("link")
        if isinstance(u, str) and u.startswith("http") and u not in seen:
            seen.add(u)
            out.append({
                "url": u,
                "title": str(d.get("title") or ""),
                "snippet": str(d.get("snippet") or d.get("content") or d.get("description") or "")[:400],
            })
    return out


def extract_text(resp):
    """Return the longest string in a fetch response (that's the page content)."""
    best = ""

    def rec(o):
        nonlocal best
        if isinstance(o, str):
            if len(o) > len(best):
                best = o
        elif isinstance(o, dict):
            for v in o.values():
                rec(v)
        elif isinstance(o, list):
            for v in o:
                rec(v)

    rec(resp)
    return best


def html_to_text(html: str) -> str:
    html = re.sub(r"(?is)<(script|style|noscript).*?</\1>", " ", html)
    html = re.sub(r"(?s)<[^>]+>", " ", html)
    html = re.sub(r"&nbsp;|&#160;", " ", html)
    return re.sub(r"\s+", " ", html).strip()


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip().lower()


def hint_to_url(hint: str):
    """'stripe.com/docs/api' -> 'https://stripe.com/docs/api'. Returns None if no domain."""
    token = (hint or "").split()[0] if hint else ""
    if "." not in token:
        return None
    return token if token.startswith("http") else "https://" + token


def host(url: str) -> str:
    return urlparse(url).netloc.lower().replace("www.", "")


# ----------------------------------------------------------------------------
# Composio search / fetch
# ----------------------------------------------------------------------------
class Web:
    def __init__(self):
        from composio import Composio
        self.c = Composio(
            api_key=os.environ["COMPOSIO_API_KEY"],
            toolkit_versions={"composio_search": "latest"},
        )
        self.search_slug = None

    def _exec(self, slug, args):
        try:
            r = self.c.tools.execute(slug, arguments=args, user_id=COMPOSIO_USER_ID)
        except Exception as e:
            if "version" in str(e).lower():
                r = self.c.tools.execute(
                    slug, arguments=args, user_id=COMPOSIO_USER_ID,
                    dangerously_skip_version_check=True,
                )
            else:
                raise
        if isinstance(r, dict) and r.get("successful") is False:
            raise RuntimeError(str(r.get("error") or "tool returned successful=false"))
        return r

    def search(self, query: str):
        slugs = [self.search_slug] if self.search_slug else SEARCH_SLUGS
        last_err = None
        for slug in slugs:
            try:
                args = {"query": query}
                resp = self._exec(slug, args)
                results = extract_results(resp)
                if results:
                    self.search_slug = slug
                    return results[:RESULTS_PER_SEARCH]
            except Exception as e:  # try next slug
                last_err = e
                log("search_slug_failed", slug=slug, error=str(e)[:300])
        if last_err:
            raise last_err
        return []

    def fetch(self, url: str) -> str:
        """Composio fetch first; plain HTTP as a fallback."""
        for args in ({"urls": [url]}, {"url": url}):
            try:
                text = extract_text(self._exec(FETCH_SLUG, args))
                if len(text) > 300:
                    return text
            except Exception as e:
                log("composio_fetch_failed", url=url, error=str(e)[:200])
        try:
            r = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0 (research-agent)"})
            if r.ok:
                text = html_to_text(r.text)
                if len(text) > 300:
                    return text
                log("page_empty_maybe_js", url=url, chars=len(text))
            else:
                log("http_error", url=url, status=r.status_code)
        except Exception as e:
            log("requests_failed", url=url, error=str(e)[:200])
        return ""


def rank_urls(results, hint_url):
    """Official docs first, then anything docs-like. Drops social / video / forum sites."""
    hint_host = host(hint_url) if hint_url else ""
    scored = []
    for r in results:
        u = r["url"]
        if any(d in u for d in SKIP_DOMAINS):
            continue
        s = 0
        h = host(u)
        if hint_host and (h.endswith(hint_host) or hint_host.endswith(h)):
            s += 3
        if re.search(r"docs|developer|api|reference", u, re.I):
            s += 2
        if re.search(r"auth|getting-started|quickstart|credentials|oauth", u, re.I):
            s += 1
        if "github.com" in h or "mcp" in u.lower():
            s += 1
        scored.append((s, r))
    scored.sort(key=lambda x: -x[0])
    return [r for _, r in scored]


# ----------------------------------------------------------------------------
# Gemini extraction
# ----------------------------------------------------------------------------
PROMPT = """You are a careful research analyst for Composio, a company that turns apps into tools AI agents can call.
Research the app "{app}" (category: {category}). Use ONLY the page excerpts below. Do not use outside knowledge.

RULES (very important):
- Every claim needs evidence: a URL taken from the pages below and a SHORT exact quote (max 25 words) copied word-for-word from that page.
- If the pages do not prove something, use "unknown" and say so. NEVER guess.
- "self_serve" = can a developer get credentials alone, for free or on a trial?
- "buildable_verdict" = could this become an agent toolkit TODAY? yes / partly / no / unknown. If not "yes", put the main blocker in "main_blocker".
- Today is {today}.

Return ONLY one JSON object with exactly these keys:
{{
  "one_line_description": "what the app does, max 20 words",
  "auth_methods": list of any of {auth_values},
  "self_serve": one of {self_serve_values},
  "self_serve_note": "short explanation (plan name, approval step, etc.)",
  "api_type": one of {api_type_values},
  "api_breadth": one of {breadth_values},
  "existing_mcp": "yes" | "no" | "unknown",
  "mcp_url": "url or empty string",
  "buildable_verdict": one of {verdict_values},
  "main_blocker": one of {blocker_values},
  "blocker_note": "one sentence",
  "has_free_tier": "yes" | "no" | "unknown",
  "has_webhooks": "yes" | "no" | "unknown",
  "has_openapi_spec": "yes" | "no" | "unknown",
  "rate_limits_documented": "yes" | "no" | "unknown",
  "confidence": "high" | "medium" | "low",
  "evidence": [ {{"field": "auth_methods", "url": "...", "quote": "..."}} ]   // at least one item per: auth_methods, self_serve, api_type, existing_mcp
}}

PAGES:
{pages}
"""


def build_prompt(app, category, pages):
    blocks = []
    for i, p in enumerate(pages, 1):
        blocks.append(f"--- PAGE {i} | URL: {p['url']} ---\n{p['text'][:MAX_CHARS_PER_PAGE]}\n")
    return PROMPT.format(
        app=app, category=category, today=date.today().isoformat(),
        auth_values=AUTH_VALUES, self_serve_values=SELF_SERVE_VALUES,
        api_type_values=API_TYPE_VALUES, breadth_values=BREADTH_VALUES,
        verdict_values=VERDICT_VALUES, blocker_values=BLOCKER_VALUES,
        pages="\n".join(blocks) if blocks else "(no pages could be read)",
    )


def call_gemini(client, prompt):
    from google.genai import types
    last = None
    for attempt in range(6):
        try:
            r = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0, response_mime_type="application/json"),
            )
            txt = (r.text or "").strip()
            txt = re.sub(r"^```(?:json)?|```$", "", txt).strip()
            return json.loads(txt)
        except Exception as e:
            last = e
            msg = str(e)
            wait = 25 * (attempt + 1) if ("429" in msg or "RESOURCE_EXHAUSTED" in msg) else 4 * (attempt + 1)
            log("gemini_retry", attempt=attempt + 1, wait=wait, error=msg[:200])
            time.sleep(wait)
    raise last


def clean_enum(value, allowed, default="unknown"):
    return value if value in allowed else default


def verify_evidence(evidence, pages):
    """Check each quote really appears in the page it points to. Returns (checked_evidence, ratio)."""
    by_url = {p["url"]: norm(p["text"]) for p in pages}
    all_text = " ".join(by_url.values())
    checked, ok = [], 0
    for ev in evidence or []:
        if not isinstance(ev, dict):
            continue
        q = norm(ev.get("quote", ""))
        u = ev.get("url", "")
        found = bool(q) and len(q) > 8 and (q in by_url.get(u, "") or q in all_text)
        in_right_page = bool(q) and q in by_url.get(u, "")
        ev = {**ev, "quote_found": found, "quote_on_cited_page": in_right_page,
              "url_was_read": u in by_url}
        ok += 1 if found else 0
        checked.append(ev)
    return checked, (round(ok / len(checked), 2) if checked else 0.0)


# ----------------------------------------------------------------------------
# per-app pipeline
# ----------------------------------------------------------------------------
def research_app(row, web, gem):
    app, category, hint = row["app"], row["category"], row["hint_url"]
    hint_url = hint_to_url(hint)
    rec = {"id": int(row["id"]), "app": app, "category": category, "hint_url": hint}
    errors = []

    # 1. SEARCH
    queries = [
        f"{app} API authentication docs",
        f"{app} API getting started developer credentials",
        f"{app} MCP server",
    ]
    results = []
    for q in queries:
        try:
            results += web.search(q)
        except Exception as e:
            errors.append(f"search '{q}': {str(e)[:150]}")
            log("search_failed", app=app, query=q, error=str(e)[:300])
        time.sleep(0.5)

    ranked = rank_urls(results, hint_url)
    urls = []
    if hint_url:
        urls.append(hint_url)
    for r in ranked:
        if r["url"] not in urls:
            urls.append(r["url"])

    # 2. READ
    pages = []
    for u in urls:
        if len(pages) >= MAX_PAGES:
            break
        text = web.fetch(u)
        if text:
            pages.append({"url": u, "text": text})
    (RAW_DIR / str(rec["id"])).mkdir(parents=True, exist_ok=True)
    for i, p in enumerate(pages, 1):
        (RAW_DIR / str(rec["id"]) / f"{i}.txt").write_text(f"URL: {p['url']}\n\n{p['text']}", encoding="utf-8")
    if not pages:
        errors.append("no pages could be read")
        log("no_pages", app=app)

    # 3. EXTRACT
    try:
        data = call_gemini(gem, build_prompt(app, category, pages))
    except Exception as e:
        errors.append(f"gemini: {str(e)[:200]}")
        log("extract_failed", app=app, error=str(e)[:300])
        data = {}

    # clean values so the table stays consistent
    auth = data.get("auth_methods") or []
    if isinstance(auth, str):
        auth = [auth]
    rec.update({
        "one_line_description": str(data.get("one_line_description", ""))[:200],
        "auth_methods": [a for a in auth if a in AUTH_VALUES] or ["Unknown"],
        "self_serve": clean_enum(data.get("self_serve"), SELF_SERVE_VALUES),
        "self_serve_note": str(data.get("self_serve_note", ""))[:300],
        "api_type": clean_enum(data.get("api_type"), API_TYPE_VALUES, "Unknown"),
        "api_breadth": clean_enum(data.get("api_breadth"), BREADTH_VALUES),
        "existing_mcp": clean_enum(data.get("existing_mcp"), ["yes", "no", "unknown"]),
        "mcp_url": str(data.get("mcp_url", "")),
        "buildable_verdict": clean_enum(data.get("buildable_verdict"), VERDICT_VALUES),
        "main_blocker": clean_enum(data.get("main_blocker"), BLOCKER_VALUES),
        "blocker_note": str(data.get("blocker_note", ""))[:300],
        "has_free_tier": clean_enum(data.get("has_free_tier"), ["yes", "no", "unknown"]),
        "has_webhooks": clean_enum(data.get("has_webhooks"), ["yes", "no", "unknown"]),
        "has_openapi_spec": clean_enum(data.get("has_openapi_spec"), ["yes", "no", "unknown"]),
        "rate_limits_documented": clean_enum(data.get("rate_limits_documented"), ["yes", "no", "unknown"]),
        "confidence": clean_enum(data.get("confidence"), ["high", "medium", "low"], "low"),
    })

    # 4. CHECK quotes against the real page text
    evidence, ratio = verify_evidence(data.get("evidence"), pages)
    rec["evidence"] = evidence
    rec["evidence_urls"] = sorted({e.get("url") for e in evidence if e.get("url")})
    rec["_meta"] = {
        "pages_read": [p["url"] for p in pages],
        "evidence_quote_match_ratio": ratio,
        "errors": errors,
        "model": GEMINI_MODEL,
        "search_slug": web.search_slug,
        "run_date": date.today().isoformat(),
        "needs_human": bool(errors) or ratio < 0.7 or rec["confidence"] == "low" or not pages,
    }
    return rec


# ----------------------------------------------------------------------------
# main
# ----------------------------------------------------------------------------
def load_rows(path="apps.csv"):
    with open(ROOT / path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def save(out_path, records):
    with _save_lock:
        data = sorted(records.values(), key=lambda r: r["id"])
        Path(out_path).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description="Research apps for Composio toolkit-buildability.")
    ap.add_argument("--app", help="research one app by name (case-insensitive)")
    ap.add_argument("--all", action="store_true", help="research every app in apps.csv")
    ap.add_argument("--ids", help="comma-separated ids, e.g. 1,5,12")
    ap.add_argument("--out", default="results_v1.json")
    ap.add_argument("--workers", type=int, default=3, help="parallel apps (keep low on Gemini free tier)")
    ap.add_argument("--resume", action="store_true", help="skip apps already in --out")
    ap.add_argument("--limit", type=int, help="only the first N apps (for testing)")
    args = ap.parse_args()

    for k in ("COMPOSIO_API_KEY", "GEMINI_API_KEY"):
        if not os.getenv(k):
            sys.exit(f"Missing {k}. Put it in your .env file.")

    rows = load_rows()
    if args.app:
        rows = [r for r in rows if args.app.lower() in r["app"].lower()]
        if not rows:
            sys.exit(f"No app matching '{args.app}' in apps.csv")
    elif args.ids:
        wanted = {int(x) for x in args.ids.split(",")}
        rows = [r for r in rows if int(r["id"]) in wanted]
    elif not args.all:
        sys.exit("Use --app NAME, --ids 1,2,3 or --all")
    if args.limit:
        rows = rows[: args.limit]

    records = {}
    out_path = ROOT / args.out
    if args.resume and out_path.exists():
        for r in json.loads(out_path.read_text(encoding="utf-8")):
            if not r.get("_meta", {}).get("errors"):
                records[r["id"]] = r
        rows = [r for r in rows if int(r["id"]) not in records]
        print(f"Resuming: {len(records)} done, {len(rows)} to go")

    from google import genai
    web = Web()
    gem = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    start = time.time()
    done = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = {pool.submit(research_app, r, web, gem): r for r in rows}
        for fut in as_completed(futs):
            r = futs[fut]
            try:
                rec = fut.result()
            except Exception as e:  # never let one app kill the whole run
                log("app_crashed", app=r["app"], error=str(e)[:300])
                rec = {"id": int(r["id"]), "app": r["app"], "category": r["category"],
                       "hint_url": r["hint_url"], "_meta": {"errors": [f"crash: {e}"], "needs_human": True}}
            records[rec["id"]] = rec
            save(out_path, records)
            done += 1
            flag = " [NEEDS HUMAN]" if rec["_meta"].get("needs_human") else ""
            print(f"[{done}/{len(rows)}] {rec['app']}: verdict={rec.get('buildable_verdict','?')} "
                  f"auth={rec.get('auth_methods','?')} self_serve={rec.get('self_serve','?')}{flag}")

    flagged = sum(1 for r in records.values() if r["_meta"].get("needs_human"))
    print(f"\nDone in {(time.time()-start)/60:.1f} min. Saved {len(records)} apps to {out_path.name}. "
          f"{flagged} flagged for human review. Log: {LOG_FILE.name}")


if __name__ == "__main__":
    main()
