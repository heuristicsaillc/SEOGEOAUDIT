# SEO & GEO Auditor - Technical Design

Technical design for an application that audits any website for Search Engine Optimisation (SEO) and Generative Engine Optimisation (GEO), scores it, and produces two separate reports (one for SEO, one for GEO) with recommendations to improve each.

Status: GA4 + Google Search Console use **OAuth CLI** (personal Google account) as the primary auth path. A one-time browser sign-in saves a refresh token; `backend/connected_properties.json` maps each domain to its GSC site URL and GA4 Property ID. Up to **6 first-party SEO parameters** are scored for connected domains when APIs succeed. Service account remains an optional fallback (`GOOGLE_APPLICATION_CREDENTIALS`); OAuth token takes priority when both exist.

Setup guides (OAuth only, no service account): `Connected_Mode_Site_Owner_Guide.pdf` and `Connected_Mode_Tool_Operator_Guide.pdf` (regenerate via `generate_connected_guide_pdf.py`). Regenerate this document's PDF with `python3 generate_pdf.py SEO_GEO_Auditor_Technical_Design.md SEO_GEO_Auditor_Technical_Design.pdf`.

---

# 1. System overview

- A single Python/FastAPI application that exposes a JSON API and also serves a simple React frontend (one deployable unit).
- The user enters a URL; the app crawls/renders it, runs SEO and GEO analyzers across the full parameter catalog, scores each, and returns two reports.
- Gemini is the LLM used for all AI judgement (content quality, answerability, citation likelihood, etc.).
- SEO is crawl-based; non-crawlable SEO parameters are Manual and excluded from the score, except 6 that are measured when the domain is a connected GA4/GSC property.
- GEO is fully automated using external APIs plus Gemini (no Manual parameters).

# 2. Architecture and data flow

[[FLOW:architecture]]

End-to-end: the URL is fetched (raw HTTP + rendered DOM); the SEO and GEO analyzers read the page plus their data sources; results are scored independently; two reports are returned together and shown as two tabs in the UI.

# 3. Tech stack

- Backend: FastAPI + Uvicorn (Python). Serves the API and the built React app.
- Frontend: Vite + React (URL input, progress, two report tabs).
- Fetch/render: httpx (raw HTML, headers, redirects) + Playwright/Firecrawl (rendered DOM for JS-heavy pages).
- Parse: BeautifulSoup + lxml.
- Performance: Google PageSpeed Insights API (Lighthouse + lab Core Web Vitals + CrUX field data).
- First-party analytics: google-api-python-client + google-auth + google-auth-oauthlib (OAuth CLI), google-analytics-data (GA4 Data API). Credentials loaded by `app/google_auth.py` — OAuth refresh token first, service account fallback.
- LLM: Gemini via google-genai. OpenAI used only for ChatGPT-style citation checks.

# 4. Detection methods

- Crawl (auto) = httpx + Playwright/Firecrawl + BeautifulSoup parsing of the page, headers, robots/sitemap/llms.txt.
- PSI = Google PageSpeed Insights API.
- LLM = Gemini judgement.
- External = third-party API (GEO: SerpApi, Perplexity, OpenAI, Wikidata/Wikipedia, Google Knowledge Graph, Serper, X).
- First-party = GA4 / Search Console via OAuth token (or service-account fallback). Only for domains in `connected_properties.json`. Returns `DetectionMethod.FIRST_PARTY` with `Confidence.MEASURED` when scored.
- Manual = data the tool cannot obtain without third-party products (off-site link data, GBP) or when the domain is not connected; shown but not scored.
- Not Measured = an automated or first-party check was attempted but could not run (missing/blocked API key, GSC/GA4 API error, PSI unavailable); excluded from the score.

# 5. Scoring model

- Each scored parameter is rated Meeting (full credit) / Partial (half) / Not Meeting (zero).
- Only Meeting, Partial, and Not Meeting count toward category and final scores. **Manual** and **Not Measured** are shown in the report but excluded from the denominator.
- SEO Manual parameters: **6 off-site** (backlinks, GBP, etc.) are always Manual. **6 first-party** (CTR, sitemap GSC, log file analysis, dwell time, bounce rate, pogo-sticking) are Manual when the domain is not connected; they become First-party when connected and credentials are present.
- GA4 engagement rows (dwell, bounce, pogo) stay **Manual** until GA4 returns session data for the page; GSC rows can still score when GSC responds.
- GEO has no Manual parameters — all are scored or Not Measured.
- Category score = weighted average of that category's scored parameters; final SEO and GEO scores = weighted average across categories, mapped to 0-100 with a letter grade (A-F).

# 6. Recommendations

