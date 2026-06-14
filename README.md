# SEO & GEO Auditor

Audits any website for **Search Engine Optimisation (SEO)** and **Generative Engine Optimisation (GEO)**, scores each independently, and returns **two separate reports** with prioritized recommendations.

Built per `SEO_GEO_Auditor_Technical_Design.md`: a Python/FastAPI backend that runs one **agent per analysis category** concurrently with `asyncio`, plus a Vite + React frontend with two report tabs.

---

## Architecture

The codebase is organised into a small set of single-concept modules — each file maps to one clear idea, so it stays modular without a sprawl of tiny files.

```
backend/app/
├── main.py            # FastAPI app: /api routes + serves the built React app
├── config.py          # Loads all keys from .env into a typed Settings object
├── models.py          # All Pydantic models + enums (ParameterResult, Report, Audit, …)
├── clients.py         # Every external API client + shared HTTP helpers + Clients bundle
├── crawl.py           # Page I/O -> shared PageContext (fetcher + renderer + parser)
├── scoring.py         # Weighted scoring/grading + the Gemini narrative summary
├── orchestrator.py    # Runs crawl + PSI + all agents concurrently; connected-property registry
└── agents/
    ├── base.py        # BaseAgent + AgentContext + every shared helper (result factories, PSI/JSON-LD utils)
    ├── seo_agents.py  # The 7 SEO category agents
    └── geo_agents.py  # The 8 GEO category agents
```

### Data flow
1. **Crawl + PSI** run concurrently: the page is fetched (raw HTTP + rendered DOM) and PageSpeed Insights is queried for mobile + desktop.
2. The single **`PageContext`** is shared with all **15 agents**, which run **concurrently** (`asyncio.gather`). Each agent returns the `ParameterResult` rows for its category.
3. Each report is **scored** (Meeting = full credit, Partial = half, Not Meeting = zero; Manual/Not Measured excluded from the denominator).
4. **Two narrative summaries** (SEO + GEO) are generated in parallel via Gemini.
5. The API returns both reports; the UI shows them as two tabs.

---

## Setup

### 1. Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Optional: install the headless browser so JS-heavy pages render fully.
# Without it, the tool falls back to raw HTML (or Firecrawl) automatically.
playwright install chromium
```

All API keys are read from the project-root `.env` (already present). No keys are passed on the command line.

### 2. Frontend

```bash
cd frontend
npm install
npm run build
```

This produces `frontend/dist`, which the backend serves in production.

---

## Running

### One command (recommended)

From the project root:

```bash
# First time only
cd backend && python3 -m venv .venv && pip install -r requirements.txt && cd ..
npm install

# Every time
npm run dev
# open http://127.0.0.1:8000
```

Or use the shell wrapper (same behavior):

```bash
./scripts/run-dev.sh
```

The backend serves the built React UI and all `/api/*` routes on **port 8000**. Frontend changes rebuild automatically (`vite build --watch`); backend changes reload via uvicorn.

### Production-style (no file watching)

```bash
npm start
# open http://127.0.0.1:8000
```

### API

```bash
curl -X POST http://127.0.0.1:8000/api/audit \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://example.com"}'
```

Interactive docs: `http://127.0.0.1:8000/docs`.

---

## Connected mode (GA4 + Search Console)

Six first-party SEO parameters (CTR, sitemap submission, crawl frequency, dwell time, bounce rate, pogo-sticking) are **Measured** only for connected properties. Map a domain in [`backend/connected_properties.json`](backend/connected_properties.json):

```json
{
  "heuristicsaisolutions.com": {
    "gsc_site_url": "https://www.heuristicsaisolutions.com/",
    "ga4_property_id": "123456789"
  }
}
```

### OAuth CLI (recommended — personal Google account)

Search Console often rejects service-account emails in the UI. Use **your own Google account** instead:

1. **Google Cloud** (project `seogeoaudit-498619`): enable Search Console API, Google Analytics Data API, and Google Analytics Admin API.
2. **OAuth consent screen:** External; add scopes `webmasters.readonly` and `analytics.readonly`.
3. **Credentials → OAuth client ID → Desktop app** → download JSON → save as `secrets/google-oauth-client.json`.
4. **Optional `.env` paths** (defaults work if files live in `secrets/`):

```
GOOGLE_OAUTH_CLIENT_SECRETS=/path/to/secrets/google-oauth-client.json
GOOGLE_OAUTH_TOKEN_PATH=/path/to/secrets/google-oauth-token.json
```

5. **One-time sign-in** (run from the `backend` folder):

```bash
cd backend && source .venv/bin/activate
pip install -r requirements.txt
python scripts/google_auth.py
```

If your shell is **already in `backend`**, omit the `cd backend &&` part — otherwise you get `cd: no such file or directory: backend`.

To re-list GSC/GA4 after enabling APIs (no browser):

```bash
python scripts/google_auth.py --list-only
```

Sign in with the Google account that owns your GSC property. The script lists your GSC site URLs and GA4 property IDs.

6. Copy the exact `gsc_site_url` and numeric `ga4_property_id` into `connected_properties.json`, restart the backend, and re-run an audit.

Full details: [`secrets/README.md`](secrets/README.md).

### Service account (optional — agency / multi-tenant)

If GSC accepts your service-account email, set `GOOGLE_APPLICATION_CREDENTIALS` to the JSON key path. **OAuth takes priority** when `secrets/google-oauth-token.json` exists.

For any non-connected domain (or missing credentials), the 6 parameters fall back to **Manual** (excluded from the score).

---

## Graceful degradation

Every external client fails soft: if a key is missing/blocked or an API errors, the affected parameter is reported as **Not Measured** (and excluded from scoring) rather than breaking the audit.

> Note: PageSpeed Insights requires the **"PageSpeed Insights API"** to be enabled for `GOOGLE_API_KEY` in Google Cloud. If it is blocked, the Core Web Vitals category shows as *Not Measured* until the API is enabled.

---

## Tech stack

FastAPI · Uvicorn · httpx · BeautifulSoup/lxml · Playwright · PageSpeed Insights · GA4 + Search Console (OAuth or service account) · Gemini (via OpenAI-compatible endpoint) · OpenAI · Serper · Perplexity · SerpApi · Wikidata/Wikipedia · Google Knowledge Graph · Firecrawl · Vite + React.
