# AI Product Ops Research Agent — 100-App Integration Feasibility Study

## Overview

This project investigates 100 software applications across 10 categories to evaluate their suitability for AI-agent integrations and toolkit development.

The goal is to automate the early research process involved in deciding whether an application can become a tool that an AI agent can call.

For each application, the research pipeline examines:
- Category and one-line product description
- Authentication methods
- Developer access: free, trial, paid, admin-approved, or partner-gated
- Public API availability and API type
- API breadth and existing MCP availability
- Integration buildability and primary blockers
- Supporting documentation URLs and evidence quotations

The project combines an AI research agent, source verification, manual review, and an interactive HTML dashboard.

## 1. Research Scope

The dataset contains **100 applications across 10 categories**:

| Category | Applications |
|---|---:|
| CRM and Sales | 10 |
| Support and Helpdesk | 10 |
| Communications and Messaging | 10 |
| Marketing, Ads, Email and Social | 10 |
| Ecommerce | 10 |
| Data, SEO and Scraping | 10 |
| Developer, Infra and Data Platforms | 10 |
| Productivity and Project Management | 10 |
| Finance and Fintech | 10 |
| AI, Research and Media-native | 10 |
| **Total** | **100** |

## 2. Key Findings

### API access and integration patterns

- **71%** of applications are classified as free or trial-accessible (43 free and 28 trial).
- **94 applications** have REST API support, including applications that also support GraphQL.
- **97 applications** have REST or GraphQL API support.
- OAuth2 appears in 68 applications, while API keys appear in 58. Authentication methods can overlap.
- 81 applications received a buildability verdict of `yes`, 17 received `partly`, one was `unknown`, and one was `no`.
- 81 applications have an existing MCP marked as available; 11 remain unknown and 8 are marked no.

### What these patterns suggest

1. **API availability is not the same as integration readiness.** An application may expose a public API but still require paid access, administrative approval, or additional permissions.
2. **OAuth2 and API keys dominate the authentication landscape.** A reusable integration pipeline should support both.
3. **Self-serve access creates opportunities.** Free and trial-accessible applications are promising candidates for early integration research.
4. **Access restrictions are important blockers.** Paid plans, admin approval, unclear authentication requirements, and account-level restrictions can affect buildability.
5. **Human verification remains necessary.** Documentation can be incomplete, ambiguous, or difficult to validate automatically.

## 3. Research Agent

The research pipeline was developed in Python to automate application research across the 100-app dataset.

### Workflow

1. **Input:** Reads the application list from `apps.csv`.
2. **Search:** Searches the web for relevant developer documentation and API information.
3. **Fetch:** Retrieves source pages and extracts readable content.
4. **AI extraction:** Uses Groq LLMs to extract structured application information.
5. **Evidence verification:** Checks extracted quotations against their cited source URLs.
6. **Structured output:** Saves application records in JSON format.
7. **Human review:** Flags uncertain records and creates review queues.
8. **Analysis:** Compares results, identifies patterns, and prepares dashboard data.

### Technology

| Component | Implementation |
|---|---|
| Language | Python |
| Primary LLM | Groq |
| Optional LLM fallback | Google Gemini |
| Search | DuckDuckGo through `ddgs`; optional Tavily |
| Page retrieval | HTTP requests and Jina Reader fallback |
| Data processing | Python, JSON and CSV |
| Dashboard | HTML, CSS and JavaScript |

**Implementation note:** This is an independent Python research pipeline. It uses Composio-related integration research criteria, but does not claim to use the Composio SDK or MCP to execute the research itself.

### Where human input was needed

Human review was used to:
- Check ambiguous or incomplete documentation.
- Correct metadata and evidence mismatches.
- Recover records where automated research failed.
- Compare the revised output against a manually checked reference.
- Preserve uncertain findings instead of forcing a confident verdict.

## 4. Verification and Accuracy

The project uses a manual verification sample of 25 applications, covering 125 field-level checks.

| Verification measure | Result |
|---|---:|
| V1 correct | 53 |
| V1 wrong | 9 |
| V1 unclear | 63 |
| V1 agreement among determinate checks | 85.5% (53/62) |
| V2 matches | 58 |
| V2 mismatches | 4 |
| V2 unscored | 63 |
| V2 comparison agreement | 93.5% (58/62) |

### Important methodology note

The V2 comparison includes manual corrections aligned with the human reference. Therefore, **93.5% is comparison agreement, not an independent second-pass accuracy measurement**. It should not be interpreted as proof that the complete 100-app dataset is 93.5% accurate.

Four mismatches remain in the comparison, and 63 checks were unclear and not scored.

A total of 58 application records are flagged for further human review. Paygent Connect (ID 84) remains a known evidence gap.

The verification process is documented in:
- `sheet_v1.csv`
- `step6_verification_completed.xlsx`
- `step7_human_review_queue.csv`
- `step7_supplemental_review_queue.csv`
- `step7_v2_comparison.csv`

## 5. Interactive Case Study Dashboard

The `site/` directory contains the self-contained HTML dashboard and its supporting data files.

The dashboard includes:
- Key findings and research statistics
- Authentication and API distribution
- Self-serve access and buildability patterns
- Searchable application-level research table
- Evidence/source links
- V1 and V2 verification comparison
- Human-review status and known limitations
- Downloadable research data

### Run the dashboard locally

From the project root:

```bash
python -m http.server 8000 --directory site
```

Open `http://localhost:8000` in your browser.

## 6. Repository Structure

```text
app-research-agent/
│
├── apps.csv
├── agent_v2.py
├── agent_v3_recovery.py
├── requirements.txt
├── .gitignore
│
├── results_v1_FROZEN.json
├── results_v2.json
├── sheet_v1.csv
├── step6_verification_completed.xlsx
│
├── step7_human_review_queue.csv
├── step7_supplemental_review_queue.csv
├── step7_v2_comparison.csv
│
├── analyze_patterns.py
├── compare_v2.py
├── make_sheet.py
├── manual_recovery.py
├── manual_evidence_patch.py
├── prepare_supplemental_review.py
├── finalize_remaining_corrections.py
│
└── site/
    ├── index.html
    ├── results.json
    ├── step7_human_review_queue.csv
    ├── step7_supplemental_review_queue.csv
    └── step7_v2_comparison.csv
```

## 7. Setup and Run the Agent

### Requirements

- Python
- A Groq API key
- Optional Gemini API key
- Optional Tavily API key

Install dependencies:

```bash
pip install -r requirements.txt
```

Create a `.env` file in the project root:

```env
GROQ_API_KEY=your_groq_api_key
GEMINI_API_KEY=
TAVILY_API_KEY=
```

Keep `.env` private and never commit API keys.

### Useful commands

Test the connection:

```bash
python agent_v2.py --ping
```

Research one application:

```bash
python agent_v2.py --app "Slack"
```

Research selected application IDs:

```bash
python agent_v2.py --ids 1,5,12
```

Research all applications:

```bash
python agent_v2.py --all --out results_v2.json
```

Resume an interrupted run:

```bash
python agent_v2.py --all --out results_v2.json --resume
```

## 8. Limitations and Next Steps

- Some application documentation is incomplete or ambiguous.
- API availability does not guarantee that every endpoint is accessible to every developer account.
- Existing MCP availability and buildability classifications may need additional validation.
- Some records still require human review.
- The project evaluates documented integration feasibility; it does not establish live connectivity to all 100 applications.

Future improvements include more field-specific evidence verification, independent second-pass validation, live API connectivity tests, and deeper MCP capability checks.

---

**Project deliverable:** An AI-assisted research pipeline and interactive case study for evaluating integration feasibility across 100 applications.