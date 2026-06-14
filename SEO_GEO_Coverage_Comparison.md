# SEO & GEO Auditor - Coverage Comparison

Generated: June 9, 2026

Compares three reference PDFs against the current SEO_GEO_Auditor application (127 parameters across 15 categories). The app audits a single URL per run with a shallow internal crawl (~25 pages). Semrush and baseline PDFs report whole-site or property-level aggregates.

Legend: **Yes** = implemented and auto-calculated (Connected Mode counts for first-party GA4/GSC). **Partial** = related check exists but differs in scope, granularity, or bot name. **No** = not implemented.

---

## Executive Summary

| Section | Source PDF | Total checks | Yes | Partial | No |
|---|---|---|---|---|---|
| 1 | Performance Baseline (GA4/GSC/CWV) | 23 | 3 | 6 | 14 |
| 2 | Semrush Full Site Audit | 96 | 35 | 26 | 35 |
| 3 | Semrush AI Search Overview | 13 | 2 | 5 | 6 |
| **Total** | | **132** | **40** | **37** | **55** |

Top gaps: property-level analytics dashboard (users, channels, keywords, device/country), full-site crawl inventory, expanded AI bot user-agent matrix (ChatGPT-User, OAI-SearchBot, etc.), time-series trend charts, form/exit-page reporting.

---

## Section 1 - Performance Baseline PDF

Source: Performance_Baseline-Traffic__Engagement__SEO___Web_Vitals___Feb_20__20-21st_May_2026.pdf

| Parameter | Calculated in SEO_GEO_Auditor? | App parameter / notes |
|---|---|---|
| Engagement Rate | Partial | Used inside Pogo-sticking risk (UxAgent); not a standalone KPI |
| Total Users | No | GA4 client queries per-page metrics only; no property-level user counts |
| New Users | No | Not queried from GA4 |
| Average Session Duration | Partial | Dwell time / scroll depth via GA4 when Connected Mode |
| Bounce Rate | Partial | Bounce rate in context via GA4 when Connected Mode |
| Clicks by Device (Mobile/Desktop/Tablet) | No | GSC device dimension not implemented |
| Clicks by Country | No | GSC country dimension not implemented |
| Organic traffic trend (top pages traffic %) | No | No site-wide traffic ranking dashboard |
| Traffic by source (organic/direct/referral) | No | No GA4 channel-group reporting |
| Session source breakdown (google/bing/yahoo/etc.) | No | Not implemented |
| Organic Social traffic | No | Not implemented |
| Session primary channel group | No | Not implemented |
| Top ranking keywords (CTR, position, clicks, impressions) | Partial | Page-level GSC data in Click-through rate (CTR) only; no keyword top-20 list |
| Bounce rate trend (time series) | No | Point-in-time only; no charts |
| Average engagement time trend (time series) | No | Point-in-time only; no charts |
| Pages per session | No | Not in GA4 query |
| Mobile vs Desktop traffic split | Partial | Mobile vs desktop delta scores CWV gap, not traffic/users split |
| LCP (Core Web Vitals) | Yes | CoreWebVitalsAgent via PageSpeed Insights |
| CLS (Core Web Vitals) | Yes | CoreWebVitalsAgent via PageSpeed Insights |
| INP (Core Web Vitals) | Yes | CoreWebVitalsAgent via PageSpeed Insights |
| Page load speed - Desktop | Partial | Lighthouse performance score + LCP/TTFB; not dedicated load-speed KPI |
| Page load speed - Mobile | Partial | Same PSI mobile run; not dedicated load-speed KPI |
| Form submissions by type | No | No GA4 event/conversion tracking |
| Top exit pages | No | Not implemented |

Section 1 totals: Yes 3, Partial 6, No 14

---

## Section 2 - Semrush Full Site Audit PDF

Source: Semrush-Full_Site_Audit_Report-optiorx_com-6th_Feb_2026.pdf

### Errors

