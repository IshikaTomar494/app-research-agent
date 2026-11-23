#!/usr/bin/env python3
"""
App research agent (free web search + Groq LLM, Gemini optional backup).

For each app in apps.csv it:
  1. SEARCH  - runs 2 free web searches
  2. READ    - fetches the best 5 pages (official docs first)
  3. EXTRACT - asks the LLM (Groq) for a strict JSON answer with a URL + quote per claim
  4. CHECK   - verifies that every quote really appears in the fetched page
  5. SAVE    - writes results JSON + raw pages (so you can show your work)

Usage:
  python agent.py --ping                         # test search + LLM keys
  python agent.py --models                       # list Groq models your key can use
  python agent.py --app "Stripe" --out test.json # one app (test first! use a throwaway --out)
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

load_dotenv(override=True)  # the .env file wins over any old key set elsewhere on your PC


def _env_key(name: str) -> str:
    """Read a key from the environment and remove accidental spaces / quotes."""
    return os.getenv(name, "").strip().strip("\"'").strip()


def get_key() -> str:
    """Gemini key (optional backup LLM)."""
    return _env_key("GEMINI_API_KEY")


def get_groq_key() -> str:
    """Groq key (main LLM)."""
    return _env_key("GROQ_API_KEY")

ROOT = Path(__file__).parent
RAW_DIR = ROOT / "raw"
LOG_FILE = ROOT / "agent_log.jsonl"

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")   # optional backup only
# Groq models, tried in order. llama-3.3-70b / llama-3.1-8b were shut down on 2026-08-16.
# Override in .env with GROQ_MODELS=model1,model2 (run `python agent.py --models` to see what works).
GROQ_MODELS = [m.strip() for m in os.getenv("GROQ_MODELS", "openai/gpt-oss-120b,openai/gpt-oss-20b").split(",") if m.strip()]
GROQ_URL = "https://api.groq.com/openai/v1"
GROQ_TPM = int(os.getenv("GROQ_TPM", "8000"))             # tokens/minute budget PER MODEL. Lower it if you still see 429s.
PROMPT_CHARS = int(os.getenv("PROMPT_CHARS", "10000"))    # total page text sent to the LLM per app
MAX_OUTPUT_TOKENS = 3000
COMPOSIO_USER_ID = os.getenv("COMPOSIO_USER_ID", "default")
MAX_PAGES = 5            # pages read per app
MAX_CHARS_PER_PAGE = 10000
RESULTS_PER_SEARCH = 6

# 100% free stack: DuckDuckGo search (ddgs package) + plain web requests + Jina Reader for
# JavaScript-heavy pages + Gemini free tier. No paid services.

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
    """Free search + free page reading. No Composio charges."""

    def __init__(self):
        from ddgs import DDGS
        self.ddgs = DDGS()
        self.tavily_key = os.getenv("TAVILY_API_KEY", "").strip().strip("\"'").strip()
        self.search_slug = "tavily" if self.tavily_key else "ddgs (DuckDuckGo)"

    def _tavily(self, query: str):
        r = requests.post(
            "https://api.tavily.com/search",
            headers={"Authorization": f"Bearer {self.tavily_key}"},
            json={"query": query, "max_results": RESULTS_PER_SEARCH, "search_depth": "basic"},
            timeout=30,
        )
        if not r.ok:
            raise RuntimeError(f"tavily {r.status_code}: {r.text[:200]}")
        return [{"url": x["url"], "title": x.get("title", ""), "snippet": str(x.get("content", ""))[:400]}
                for x in r.json().get("results", []) if x.get("url")]

    BACKENDS = ["auto", "duckduckgo", "bing", "brave", "yahoo", "mojeek", "google"]

    def search(self, query: str):
        """Tavily first (if a key is set), then several free backends."""
        last = None
        if self.tavily_key:
            try:
                out = self._tavily(query)
                if out:
                    self.search_slug = "tavily"
                    return out
            except Exception as e:
                last = e
                log("tavily_failed", query=query, error=str(e)[:200])
        for rnd in range(2):
            for backend in self.BACKENDS:
                try:
                    raw = self.ddgs.text(query, max_results=RESULTS_PER_SEARCH + 2, backend=backend) or []
                    out = []
                    for r in raw:
                        u = r.get("href") or r.get("url") or r.get("link")
                        if isinstance(u, str) and u.startswith("http"):
                            out.append({"url": u, "title": str(r.get("title") or ""),
                                        "snippet": str(r.get("body") or "")[:400]})
                    if out:
                        self.search_slug = f"ddgs/{backend}"
                        return out[:RESULTS_PER_SEARCH]
                    last = RuntimeError(f"{backend}: 0 results")
                except Exception as e:
                    last = e
                    log("search_backend_failed", backend=backend, query=query, error=str(e)[:150])
                time.sleep(0.7)
            time.sleep(4)
        raise last or RuntimeError("search failed")

    def fetch(self, url: str) -> str:
        """Plain HTTP first. If the page is empty (JavaScript site), try Jina Reader (free)."""
        try:
            r = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0 (research-agent)"})
            if r.ok:
                text = html_to_text(r.text)
                if len(text) > 1500:
                    return text
                log("page_short_trying_jina", url=url, chars=len(text))
            else:
                log("http_error", url=url, status=r.status_code)
        except Exception as e:
            log("requests_failed", url=url, error=str(e)[:200])
        try:
            r = requests.get("https://r.jina.ai/" + url, timeout=40,
                             headers={"Accept": "text/plain"})
            time.sleep(3)  # free tier is rate limited
            if r.ok and len(r.text) > 300:
                return r.text
            log("jina_failed", url=url, status=r.status_code)
        except Exception as e:
            log("jina_error", url=url, error=str(e)[:200])
        return ""


def is_official(url, hint_url):
    """True if the page belongs to the app's own site/repo (the hint_url in apps.csv)."""
    if not hint_url:
        return False
    hh = host(hint_url)
    if hh == "github.com":   # any github.com page would match otherwise; require the same repo
        return url.lower().startswith(hint_url.lower().rstrip("/"))
    h = host(url)
    return h.endswith(hh) or hh.endswith(h)


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
        if is_official(u, hint_url):
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
- The app's official site/repo is: {hint}. Each page below is tagged OFFICIAL (the app's own site/repo) or THIRD-PARTY.
- Many names are shared by unrelated products. Base auth_methods, self_serve, api_type and api_breadth ONLY on OFFICIAL pages. If a THIRD-PARTY page is about a different product with a similar name, ignore it completely. Use THIRD-PARTY pages only to confirm an MCP server, and only if it is clearly for this exact app.
- If the app is a command-line tool or library with no web API, no account and no credentials (for example a GitHub project), set auth_methods to ["None"], self_serve to "not_applicable", api_type to "SDK/CLI only" and main_blocker to "cli_only". Do NOT invent credentials.

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