- Rule-based: every Partial / Not Meeting parameter carries a concrete fix, a priority (High/Med/Low), and an effort estimate, shown in the report's Recommendation column.
- Gemini-generated: a prioritized narrative summary at the top of each report (top fixes first), generated separately for SEO and GEO.

# 7. Reports

- Two separate reports returned in one API response and shown as two tabs.
- Each report header shows the final score + grade; each category shows a sub-score.
- Each category renders a table: Parameter | What to check | Rating | Recommendation. When a row has both `detail` and `recommendation`, the UI shows the recommendation with evidence `detail` beneath it (muted). SEO Manual and Not Measured rows are visually de-emphasised and noted as excluded from the score.
- SEO report adds a Core Web Vitals panel; GEO report adds an AI-citation appearance panel (which engines cite the site + competitor gap).

---

# Part 1 - SEO Parameters

## 01 Crawlability & Indexability

| Parameter | What to check | How it's checked | Auto/Manual | API key / tool |
|---|---|---|---|---|
| robots.txt | Correct disallow rules; no accidental crawl blocks on key pages | Fetch and parse /robots.txt | Automated | Crawl (no key) |
| sitemap.xml | Present; no 4xx/5xx URLs; lastmod populated | Fetch sitemap, validate URLs + status | Automated | Crawl (no key) |
| sitemap GSC-submission status | Submitted to Google Search Console | GSC sitemaps.list (connected); Meeting when submitted with no errors, Partial when errors on submitted sitemaps, Not Meeting when none registered; Not Measured on API error; else Manual | Connected (GSC) | OAuth token (or GOOGLE_APPLICATION_CREDENTIALS fallback) |
| Meta robots | No unintended noindex/nofollow; check X-Robots-Tag header | Parse meta tag + response headers | Automated | Crawl (no key) |
| Canonical tags | Self-referencing; no conflicting/chained canonicals | Parse <link rel=canonical> | Automated | Crawl (no key) |
| HTTP status & redirects | No redirect chains > 1 hop; 301 not 302 for permanent | Follow + record redirect chain | Automated | Crawl (no key) |
| Crawl depth (NEW) | Key pages reachable within 3 clicks from homepage | Limited internal crawl + depth graph | Automated | Crawl (no key) |
| Pagination handling (NEW) | rel=next/prev or infinite-scroll pattern; no thin dupes | Parse pagination markup | Automated | Crawl (no key) |
| Log file analysis (NEW) | Googlebot visit frequency; crawl budget waste | GSC urlInspection.index.inspect (connected); Meeting when indexed and crawled, Partial when crawled but not indexed; Not Measured when empty or API error; else Manual | Connected (GSC) | OAuth token (or GOOGLE_APPLICATION_CREDENTIALS fallback) |
| XML sitemap index (NEW) | Sitemap index pointing to sub-sitemaps (news/image/video) | Detect <sitemapindex> | Automated | Crawl (no key) |
| noarchive / nosnippet (NEW) | No accidental suppression of snippets or cached pages | Parse robots directives + headers | Automated | Crawl (no key) |

## 02 On-Page Signals

| Parameter | What to check | How it's checked | Auto/Manual | API key / tool |
|---|---|---|---|---|
| Title tag | 50-60 chars, primary keyword near front, unique | Parse <title>, length + keyword position | Automated | Crawl (no key) |
| Meta description | 150-160 chars, action-oriented, includes target keyword | Parse meta description | Automated | Crawl (no key) |
| Heading hierarchy | Single H1; logical H2->H3; no skipped levels | Parse heading tree | Automated | Crawl (no key) |
| Word count / content depth | Matches competitive benchmark; no thin content | Count words + Gemini depth judgement | Automated | Crawl + GEMINI_API_KEY |
| Image alt coverage | Informational images have alts; decorative use alt="" | Parse <img alt> coverage | Automated | Crawl (no key) |
| Internal links + anchor text | Keyword-rich anchors; no orphan pages; logical graph | Parse links + build internal graph | Automated | Crawl (no key) |
| Keyword usage | Primary keyword in title/H1/first 100 words; related terms | Text analysis + Gemini semantic check | Automated | Crawl + GEMINI_API_KEY |
| Duplicate content (NEW) | Near-duplicate pages consolidated via canonical/301 | Compare page fingerprints + canonicals | Automated | Crawl (no key) |
| Content freshness signals (NEW) | Visible publish + last-updated dates | Parse dates in HTML + schema | Automated | Crawl (no key) |
| Table of contents (NEW) | Anchor-linked ToC on long-form pages | Detect ToC anchors | Automated | Crawl (no key) |
| E-E-A-T signals on-page (NEW) | Author bio, credentials, About page, attribution | Parse author/about + Gemini judgement | Automated | Crawl + GEMINI_API_KEY |
| Outbound link quality (NEW) | Links to authoritative, topically relevant external sources | Parse outbound links + Gemini relevance | Automated | Crawl + GEMINI_API_KEY |
| Multimedia coverage (NEW) | Video, images, or infographics present | Detect media elements | Automated | Crawl (no key) |
| LSI / semantic coverage (NEW) | Topic completeness vs top-ranking pages | Gemini topic-model comparison | Automated | GEMINI_API_KEY |