| Parameter | Calculated in SEO_GEO_Auditor? | App parameter / notes |
|---|---|---|
| Pages returned 5XX status code | Partial | Broken links + HTTP status check sampled links; no site-wide 5XX inventory |
| Pages returned 4XX status code | Partial | Broken links samples 4xx; no site-wide 4XX page count |
| Pages don't have title tags | Yes | Title tag (CrawlabilityAgent / OnPageAgent) |
| Issues with duplicate title tags | Partial | Title tag checks current page only; no cross-site duplicate detection |
| Pages have duplicate content issues | Partial | Duplicate content checks canonical on page; no near-duplicate fingerprinting |
| Internal links are broken | Yes | Broken links (TechnicalAgent crawl sample) |
| Pages couldn't be crawled | No | No crawl-failure taxonomy or site-wide inventory |
| Pages couldn't be crawled (DNS resolution issues) | No | Not implemented |
| Pages couldn't be crawled (incorrect URL formats) | Partial | URL structure checks current URL; no crawl URL-format audit |
| Internal images are broken | No | Image alt coverage only; no broken-image status checks |
| Pages have duplicate meta descriptions | Partial | Meta description on current page; no cross-site duplicate detection |
| Robots.txt file has format errors | Yes | robots.txt (CrawlabilityAgent) |
| sitemap.xml files have format errors | Yes | sitemap.xml (CrawlabilityAgent) |
| Incorrect pages found in sitemap.xml | Partial | sitemap.xml validates existence and lastmod; not full URL validation |
| Pages have a WWW resolve issue | No | Not implemented |
| This page has no viewport tag | Yes | Mobile viewport (TechnicalAgent) |
| Pages have too large HTML size | No | Not implemented |
| AMP pages have no canonical tag | Partial | AMP / Web Stories checks AMP presence; optional informational |
| Issues with hreflang values | Yes | hreflang (TechnicalAgent) |
| hreflang conflicts within page source code | Partial | hreflang checks x-default; not full conflict detection |
| Issues with incorrect hreflang links | Partial | hreflang basic validation only |
| Non-secure pages | Yes | HTTPS / SSL (TechnicalAgent) |
| Issues with expiring or expired certificate | Partial | HTTPS / SSL checks tls_ok; not certificate expiry date |
| Issues with old security protocol | No | Not implemented |
| Issues with incorrect certificate name | No | Not implemented |
| Issues with mixed content | Yes | HTTPS / SSL checks mixed content |
| No redirect or canonical to HTTPS homepage from HTTP | Partial | HTTPS / SSL on audited URL; not HTTP-homepage-specific check |
| Pages with a broken canonical link | Yes | Canonical tags (CrawlabilityAgent) |
| Pages have multiple canonical URLs | Partial | Canonical tags checks single canonical presence |
| Pages have a meta refresh tag | No | Not implemented |
| Issues with broken internal JavaScript and CSS files | No | Not implemented |
| Subdomains don't support secure encryption algorithms | No | Not implemented |
| sitemap.xml files are too large | No | Not implemented |
| Links couldn't be crawled (incorrect URL formats) | No | Not implemented |
| Structured data items are invalid | Yes | Schema.org JSON-LD + Rich result eligibility |
| Pages are missing the viewport width value | Yes | Mobile viewport (width=device-width check) |
| Pages have slow load speed | Partial | LCP, TTFB, Lighthouse scores via PSI; not Semrush load-speed threshold |

### Warnings

| Parameter | Calculated in SEO_GEO_Auditor? | App parameter / notes |
|---|---|---|
| External links are broken | Partial | Broken links focuses on crawl sample; external monitoring limited |
| External images are broken | No | Not implemented |
| Links on HTTPS pages lead to HTTP page | Partial | HTTPS / SSL mixed-content check partially covers |
| Pages don't have enough text within title tags | Yes | Title tag (50-60 char heuristic) |
| Pages have too much text within title tags | Yes | Title tag length check |
| Pages don't have an h1 heading | Yes | Heading hierarchy (single H1) |
| Pages have duplicate H1 and title tags | No | Not implemented as separate check |
| Pages don't have meta descriptions | Yes | Meta description (OnPageAgent) |
| Pages have too many on-page links | No | Not implemented |
| URLs with a temporary redirect | Partial | HTTP status & redirects flags 302; not site-wide redirect inventory |
| Images don't have alt attributes | Yes | Image alt coverage (OnPageAgent) |
| Pages have low text-HTML ratio | No | Not implemented |
| Pages have too many parameters in their URLs | Yes | URL structure (<=2 query params) |
| Pages have no hreflang and lang attributes | Partial | hreflang when present; lang attribute not checked |
| Pages don't have character encoding declared | No | Not implemented |
| Pages don't have doctype declared | No | Not implemented |
| Pages have a low word count | Yes | Word count / content depth (OnPageAgent) |
| Pages have incompatible plugin content | No | Not implemented |
| Pages contain frames | No | Not implemented |
| Pages have underscores in the URL | Yes | URL structure (no underscores in path) |
| Outgoing internal links contain nofollow attribute | No | Not implemented |
| Sitemap.xml not indicated in robots.txt | Partial | robots.txt + sitemap.xml checked separately; not cross-reference |
| Sitemap.xml not found | Yes | sitemap.xml (CrawlabilityAgent) |
| Homepage does not use HTTPS encryption | Partial | HTTPS / SSL on any audited URL; not homepage-specific |
| Subdomains don't support SNI | No | Not implemented |
| HTTP URLs in sitemap.xml for HTTPS site | No | Not implemented |
| Uncompressed pages | No | Not implemented |
| Issues with blocked internal resources in robots.txt | No | Not implemented |
| Issues with uncompressed JavaScript and CSS files | Partial | PSI audits partially cover resource optimization |
| Issues with uncached JavaScript and CSS files | No | Not implemented |
| Pages have JS/CSS total size too large | Partial | Third-party script impact + render-blocking via PSI |
| Pages use too many JavaScript and CSS files | No | Not implemented |
| Issues with unminified JavaScript and CSS files | Partial | PSI best-practices audits partially cover |
| Link URLs are too long | Partial | URL structure checks page URL <115 chars; not link URL length |