# ----------------------------------------------------------------------------
# LLM layer: Groq (main) -> Gemini (optional backup)
# ----------------------------------------------------------------------------
class FatalLLMError(Exception):
    """Bad API key etc. Retrying will never help, so stop the whole run."""


KEYWORDS = (
    "auth", "oauth", "api key", "api-key", "apikey", "token", "bearer", "credential", "scope",
    "mcp", "model context protocol", "rate limit", "webhook", "openapi", "swagger", "graphql",
    "pricing", "free", "trial", "approval", "approved", "partner", "contact sales", "sandbox",
    "developer account", "paid plan", "enterprise", "app review",
)


def smart_excerpt(text: str, limit: int) -> str:
    """Keep the start of the page + the 500-char chunks that mention auth/pricing/MCP words.
    Much better than blindly cutting the first N characters, and keeps the prompt small."""
    if len(text) <= limit:
        return text
    head_len = limit // 4
    head, rest = text[:head_len], text[head_len:]
    size = 500
    scored = []
    for i in range(0, len(rest), size):
        c = rest[i:i + size]
        lc = c.lower()
        scored.append((sum(lc.count(k) for k in KEYWORDS), i, c))
    budget, used, picked = limit - head_len, 0, []
    for s, i, c in sorted(scored, key=lambda x: (-x[0], x[1])):
        if s == 0:
            break
        if used + len(c) > budget:
            continue
        picked.append((i, c))
        used += len(c)
    picked.sort()
    return head + " ... " + " ... ".join(c for _, c in picked)