## 03 Technical SEO

| Parameter | What to check | How it's checked | Auto/Manual | API key / tool |
|---|---|---|---|---|
| HTTPS / SSL | Valid cert; no mixed content; HSTS header | Inspect TLS + headers + page resources | Automated | Crawl (no key) |
| Mobile viewport | Meta viewport; no horizontal scroll; tap targets >= 44px | Parse viewport + PSI mobile audit | Automated | Crawl + PSI (GOOGLE_API_KEY) |
| URL structure | Lowercase, hyphens, keyword-rich, < 115 chars, no junk params | Analyze URL string | Automated | Crawl (no key) |
| hreflang | Correct lang/region; self-referencing; x-default set | Parse hreflang tags | Automated | Crawl (no key) |
| Broken links | 0 internal 4xx; external link monitoring | Crawl links + check status codes | Automated | Crawl (no key) |
| Render-blocking resources | CSS/JS deferred or async; critical CSS inlined | PSI audit + markup parse | Automated | PSI (GOOGLE_API_KEY) |
| JavaScript rendering (NEW) | Critical content not JS-only | Diff raw HTML vs rendered DOM | Automated | Crawl (Playwright/Firecrawl) |
| HTTP/2 or HTTP/3 (NEW) | Protocol version check | Inspect connection protocol | Automated | Crawl (no key) |
| Server response time (NEW) | TTFB < 200ms; server-side caching | Measure TTFB + PSI | Automated | Crawl + PSI (GOOGLE_API_KEY) |
| Image compression & format (NEW) | WebP/AVIF; lazy loading; explicit width/height | PSI image audit + markup parse | Automated | PSI (GOOGLE_API_KEY) |
| Third-party script impact (NEW) | Defer non-critical scripts | PSI third-party audit | Automated | PSI (GOOGLE_API_KEY) |
| Security headers (NEW) | CSP, X-Frame-Options, Referrer-Policy | Inspect response headers | Automated | Crawl (no key) |
| AMP / Web Stories (NEW) | Valid AMP markup + AMP-canonical pairing | Detect AMP markup | Automated | Crawl (no key) |

## 04 Core Web Vitals & Performance

| Parameter | What to check | How it's checked | Auto/Manual | API key / tool |
|---|---|---|---|---|
| LCP | <= 2.5s; main image/text block is largest element | PSI lab + CrUX field | Automated | PSI (GOOGLE_API_KEY) |
| CLS | <= 0.1; reserve space for media/embeds | PSI lab + CrUX field | Automated | PSI (GOOGLE_API_KEY) |
| INP | <= 200ms; replaces FID | PSI / CrUX field | Automated | PSI (GOOGLE_API_KEY) |
| TTFB | <= 800ms; server + CDN tuning | PSI / measured | Automated | PSI (GOOGLE_API_KEY) |
| Lighthouse scores | Performance, Accessibility, Best Practices, SEO >= 90 | PSI category scores | Automated | PSI (GOOGLE_API_KEY) |
| Field data (CrUX) (NEW) | Real-user field data; lab != real users | PSI CrUX data | Automated | PSI (GOOGLE_API_KEY) |
| Mobile vs desktop delta (NEW) | Run CWV separately for mobile and desktop | PSI run twice | Automated | PSI (GOOGLE_API_KEY) |
| Font loading strategy (NEW) | font-display: swap; preload key fonts; fallbacks | Parse CSS/font usage + PSI | Automated | Crawl + PSI (GOOGLE_API_KEY) |

## 05 Structured Data & Social

| Parameter | What to check | How it's checked | Auto/Manual | API key / tool |
|---|---|---|---|---|
| Schema.org JSON-LD | Article, Product, FAQ, HowTo, BreadcrumbList, Organization, LocalBusiness | Parse + validate JSON-LD | Automated | Crawl (no key) |
| OG / Twitter cards | og:title, og:image (1200x630), og:description, twitter:card | Parse meta tags | Automated | Crawl (no key) |
| Favicon | SVG + 32px PNG + apple-touch-icon | Detect favicon links | Automated | Crawl (no key) |
| Rich result eligibility (NEW) | Warnings/errors check | Validate schema against rich-result rules | Automated | Crawl (no key) |
| Breadcrumb schema (NEW) | BreadcrumbList on interior pages | Parse JSON-LD | Automated | Crawl (no key) |
| Sitelinks searchbox (NEW) | WebSite schema with potentialAction SearchAction | Parse JSON-LD | Automated | Crawl (no key) |
| Review / Rating schema (NEW) | AggregateRating on product/service pages | Parse JSON-LD | Automated | Crawl (no key) |
| Video schema (NEW) | VideoObject with thumbnail, duration, uploadDate | Parse JSON-LD | Automated | Crawl (no key) |