### Notices

| Parameter | Calculated in SEO_GEO_Auditor? | App parameter / notes |
|---|---|---|
| Pages have more than one H1 tag | Yes | Heading hierarchy (exactly one H1) |
| Llms.txt not found | Yes | llms.txt (AiBotCrawlabilityAgent - GEO) |
| Pages are blocked from crawling | Yes | Meta robots + robots.txt (CrawlabilityAgent) |
| Page URLs are longer than 200 characters | Partial | URL structure threshold is 115 chars on current URL |
| Outgoing external links contain nofollow attributes | No | Not implemented |
| Robots.txt not found | Yes | robots.txt (CrawlabilityAgent) |
| Pages have hreflang language mismatch issues | Partial | hreflang basic check; not full language mismatch |
| Subdomains don't support HSTS | Partial | HTTPS / SSL checks HSTS header on response |
| Orphaned pages in Google Analytics | No | Not implemented |
| Orphaned pages in sitemaps | No | Not implemented |
| Pages blocked by X-Robots-Tag: noindex HTTP header | Yes | Meta robots checks X-Robots-Tag header |
| Issues with blocked external resources in robots.txt | No | Not implemented |
| Issues with broken external JavaScript and CSS files | No | Not implemented |
| Pages need more than 3 clicks to be reached | Yes | Crawl depth (max internal depth <=3) |
| Pages have only one incoming internal link | Partial | Internal links + anchor text; no orphan incoming-link inventory |
| URLs with a permanent redirect | Partial | HTTP status & redirects; not site-wide 301 inventory |
| Resources are formatted as page link | No | Not implemented |
| Links on this page have no anchor text | Partial | Internal links + anchor text (descriptive % heuristic) |
| Links have non-descriptive anchor text | Partial | Internal links + anchor text (descriptive % heuristic) |
| Links to external pages returned 403 HTTP status | No | Not implemented |
| Llms.txt has formatting issues | Partial | llms.txt checks existence only; no format validation |
| Pages contain too much content | No | Not implemented |
| Pages have outdated content | Partial | Content freshness signals (date regex heuristic) |
| Pages have low semantic HTML usage | Yes | Semantic HTML (ExtractabilityAgent - GEO) |
| Pages require content optimization | Partial | LLM-based depth/keyword checks; no Semrush optimization score |

Section 2 totals: Yes 35, Partial 26, No 35

---

## Section 3 - Semrush AI Search Overview PDF

Source: Semrush-Site_Audit__Overview-optiorx_com-9th_Jun_2026.pdf

| Parameter | Calculated in SEO_GEO_Auditor? | App parameter / notes |
|---|---|---|
| Site Health score (percentage) | Partial | Category + final letter grade; different methodology than Semrush |
| AI Search Health score (percentage) | Partial | GEO report final score; not Semrush AI Search Health model |
| Crawled pages stats (Blocked/Redirect/Broken/Healthy) | No | Single-page audit; no site-wide page inventory |
| Pages blocked from AI search (aggregate %) | Partial | AiBotCrawlabilityAgent per-page robots checks; no site-wide % |
| ChatGPT-User bot blocking | No | App checks GPTBot, not ChatGPT-User |
| OAI-SearchBot bot blocking | No | Not in bot user-agent list |
| Googlebot blocking | No | Not checked (only Google-Extended) |
| Google-Extended bot blocking | Yes | AiBotCrawlabilityAgent (GEO) |
| PerplexityBot bot blocking | Yes | Grouped in GPTBot / ClaudeBot / PerplexityBot |
| Perplexity-User bot blocking | No | Not in bot user-agent list |
| Claude-User bot blocking | No | App checks ClaudeBot, not Claude-User |
| Claude-SearchBot bot blocking | No | App checks ClaudeBot, not Claude-SearchBot |
| Top Issues list (Errors/Warnings dashboard) | Partial | Report lists failing parameters; not Semrush-style issue dashboard |

Section 3 totals: Yes 2, Partial 5, No 6

---

## Appendix - Summary Counts

| Section | Yes | Partial | No | Total |
|---|---|---|---|---|
| 1 - Performance Baseline | 3 | 6 | 14 | 23 |
| 2 - Semrush Full Site Audit | 35 | 26 | 35 | 96 |
| 3 - Semrush AI Search Overview | 2 | 5 | 6 | 13 |
| **Grand total** | **40** | **37** | **55** | **132** |

Status key: Yes = auto-calculated (Connected Mode for GA4/GSC). Partial = related check with scope/threshold/bot-name differences. No = not implemented.

SEO_GEO_Auditor implements 127 native parameters in backend/app/agents/ (67 SEO + 60 GEO). This comparison maps external PDF metrics to that implementation.