def build_prompt(app, category, pages, hint_url=None):
    per_page = max(1500, PROMPT_CHARS // max(1, len(pages)))
    blocks = []
    for i, p in enumerate(pages, 1):
        tag = "OFFICIAL" if is_official(p["url"], hint_url) else "THIRD-PARTY"
        blocks.append(f"--- PAGE {i} | {tag} | URL: {p['url']} ---\n{smart_excerpt(p['text'], per_page)}\n")
    return PROMPT.format(
        app=app, category=category, today=date.today().isoformat(),
        hint=hint_url or "unknown",
        auth_values=AUTH_VALUES, self_serve_values=SELF_SERVE_VALUES,
        api_type_values=API_TYPE_VALUES, breadth_values=BREADTH_VALUES,
        verdict_values=VERDICT_VALUES, blocker_values=BLOCKER_VALUES,
        pages="\n".join(blocks) if blocks else "(no pages could be read)",
    )


class TokenLimiter:
    """Sliding 60-second window, so we stay under the tokens-per-minute cap instead of hitting 429."""

    def __init__(self, tpm):
        self.tpm = max(1000, int(tpm * 0.85))   # keep 15% headroom
        self.events = []
        self.lock = threading.Lock()

    def reserve(self, tokens):
        """Return 0 if we may send now (and reserve it), else seconds to wait."""
        tokens = min(tokens, self.tpm)
        with self.lock:
            now = time.time()
            self.events = [(t, n) for t, n in self.events if now - t < 60]
            used = sum(n for _, n in self.events)
            if used + tokens <= self.tpm or not self.events:
                self.events.append((now, tokens))
                return 0
            return max(1.0, 60 - (now - self.events[0][0]) + 0.5)


_limiters = {}
_dead_models = set()          # models that are gone or out of daily quota for this run
_no_extras = set()            # models that rejected reasoning_effort / response_format
_pool_lock = threading.Lock()


def _limiter(model):
    with _pool_lock:
        if model not in _limiters:
            _limiters[model] = TokenLimiter(GROQ_TPM)
        return _limiters[model]


def _retry_seconds(resp, msg):
    """How long Groq says to wait. Reads 'try again in 1m5.2s' or the Retry-After header."""
    m = re.search(r"try again in (?:(\d+)m)?(?:([\d.]+)s)?", msg)
    if m and (m.group(1) or m.group(2)):
        return int(m.group(1) or 0) * 60 + float(m.group(2) or 0)
    try:
        return float(resp.headers.get("retry-after", ""))
    except ValueError:
        return 20.0


def _parse_json(txt):
    txt = (txt or "").strip()
    txt = re.sub(r"^```(?:json)?|```$", "", txt).strip()
    try:
        data = json.loads(txt)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", txt, re.S)   # reasoning models sometimes add words around the JSON
        if not m:
            raise
        data = json.loads(m.group(0))
    if isinstance(data, list) and data:
        data = data[0]
    if not isinstance(data, dict):
        raise ValueError("LLM did not return a JSON object")
    return data


def call_groq(prompt):
    """Ask Groq. Spreads work across models, respects tokens/minute, switches model when one is
    out of quota or gone, and gives up after a bounded number of tries (never a 15-minute hang)."""
    key = get_groq_key()
    est_tokens = int(len(prompt) / 3.2) + 1500   # input estimate + room for reasoning/output
    last = None
    for attempt in range(12):
        live = [m for m in GROQ_MODELS if m not in _dead_models]
        if not live:
            raise RuntimeError(f"all Groq models unavailable. last error: {last}")
        model, waits = None, []
        for m in live:
            w = _limiter(m).reserve(est_tokens)
            if w == 0:
                model = m
                break
            waits.append(w)
        if model is None:               # every model is at its per-minute budget: wait for the first to free up
            time.sleep(min(waits))
            continue

        body = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "max_completion_tokens": MAX_OUTPUT_TOKENS,
        }
        if model not in _no_extras:
            body["response_format"] = {"type": "json_object"}
            if "gpt-oss" in model:
                body["reasoning_effort"] = "low"
        try:
            r = requests.post(f"{GROQ_URL}/chat/completions", timeout=90,
                              headers={"Authorization": f"Bearer {key}"}, json=body)
        except requests.RequestException as e:
            last = e
            log("groq_network_error", model=model, attempt=attempt + 1, error=str(e)[:200])
            time.sleep(3 * (attempt + 1))
            continue

        if r.ok:
            try:
                data = _parse_json(r.json()["choices"][0]["message"]["content"])
                data["_model_used"] = model
                return data
            except Exception as e:
                last = e
                log("groq_bad_json", model=model, attempt=attempt + 1, error=str(e)[:200])
                continue

        msg = r.text[:400]
        last = RuntimeError(f"{r.status_code} {msg[:200]}")
        low = msg.lower()
        if r.status_code in (401, 403):
            raise FatalLLMError(f"Groq rejected the key ({r.status_code}). Check GROQ_API_KEY in .env")
        if r.status_code in (404, 410) or "decommission" in low or "does not exist" in low or "model_not_found" in low:
            _dead_models.add(model)
            log("groq_model_dead", model=model, error=msg[:200])
        elif r.status_code == 429:
            wait = _retry_seconds(r, msg)
            if "per day" in low or "tpd" in low or wait > 90:
                _dead_models.add(model)   # daily quota used up: move on to the next model
                log("groq_daily_quota", model=model, wait=wait)
            else:
                log("groq_429", model=model, wait=wait, attempt=attempt + 1)
                time.sleep(min(wait, 60) + 1)
        elif r.status_code == 400 and model not in _no_extras and ("reasoning" in low or "response_format" in low or "json_object" in low):
            _no_extras.add(model)
            log("groq_dropping_extras", model=model, error=msg[:200])
        elif r.status_code == 400 and "json_validate_failed" in low:
            log("groq_bad_json", model=model, attempt=attempt + 1, error="json_validate_failed")
        else:
            log("groq_error", model=model, status=r.status_code, attempt=attempt + 1, error=msg[:200])
            time.sleep(min(5 * (attempt + 1), 30))
    raise RuntimeError(f"Groq failed after retries: {last}")