## 06 Off-Page & Authority

| Parameter | What to check | How it's checked | Auto/Manual | API key / tool |
|---|---|---|---|---|
| Backlink profile | Domain authority distribution; toxic ratio; anchor diversity | Requires off-site link index | Manual | Requires off-site link data |
| Referring domain count | Unique linking root domains; trend | Requires off-site link index | Manual | Requires off-site link data |
| Topical authority | Topic cluster breadth; hub-spoke internal linking | Internal graph + Gemini topic analysis | Automated | Crawl + GEMINI_API_KEY |
| Brand mentions (unlinked) | Citation signals across the web | Requires off-site monitoring | Manual | Requires off-site monitoring |
| Competitor link gap | Links competitors have that you lack | Requires off-site link index | Manual | Requires off-site link data |
| NAP consistency (local) - on-page | Name/Address/Phone present and consistent on page | Parse on-page NAP | Automated | Crawl (no key) |
| NAP consistency (local) - cross-directory | Identical across external directories | Requires directory data | Manual | Requires off-site data |
| Google Business Profile | Verified, complete listing; reviews; posts | Requires GBP ownership/listing data | Manual | Requires GBP |

## 07 UX & Engagement Signals

| Parameter | What to check | How it's checked | Auto/Manual | API key / tool |
|---|---|---|---|---|
| Click-through rate (CTR) | GSC CTR vs position benchmark | GSC searchanalytics.query (connected); scored Not Meeting when 0 impressions; Not Measured on API error; else Manual | Connected (GSC) | OAuth token (or GOOGLE_APPLICATION_CREDENTIALS fallback) |
| Dwell time / scroll depth | GA4 engagement proxy | GA4 runReport (connected + data), else Manual | Connected (GA4) | OAuth token (or GOOGLE_APPLICATION_CREDENTIALS fallback) |
| Bounce rate in context | High bounce interpreted by page type | GA4 runReport bounceRate (connected + data), else Manual | Connected (GA4) | OAuth token (or GOOGLE_APPLICATION_CREDENTIALS fallback) |
| Pogo-sticking risk | Users returning to SERP quickly = intent mismatch | GA4 + GSC derived (connected + GA4 data), else Manual | Connected (GA4+GSC) | OAuth token (or GOOGLE_APPLICATION_CREDENTIALS fallback) |
| Search intent alignment | Informational/navigational/commercial/transactional match | Gemini judges intent vs page type | Automated | GEMINI_API_KEY |

---

# Part 2 - GEO Parameters (fully automated)

## 01 Answerability

| Parameter | What to check | How it's checked | Auto/Manual | API key / tool |
|---|---|---|---|---|
| Concise top answer | Direct answer in first 40-50 words | Parse intro + Gemini judgement | Automated | Crawl + GEMINI_API_KEY |
| Question-phrased headings | H2/H3 as natural-language questions | Parse headings | Automated | Crawl (no key) |
| FAQ section | Marked up with FAQPage schema; long-tail variants | Parse JSON-LD + content | Automated | Crawl (no key) |
| TL;DR / summary box | Scannable summary easy for AI to lift | Detect summary + Gemini | Automated | Crawl + GEMINI_API_KEY |
| Definition blocks (NEW) | "X is defined as..." near the top | Pattern + Gemini detection | Automated | Crawl + GEMINI_API_KEY |
| Step-by-step answers (NEW) | Numbered steps with clear action verbs | Parse ordered lists | Automated | Crawl (no key) |
| Comparison answers (NEW) | Tables or "A vs B" sections for comparative queries | Detect comparison tables | Automated | Crawl (no key) |

## 02 Extractability

| Parameter | What to check | How it's checked | Auto/Manual | API key / tool |
|---|---|---|---|---|
| Semantic HTML | article/section/aside/figure used correctly; not div-soup | Parse DOM structure | Automated | Crawl (no key) |
| Chunkable paragraphs | Short paragraphs (2-4 sentences); one idea each | Analyze paragraph lengths | Automated | Crawl (no key) |
| Lists & tables | HTML ul/ol/table (not image-based) | Detect list/table elements | Automated | Crawl (no key) |
| Heading-to-content ratio (NEW) | Each heading followed by substantive content | Map headings to content blocks | Automated | Crawl (no key) |
| Code blocks / data blocks (NEW) | pre/code tags; machine-readable tables | Detect code/data markup | Automated | Crawl (no key) |
| No content in images/PDFs (NEW) | Text not locked inside images/PDFs | Detect text-in-image + Gemini OCR check | Automated | Crawl + GEMINI_API_KEY |
| Consistent terminology (NEW) | Same term used throughout; no synonym-switching | Gemini terminology analysis | Automated | GEMINI_API_KEY |

