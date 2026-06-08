# SEO & GEO Parameter Reference (Automation Plan)

Complete parameter checklist for Search Engine Optimisation (SEO) and Generative Engine Optimisation (GEO), showing for each parameter: what to check, how the tool checks it, whether it is Automated or Manual, and the API key / tool planned.

Policy:
- SEO is crawl-based. Parameters that cannot be determined from the site itself are marked Manual and excluded from the SEO score.
- **Connected mode:** six first-party SEO parameters (CTR, sitemap GSC submission, log/crawl analysis, dwell time, bounce rate, pogo-sticking) become **Measured** when the domain is in `backend/connected_properties.json` and OAuth or service-account credentials have API access. If connected but a specific API returns no rows for the page, that parameter stays Manual until data exists.
- GEO is fully automated using external APIs plus Gemini. GEO has no Manual parameters.

Detection method legend:
- Crawl = httpx + Playwright/Firecrawl + BeautifulSoup parsing of the page, headers, robots/sitemap/llms.txt
- PSI = Google PageSpeed Insights API (Lighthouse + lab Core Web Vitals + CrUX field data)
- LLM = Gemini judgement
- External = third-party API (GEO only)
- First-party = GA4 / Search Console via OAuth token or service account (connected domains only)
- Manual = requires data the tool cannot obtain (site ownership / off-site data); shown but not scored

API keys referenced (from project .env):
- GEMINI_API_KEY (present), OPENAI_API_KEY (present), GOOGLE_API_KEY (present - PageSpeed + Knowledge Graph)
- SERPER_API_KEY (present), PERPLEXITY_API_KEY (present), FIRECRAWL_API_KEY (present), X_BEARER_TOKEN (present)
- SERPAPI_API_KEY (present - Google AI Overview citations)
- OAuth (connected mode): `secrets/google-oauth-client.json` + `secrets/google-oauth-token.json` (optional `GOOGLE_OAUTH_*` in `.env`)
- Service account (optional fallback): `GOOGLE_APPLICATION_CREDENTIALS`
- Wikidata SPARQL and Wikipedia REST API need no key

---

# Part 1 - SEO Parameters

## 01 Crawlability & Indexability

| Parameter | What to check | How it's checked | Auto/Manual | API key / tool |
|---|---|---|---|---|
| robots.txt | Correct disallow rules; no accidental crawl blocks on key pages | Fetch and parse /robots.txt | Automated | Crawl (no key) |
| sitemap.xml | Present; no 4xx/5xx URLs; lastmod populated | Fetch sitemap, validate URLs + status | Automated | Crawl (no key) |
| sitemap GSC-submission status | Submitted to Google Search Console | GSC sitemaps.list/get (connected), else Manual | Connected (GSC) | OAuth token or GOOGLE_APPLICATION_CREDENTIALS |
| Meta robots | No unintended noindex/nofollow; check X-Robots-Tag header | Parse meta tag + response headers | Automated | Crawl (no key) |
| Canonical tags | Self-referencing; no conflicting/chained canonicals | Parse <link rel=canonical> | Automated | Crawl (no key) |
| HTTP status & redirects | No redirect chains > 1 hop; 301 not 302 for permanent | Follow + record redirect chain | Automated | Crawl (no key) |
| Crawl depth (NEW) | Key pages reachable within 3 clicks from homepage | Limited internal crawl + depth graph | Automated | Crawl (no key) |
| Pagination handling (NEW) | rel=next/prev or infinite-scroll pattern; no thin dupes | Parse pagination markup | Automated | Crawl (no key) |
| Log file analysis (NEW) | Googlebot visit frequency; crawl budget waste | GSC urlInspection (connected), else Manual | Connected (GSC) | OAuth token or GOOGLE_APPLICATION_CREDENTIALS |
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
| Click-through rate (CTR) | GSC CTR vs position benchmark | GSC searchanalytics.query (connected + data), else Manual | Connected (GSC) | OAuth token or GOOGLE_APPLICATION_CREDENTIALS |
| Dwell time / scroll depth | GA4 engagement proxy | GA4 runReport (connected + data), else Manual | Connected (GA4) | OAuth token or GOOGLE_APPLICATION_CREDENTIALS |
| Bounce rate in context | High bounce interpreted by page type | GA4 runReport bounceRate (connected + data), else Manual | Connected (GA4) | OAuth token or GOOGLE_APPLICATION_CREDENTIALS |
| Pogo-sticking risk | Users returning to SERP quickly = intent mismatch | GA4 + GSC derived (connected + data), else Manual | Connected (GA4+GSC) | OAuth token or GOOGLE_APPLICATION_CREDENTIALS |
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

## Summary
- SEO: 11 parameters are Manual when a domain is **not connected** (excluded from score): Log file analysis, sitemap GSC-submission status, Backlink profile, Referring domain count, Brand mentions, Competitor link gap, NAP cross-directory, Google Business Profile, CTR, Dwell time/scroll depth, Bounce rate, Pogo-sticking. When connected via OAuth/service account, **6 of these become Measured** (Manual count drops to 5 off-page/GBP params).
- GEO: 0 Manual parameters - fully automated via Crawl + Gemini + External APIs.
- Connected mode setup is documented separately: `Connected_Mode_Site_Owner_Guide.pdf` and `Connected_Mode_Tool_Operator_Guide.pdf` (regenerate from markdown via `generate_connected_guide_pdf.py`).