def call_gemini(client, prompt):
    """Optional backup (only used if GEMINI_API_KEY is set and Groq failed). Two tries, short waits."""
    from google.genai import types
    last = None
    for attempt in range(2):
        try:
            r = client.models.generate_content(
                model=GEMINI_MODEL, contents=prompt,
                config=types.GenerateContentConfig(temperature=0, response_mime_type="application/json"),
            )
            data = _parse_json(r.text)
            data["_model_used"] = GEMINI_MODEL
            return data
        except Exception as e:
            last = e
            log("gemini_retry", attempt=attempt + 1, model=GEMINI_MODEL, error=str(e)[:200])
            time.sleep(10)
    raise last


def call_llm(gem, prompt):
    """Groq first. If it fails and a Gemini client exists, try Gemini once. Otherwise raise."""
    try:
        return call_groq(prompt)
    except FatalLLMError:
        raise
    except Exception as e:
        log("groq_failed", error=str(e)[:300])
        if gem is None:
            raise
        return call_gemini(gem, prompt)


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
def load_raw_pages(rid):
    """Reload pages saved by an earlier run (raw/<id>/*.txt) so we don't search/fetch again."""
    d = RAW_DIR / str(rid)
    pages = []
    if d.exists():
        files = sorted(d.glob("*.txt"), key=lambda p: int(p.stem) if p.stem.isdigit() else 0)
        for f in files:
            m = re.match(r"URL: (\S+)\n\n(.*)", f.read_text(encoding="utf-8"), re.S)
            if m:
                pages.append({"url": m.group(1), "text": m.group(2)})
    return pages