## 03 Citability & E-E-A-T

| Parameter | What to check | How it's checked | Auto/Manual | API key / tool |
|---|---|---|---|---|
| Author + credentials | Named author, bio, qualifications visible | Parse author block + Gemini | Automated | Crawl + GEMINI_API_KEY |
| Sources & citations | Outbound links to primary sources; references section | Parse citations/links | Automated | Crawl (no key) |
| Statistics & data | Quantitative claims with source attribution | Detect stats + Gemini | Automated | Crawl + GEMINI_API_KEY |
| Publish + updated dates | ISO 8601 dates in HTML + Article schema | Parse dates + JSON-LD | Automated | Crawl (no key) |
| About / Trust pages (NEW) | About, Contact, Privacy pages present | Fetch + detect trust pages | Automated | Crawl (no key) |
| Expert review signals (NEW) | "Medically reviewed by..."/"Fact-checked by..." labels | Pattern + Gemini detection | Automated | Crawl + GEMINI_API_KEY |
| Wikidata / Wikipedia entity (NEW) | Organisation/person entity exists | Query Wikidata + Wikipedia | Automated | Wikidata SPARQL + Wikipedia (no key) |
| Press mentions & awards (NEW) | Featured-in logos and award badges | On-page detection + Serper web search | Automated | Crawl + SERPER_API_KEY |
| Disclaimer / methodology (NEW) | Methodology explained for research/data content | Detect methodology + Gemini | Automated | Crawl + GEMINI_API_KEY |

## 04 AI Structured Data

| Parameter | What to check | How it's checked | Auto/Manual | API key / tool |
|---|---|---|---|---|
| FAQPage schema | Q&A pairs in JSON-LD | Parse JSON-LD | Automated | Crawl (no key) |
| HowTo schema | Steps with name, text, image | Parse JSON-LD | Automated | Crawl (no key) |
| Article schema | headline, author, datePublished, dateModified, publisher | Parse JSON-LD | Automated | Crawl (no key) |
| Organization schema | name, url, logo, sameAs (socials, Wikidata) | Parse JSON-LD | Automated | Crawl (no key) |
| Product / Offer schema | name, description, price, availability, aggregateRating | Parse JSON-LD | Automated | Crawl (no key) |
| SpeakableSpecification (NEW) | Important passages marked for voice/AI | Parse JSON-LD | Automated | Crawl (no key) |
| Dataset schema (NEW) | For research/data pages | Parse JSON-LD | Automated | Crawl (no key) |
| Event schema (NEW) | For time-bound content | Parse JSON-LD | Automated | Crawl (no key) |
| ClaimReview schema (NEW) | Fact-check pages | Parse JSON-LD | Automated | Crawl (no key) |

## 05 Entity Clarity

| Parameter | What to check | How it's checked | Auto/Manual | API key / tool |
|---|---|---|---|---|
| In-text definitions | First use of technical terms defined inline / linked | Detect definitions + Gemini | Automated | Crawl + GEMINI_API_KEY |
| Glossary page | Dedicated glossary with anchor links | Detect glossary page | Automated | Crawl (no key) |
| Named entities marked up | People/places/orgs in schema with sameAs to authoritative URIs | Parse JSON-LD sameAs | Automated | Crawl (no key) |
| Disambiguation (NEW) | Clarify ambiguous terms near first use | Gemini ambiguity analysis | Automated | GEMINI_API_KEY |
| Knowledge panel consistency (NEW) | Brand name/description/logo match Knowledge Panel | Query Google Knowledge Graph | Automated | GOOGLE_API_KEY |
| Entity co-occurrence (NEW) | Mention related authoritative entities | Gemini entity analysis | Automated | GEMINI_API_KEY |

## 06 AI-Bot Crawlability

| Parameter | What to check | How it's checked | Auto/Manual | API key / tool |
|---|---|---|---|---|
| GPTBot / ClaudeBot / PerplexityBot | Explicit allow/disallow in robots.txt | Parse robots.txt | Automated | Crawl (no key) |
| Google-Extended | Controls AI Overviews training data | Parse robots.txt | Automated | Crawl (no key) |
| llms.txt | Machine-readable site summary for LLMs | Fetch /llms.txt | Automated | Crawl (no key) |
| CCBot (Common Crawl) (NEW) | Explicit allow/disallow | Parse robots.txt | Automated | Crawl (no key) |
| Applebot-Extended (NEW) | Apple Intelligence crawler directive | Parse robots.txt | Automated | Crawl (no key) |
| Meta AI crawlers (meta-externalagent) (NEW) | Meta AI training/retrieval directive | Parse robots.txt | Automated | Crawl (no key) |
| Crawl rate limits (NEW) | AI bots not throttled to stale content | Parse Crawl-delay + measure response | Automated | Crawl (no key) |
| llms-full.txt (NEW) | Extended page-level metadata file | Fetch /llms-full.txt | Automated | Crawl (no key) |

## 07 AI Quality Scores

| Parameter | What to check | How it's checked | Auto/Manual | API key / tool |
|---|---|---|---|---|
| Clarity score | Writing unambiguous and scannable? | Gemini judgement | Automated | GEMINI_API_KEY |
| Authority score | Expertise, credentials, sourcing signaled? | Gemini judgement | Automated | GEMINI_API_KEY |
| Comprehensiveness | Covers topic fully enough to be self-sufficient? | Gemini judgement | Automated | GEMINI_API_KEY |
| Citation likelihood | Would an AI engine prefer this source? | Gemini judgement | Automated | GEMINI_API_KEY |
| Sample-query self-sufficiency test | Ask 5-10 likely queries; does page alone answer each? | Gemini multi-query test | Automated | GEMINI_API_KEY |
| AI Overview appearance monitoring (NEW) | Cited in Google AI Overviews / SearchGPT / Perplexity? | Run queries; check citations | Automated | SERPAPI_API_KEY + PERPLEXITY_API_KEY + OPENAI_API_KEY |
| Hallucination surface area (NEW) | Reduce ambiguous claims AI might misattribute | Gemini ambiguity/scope analysis | Automated | GEMINI_API_KEY |
| Prompt-align test (NEW) | Simulate LLM summary; accurate and favourable? | Gemini summary simulation | Automated | GEMINI_API_KEY |
| Competing source gap analysis (NEW) | Which sources AI cites for key queries that you lack | Diff citation lists vs target domain | Automated | SERPAPI_API_KEY + PERPLEXITY_API_KEY |

## 08 Multimodal & Voice GEO

| Parameter | What to check | How it's checked | Auto/Manual | API key / tool |
|---|---|---|---|---|
| Image alt text quality | Descriptive alts that match image content | Parse alts + Gemini vision check | Automated | Crawl + GEMINI_API_KEY |
| Video transcripts | Full text transcripts on-page or in schema | Detect transcript/VideoObject | Automated | Crawl (no key) |
| Conversational phrasing | Some content in natural spoken language for voice | Gemini tone analysis | Automated | GEMINI_API_KEY |
| Featured snippet shape | Match Google's voice/AI format: paragraph, list, or table | Detect content shape + Gemini | Automated | Crawl + GEMINI_API_KEY |
| SpeakableSpecification (voice) | Passages marked for text-to-speech | Parse JSON-LD | Automated | Crawl (no key) |

---

# Part 3 - GA4 & Search Console provisioning (connected mode)

The 6 first-party SEO parameters are measured when the audited domain is a **connected property** (listed in `backend/connected_properties.json`) and Google credentials have access. GA4 and GSC only return data for properties the owner controls and has authorised; for non-connected domains these 6 fall back to Manual.

**Roles:** The **tool operator** creates one Google Cloud project (APIs, OAuth app, PageSpeed API key). The **site owner** owns GSC/GA4 and completes a one-time OAuth sign-in. See `Connected_Mode_Tool_Operator_Guide.pdf` and `Connected_Mode_Site_Owner_Guide.pdf`.

## Authentication (OAuth CLI — recommended)

Search Console often rejects service-account emails in the UI. The primary path is a **one-time browser sign-in** with the Google account that owns GSC/GA4:

| File | Purpose |
|---|---|
| `secrets/google-oauth-client.json` | Desktop OAuth client JSON from Google Cloud Console |
| `secrets/google-oauth-token.json` | Refresh token saved by `python scripts/google_auth.py` |
| `backend/connected_properties.json` | Domain → `{ gsc_site_url, ga4_property_id }` registry |

Optional `.env` overrides: `GOOGLE_OAUTH_CLIENT_SECRETS`, `GOOGLE_OAUTH_TOKEN_PATH`.