def research_app(row, web, gem, reuse_raw=False):
    app, category, hint = row["app"], row["category"], row["hint_url"]
    hint_url = hint_to_url(hint)
    rec = {"id": int(row["id"]), "app": app, "category": category, "hint_url": hint}
    errors = []

    pages = load_raw_pages(rec["id"]) if reuse_raw else []
    if pages:
        log("reused_raw_pages", app=app, pages=len(pages))
    else:
        # 1. SEARCH
        site = host(hint_url) if hint_url else ""
        queries = [
            f"{app} {site} API authentication getting started developer credentials docs".replace("  ", " "),
            f"{app} {site} MCP server".replace("  ", " "),
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
        data = call_llm(gem, build_prompt(app, category, pages, hint_url))
    except FatalLLMError:
        raise
    except Exception as e:
        errors.append(f"llm: {str(e)[:200]}")
        log("extract_failed", app=app, error=str(e)[:300])
        data = {}

    model_used = data.pop("_model_used", "none") if isinstance(data, dict) else "none"
    rec["status"] = "ok" if data else "extract_failed"   # a failed call is NEVER a finding

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
        "model": model_used,
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


def check_models():
    """List the Groq models your key can use and test each one with a tiny prompt."""
    r = requests.get(f"{GROQ_URL}/models", headers={"Authorization": f"Bearer {get_groq_key()}"}, timeout=30)
    if not r.ok:
        print(f"Could not list models: {r.status_code} {r.text[:200]}")
        return
    skip = ("whisper", "guard", "tts", "embed", "prompt-guard", "safeguard", "orpheus")
    names = sorted(m["id"] for m in r.json().get("data", []) if not any(x in m["id"] for x in skip))
    print(f"Testing {len(names)} Groq chat models...\n")
    for n in names:
        try:
            x = requests.post(f"{GROQ_URL}/chat/completions", timeout=60,
                              headers={"Authorization": f"Bearer {get_groq_key()}"},
                              json={"model": n, "messages": [{"role": "user", "content": "Reply with the word OK."}],
                                    "max_completion_tokens": 50})
            tag = "OK" if x.ok else f"ERR {x.status_code}"
        except Exception as e:
            tag = "ERROR"
        print(f"  {tag:<8} {n}")
        time.sleep(1)
    print("\nPut working ones in .env like:  GROQ_MODELS=model-one,model-two   (best first)")


def ping():
    """Quick check that search and the LLM key work. Run: python agent.py --ping"""
    print("1) Free web search ...")
    try:
        w = Web()
        res = w.search("Stripe API documentation")
        print(f"   OK via {w.search_slug} - {len(res)} results, first: {res[0]['url'] if res else 'none'}")
    except Exception as e:
        print(f"   FAILED: {str(e)[:400]}")
    k = get_groq_key()
    print(f"2) Groq ... (key loaded: {k[:4]}...{k[-4:]}, length {len(k)}; a normal key starts with gsk_)")
    print(f"   models in use: {GROQ_MODELS}")
    try:
        data = call_groq('Return only this JSON: {"ok": true}')
        print(f"   OK - model {data.get('_model_used')} answered")
    except Exception as e:
        print(f"   FAILED: {str(e)[:400]}")


def main():
    ap = argparse.ArgumentParser(description="Research apps for Composio toolkit-buildability.")
    ap.add_argument("--app", help="research one app by name (case-insensitive)")
    ap.add_argument("--all", action="store_true", help="research every app in apps.csv")
    ap.add_argument("--ids", help="comma-separated ids, e.g. 1,5,12")
    ap.add_argument("--out", default="results_v1.json")
    ap.add_argument("--workers", type=int, default=2, help="parallel apps (keep low on the free tier)")
    ap.add_argument("--resume", action="store_true", help="skip apps already in --out")
    ap.add_argument("--limit", type=int, help="only the first N apps (for testing)")
    ap.add_argument("--ping", action="store_true", help="test search + Groq key, then exit")
    ap.add_argument("--models", action="store_true", help="list/test the Groq models your key can use, then exit")
    ap.add_argument("--reuse-raw", action="store_true", help="reuse pages saved in raw/ (skip search+read, only re-ask the LLM)")
    args = ap.parse_args()

    if not get_groq_key():
        sys.exit("Missing GROQ_API_KEY. Put it in your .env file (get one free at console.groq.com).")

    if args.ping:
        ping()
        return
    if args.models:
        check_models()
        return

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

    web = Web()
    gem = None   # optional Gemini backup, only if you set GEMINI_API_KEY
    if get_key():
        try:
            from google import genai
            gem = genai.Client(api_key=get_key())
        except ImportError:
            print("(google-genai not installed, skipping the Gemini backup)")

    start = time.time()
    done = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = {pool.submit(research_app, r, web, gem, args.reuse_raw): r for r in rows}
        for fut in as_completed(futs):
            r = futs[fut]
            try:
                rec = fut.result()
            except FatalLLMError as e:
                pool.shutdown(wait=False, cancel_futures=True)
                save(out_path, records)
                sys.exit(f"STOPPED: {e}")
            except Exception as e:  # never let one app kill the whole run
                log("app_crashed", app=r["app"], error=str(e)[:300])
                rec = {"id": int(r["id"]), "app": r["app"], "category": r["category"],
                       "hint_url": r["hint_url"], "_meta": {"errors": [f"crash: {e}"], "needs_human": True}}
            records[rec["id"]] = rec
            save(out_path, records)
            done += 1
            flag = " [NEEDS HUMAN]" if rec["_meta"].get("needs_human") else ""
            if rec.get("status") == "extract_failed":
                flag = " [EXTRACT FAILED - rerun with --resume]"
            print(f"[{done}/{len(rows)}] {rec['app']}: verdict={rec.get('buildable_verdict','?')} "
                  f"auth={rec.get('auth_methods','?')} self_serve={rec.get('self_serve','?')}{flag}")

    flagged = sum(1 for r in records.values() if r["_meta"].get("needs_human"))
    print(f"\nDone in {(time.time()-start)/60:.1f} min. Saved {len(records)} apps to {out_path.name}. "
          f"{flagged} flagged for human review. Log: {LOG_FILE.name}")


if __name__ == "__main__":
    main()