**Google Cloud setup** (tool operator's project — one project serves all connected sites):

1. Create a Google Cloud project (operator account).
2. Enable APIs: **Search Console API**, Google Analytics **Data** API, Google Analytics **Admin** API (Admin API lists GA4 Property IDs in the auth script), **PageSpeed Insights API** (for Core Web Vitals; uses `GOOGLE_API_KEY`, not OAuth).
3. OAuth consent screen: External; scopes `https://www.googleapis.com/auth/webmasters.readonly` and `https://www.googleapis.com/auth/analytics.readonly`. Add test users while app is in Testing mode.
4. Credentials → OAuth client ID → **Desktop app** → download JSON → `secrets/google-oauth-client.json`.
5. Credentials → **API key** → restrict to PageSpeed Insights API → set `GOOGLE_API_KEY` in `.env`.

**Run the auth script** (from the `backend` folder):

```bash
cd backend && source .venv/bin/activate
python scripts/google_auth.py              # one-time browser sign-in
python scripts/google_auth.py --list-only  # re-list GSC/GA4 without browser
```

If your shell is already in `backend`, omit the `cd backend &&` prefix.

The script prints GSC site URLs and numeric GA4 Property IDs. Copy the exact values into `connected_properties.json`, restart the backend, and re-run an audit.

**Credential priority at audit time:** OAuth token file (`secrets/google-oauth-token.json`) → service account JSON (`GOOGLE_APPLICATION_CREDENTIALS`). OAuth wins when both exist.

**Adding another website:** Do not create a new Cloud project. Add a row to `connected_properties.json` and sign in with a Google account that has access to that site's GSC/GA4 (re-run `google_auth.py` if the owner account differs).

## Authentication (service account — optional / agency)

When GSC accepts a service-account email, set `GOOGLE_APPLICATION_CREDENTIALS` to the JSON key path. The site owner adds that email in GSC (user) and GA4 (Viewer). Same `connected_properties.json` registry applies. OAuth takes priority when `google-oauth-token.json` exists. Not covered in the Connected Mode setup PDFs (OAuth-only).

## What is measured once GA4 + GSC are connected

| Parameter (was Manual when not connected) | Source | API method | Data returned |
|---|---|---|---|
| Click-through rate (CTR) | GSC | searchanalytics.query | clicks, impressions, ctr, average position (per page); **Not Meeting** when connected but 0 impressions |
| Sitemap submission status | GSC | sitemaps.list | submitted paths, errors, warnings; **Not Meeting** when 0 sitemaps, **Partial** when errors |
| Log file analysis (crawl frequency) | GSC | urlInspection.index.inspect | lastCrawlTime, coverageState, verdict, pageFetchState, robotsTxtState; **Partial** when crawled but not indexed |
| Dwell time / scroll depth | GA4 | runReport (28daysAgo–yesterday, pagePath filter) | averageSessionDuration, bounceRate, engagementRate (per pagePath) |
| Bounce rate | GA4 | runReport | bounceRate (per page) |
| Pogo-sticking risk | GA4 + GSC | runReport + derived | low engagementRate when GA4 data exists |

## First-party rating outcomes (connected mode)

| Outcome | Rating | Counts in score? | When |
|---|---|---|---|
| API success + pass/fail logic | Meeting / Partial / Not Meeting | Yes | Normal path (e.g. CTR with impressions, sitemap submitted cleanly, URL indexed and crawled) |
| Sitemap: 0 registered in GSC | Not Meeting | Yes | Connected, sitemaps.list succeeded |
| Sitemap: submitted with GSC errors | Partial | Yes | Connected, at least one sitemap path has errors |
| CTR: 0 GSC impressions for page | Not Meeting | Yes | Connected, searchanalytics succeeded but no rows |
| Log file: crawled, not indexed | Partial | Yes | URL Inspection returned crawl data but verdict/coverage not indexed |
| URL Inspection empty | Not Measured | No | Connected but Google has not crawled/indexed the URL yet |
| API call failed after retries | Not Measured | No | GSC/GA4 network or auth error (`first_party_empty`) |
| Domain not connected | Manual | No | Missing from `connected_properties.json` or no credentials |
| GA4 connected but no sessions | Manual | No | GA4 engagement rows until runReport returns a row for the page path |

## What stays Manual even with GA4 + GSC

| Parameter | Why it stays manual |
|---|---|
| Backlink profile | GSC Links report has no API |
| Referring domain count | GSC Links report has no API |
| Competitor link gap | Needs off-site link index; competitor data never in your GSC |
| Brand mentions (unlinked) | Not exposed by GA4/GSC |
| Google Business Profile / NAP cross-directory | Needs Business Profile / Places + directory data |

## Provisioning flow (one-time setup)

[[FLOW:auth]]

## How the tool decides per audit

[[FLOW:connected]]

## Connected-property registry

The orchestrator reads `backend/connected_properties.json` at audit time. Host is normalised (lowercase, `www.` stripped). Example:

```json
{
  "example.com": {
    "gsc_site_url": "https://www.example.com/",
    "ga4_property_id": "123456789"
  }
}
```

`gsc_site_url` must match the GSC property URL exactly (including trailing slash). `ga4_property_id` is the numeric Property ID from GA4 Admin → Property settings (not the `G-XXXXXXXX` Measurement ID).

For a multi-tenant product this mapping is collected via an onboarding form and stored in a database; the lookup logic is identical.

## GSC client behaviour (`GscClient` in `app/clients.py`)

- All GSC calls return a structured `GscApiResult` (`ok`, `data`, `error`) instead of raising to agents.
- **Retries:** up to 3 attempts with backoff (0.5s, 1s, 2s) on transient failures; cached API client is reset between attempts.
- **Concurrency:** an `asyncio.Lock` serialises GSC calls within one audit (sitemap, CTR, URL Inspection) because the Google API client is not safe for parallel `execute()` on a shared connection.
- **URL variants:** Search Analytics and URL Inspection try common URL forms (with/without trailing slash, www vs non-www) before returning empty data.
- **Search Analytics:** date range 2020–2030, `dataState=final`, page dimension filter.

## Implementation modules

| Module | Role |
|---|---|
| `app/google_auth.py` | Load OAuth token or service account; refresh expired tokens |
| `scripts/google_auth.py` | One-time CLI sign-in; `--list-only` to re-list properties |
| `app/clients.py` (`GscClient`, `Ga4Client`, `GscApiResult`) | GSC sitemaps / searchanalytics / urlInspection; GA4 runReport; PSI via `GOOGLE_API_KEY` |
| `app/agents/seo_agents.py` | `_sitemap_gsc`, `_log_analysis`, `_ctr_row` — connected-mode First-party logic |
| `app/agents/base.py` | `scored`, `manual`, `first_party_empty`, `not_measured` result factories |
| `app/orchestrator.py` (`ConnectedRegistry`) | Domain lookup at audit time |
| `backend/connected_properties.json` | Static registry (JSON file today) |
| `generate_connected_guide_pdf.py` | Professional PDFs for site-owner and tool-operator setup guides |

## Limits and behaviour

| Topic | Detail |
|---|---|
| Data latency (GSC) | Search performance data has a 2-3 day delay; the tool requests `dataState=final` |
| CTR with 0 impressions | Connected + GSC API success but no rows for the page → **Not Meeting** (scored), with recommendation to improve indexing/traffic |
| GSC/GA4 API failure | After retries, parameter is **Not Measured** (`first_party_empty`) with error detail in the report |
| Empty URL Inspection | Connected but no inspection result → **Not Measured** until Googlebot crawls the URL |
| GA4 without sessions | Dwell / bounce / pogo rows stay **Manual** until GA4 returns engagement data |
| PageSpeed Insights | Requires PageSpeed Insights API enabled in the tool operator's Cloud project and `GOOGLE_API_KEY` in `.env`; otherwise CWV/PSI parameters are **Not Measured** |
| URL Inspection quota | 2,000 inspections per property per day; the tool inspects the audited URL only |
| Privacy | Read-only scopes (`webmasters.readonly` + `analytics.readonly`); owner can revoke OAuth access or remove users at any time |
| Fallback | If a domain is not in the registry (or credentials missing), the 6 first-party parameters revert to Manual and are excluded from the score |

---

# Part 4 - APIs and keys summary

| Capability | API / source | .env key | Status |
|---|---|---|---|
| AI judgement (SEO + GEO) | Gemini (google-genai) | GEMINI_API_KEY | Present |
| ChatGPT-style citation check | OpenAI | OPENAI_API_KEY | Present |
| Performance + entity | PageSpeed Insights + Knowledge Graph | GOOGLE_API_KEY (enable PageSpeed Insights API in tool operator GCP project) | Required for CWV/PSI rows |
| Web search + press mentions | Serper | SERPER_API_KEY | Present |
| Perplexity citations | Perplexity Sonar | PERPLEXITY_API_KEY | Present |
| Google AI Overview citations | SerpApi | SERPAPI_API_KEY | Present |
| Crawl/render + extraction | Firecrawl | FIRECRAWL_API_KEY | Present |
| Brand mentions on X | X API | X_BEARER_TOKEN | Present |
| First-party analytics (GA4 + GSC) | Search Console + GA4 Data API (OAuth CLI primary) | `secrets/google-oauth-token.json` (+ optional `GOOGLE_APPLICATION_CREDENTIALS` fallback) | Per connected domain |
| Entity graph | Wikidata SPARQL + Wikipedia REST | none | No key needed |

All other API keys are read from `.env` at startup via `app/config.py`. PageSpeed and first-party Google access are independent: PSI uses `GOOGLE_API_KEY`; GSC/GA4 use OAuth (or service-account fallback).
