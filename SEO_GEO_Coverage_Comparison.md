# SEO & GEO Auditor - Coverage Comparison

Generated: June 9, 2026

Compares three reference PDFs against the current SEO_GEO_Auditor application (127 parameters across 15 categories).

**Column guide**
- **In App?** - Yes / Partial / No (implemented today)
- **How to measure / Is current method best?** - For **No** or **Partial**: how to implement the check (source + API/detail). For **Yes**: whether the app's current approach is the best method.
- **Notes** - App parameter name or extra context

**Source key:** Crawl = httpx/Playwright/Firecrawl (free) | GSC = Search Console API (free, OAuth) | GA4 = Analytics Data API (free, OAuth) | PSI = PageSpeed Insights (free, API key) | LLM = Gemini | Paid = Semrush/Ahrefs (optional)

---

## Measurement Plan Overview

| Source | Cost | Use for |
|---|---|---|
| Crawl | Free | HTML, robots, sitemap, links, TLS, schema, full-site inventory |
| GSC | Free (OAuth) | Clicks, impressions, CTR, keywords, device, country |
| GA4 | Free (OAuth) | Users, engagement, channels, sources, exit pages, events |
| PSI | Free (API key) | LCP, CLS, INP, Lighthouse, CrUX |
| LLM | Low cost | Content quality, optimization scoring |
| Paid | Subscription | Organic traffic % estimates only (2 metrics); optional |

---

## Executive Summary

| Section | Source PDF | Total | Yes | Partial | No |
|---|---|---|---|---|---|
| 1 | Performance Baseline | 23 | 3 | 6 | 14 |
| 2 | Semrush Full Site Audit | 96 | 35 | 26 | 35 |
| 3 | Semrush AI Search Overview | 13 | 2 | 5 | 6 |
| **Total** | | **132** | **40** | **37** | **55** |

---

## Section 1 - Performance Baseline PDF
Source: Performance_Baseline-Traffic__Engagement__SEO___Web_Vitals___Feb_20__20-21st_May_2026.pdf

| Parameter | In App? | How to measure / Is current method best? | Notes |
|---|---|---|---|
| Engagement Rate | Partial | Extend GA4 - runReport metric engagementRate as standalone KPI (property or page level). Current: embedded in Pogo-sticking risk only. | UxAgent |
| Total Users | No | Add via GA4: runReport metric totalUsers at property level with dateRange | Not in Ga4Client |
| New Users | No | Add via GA4: runReport metric newUsers at property level | Not in Ga4Client |
| Average Session Duration | Partial | Extend GA4 - already available via Connected Mode - expose as standalone metric. Current: Dwell time / scroll depth per page. | UxAgent |
| Bounce Rate | Partial | Extend GA4 - already available via Connected Mode - expose as standalone metric. Current: Bounce rate in context per page. | UxAgent |
| Clicks by Device (Mobile/Desktop/Tablet) | No | Add via GSC: searchAnalytics.query with dimension device | Not implemented |
| Clicks by Country | No | Add via GSC: searchAnalytics.query with dimension country | Not implemented |
| Organic traffic trend (top pages traffic %) | No | Add via GSC + Paid: GSC searchAnalytics with page dimension for clicks; Paid (Semrush) only for traffic % estimates | No dashboard |
| Traffic by source (organic/direct/referral) | No | Add via GA4: runReport with dimension sessionDefaultChannelGroup | Not implemented |
| Session source breakdown (google/bing/yahoo/etc.) | No | Add via GA4: runReport with dimension sessionSource, sorted by users | Not implemented |
| Organic Social traffic | No | Add via GA4: runReport filter sessionDefaultChannelGroup = Organic Social | Not implemented |
| Session primary channel group | No | Add via GA4: runReport with dimension sessionPrimaryChannelGroup | Not implemented |
| Top ranking keywords (CTR, position, clicks, impressions) | Partial | Extend GSC - searchAnalytics.query with query dimension, top 20 by clicks. Current: page-level CTR only via Click-through rate. | UxAgent / GSC |
| Bounce rate trend (time series) | No | Add via GA4: runReport with date dimension + bounceRate metric over 28/90 days | No time series |
| Average engagement time trend (time series) | No | Add via GA4: runReport with date dimension + averageSessionDuration | No time series |
| Pages per session | No | Add via GA4: runReport metric screenPageViewsPerSession or views/sessions | Not in Ga4Client |
| Mobile vs Desktop traffic split | Partial | Extend GA4 - runReport with deviceCategory dimension for users/sessions. Current: Mobile vs desktop delta compares CWV only, not traffic. | CoreWebVitalsAgent |
| LCP (Core Web Vitals) | Yes | Current: PSI lab + CrUX via CoreWebVitalsAgent. Best method: Yes - PSI is the Google-standard source for LCP | CoreWebVitalsAgent |
| CLS (Core Web Vitals) | Yes | Current: PSI lab + CrUX via CoreWebVitalsAgent. Best method: Yes - PSI is the standard source for CLS | CoreWebVitalsAgent |
| INP (Core Web Vitals) | Yes | Current: PSI CrUX field INP with TBT lab fallback. Best method: Yes - PSI/CrUX is the correct source for INP | CoreWebVitalsAgent |
| Page load speed - Desktop | Partial | Extend PSI - expose Lighthouse performance score + LCP as dedicated load-speed KPI. Current: LCP/TTFB/Lighthouse exist but not labeled as load speed. | CoreWebVitalsAgent |
| Page load speed - Mobile | Partial | Extend PSI - same as desktop using strategy=mobile. Current: PSI mobile run exists. | CoreWebVitalsAgent |
| Form submissions by type | No | Add via GA4: runReport with eventName dimension filtered to form_submit or custom conversion events | Not implemented |
| Top exit pages | No | Add via GA4: runReport pagePath + sessions or exitRate metric, sorted descending | Not implemented |
Section 1 totals: Yes 3, Partial 6, No 14

---

## Section 2 - Semrush Full Site Audit PDF
Source: Semrush-Full_Site_Audit_Report-optiorx_com-6th_Feb_2026.pdf

### Errors

| Parameter | In App? | How to measure / Is current method best? | Notes |
|---|---|---|---|
| Pages returned 5XX status code | Partial | Extend Crawl - full-site crawl: HEAD/GET every sitemap URL and record status >= 500. Current: Broken links samples ~25 pages only. | Broken links / HTTP status |
| Pages returned 4XX status code | Partial | Extend Crawl - full-site crawl status inventory for all internal URLs. Current: Broken links on crawl sample only. | Broken links |
| Pages don't have title tags | Yes | Current: Crawl parses <title> on audited page. Best method: Yes - Direct HTML parse is the correct method | Title tag |
| Issues with duplicate title tags | Partial | Extend Crawl - hash all titles across full-site crawl and flag duplicates. Current: checks single page title length only. | Title tag |
| Pages have duplicate content issues | Partial | Extend Crawl + LLM - simhash/content fingerprint across crawled pages + canonical check. Current: Duplicate content checks canonical on one page only. | Duplicate content |
| Internal links are broken | Yes | Current: Crawl samples link_status on ~25 pages. Best method: No - Full-site link check is more complete than sample | Broken links |
| Pages couldn't be crawled | No | Add via Crawl: full-site crawl with failure taxonomy: timeout, DNS, robots block, 403 | Not implemented |
| Pages couldn't be crawled (DNS resolution issues) | No | Add via Crawl: socket.getaddrinfo before fetch; record NXDOMAIN failures | Not implemented |
| Pages couldn't be crawled (incorrect URL formats) | Partial | Extend Crawl - validate all sitemap and discovered URLs with urlparse. Current: URL structure checks current URL only. | URL structure |
| Internal images are broken | No | Add via Crawl: HEAD/GET each img src from every crawled page | Image alt only today |
| Pages have duplicate meta descriptions | Partial | Extend Crawl - hash meta descriptions across full-site crawl. Current: Meta description on single page only. | Meta description |
| Robots.txt file has format errors | Yes | Current: Crawl fetches and parses /robots.txt. Best method: Yes - Direct fetch + parse is best | robots.txt |
| sitemap.xml files have format errors | Yes | Current: Crawl fetches and parses sitemap XML. Best method: Yes - Direct fetch + parse is best | sitemap.xml |
| Incorrect pages found in sitemap.xml | Partial | Extend Crawl - fetch each sitemap loc URL and verify status 200. Current: sitemap checks existence and lastmod count only. | sitemap.xml |
| Pages have a WWW resolve issue | No | Add via Crawl: fetch http://www and http://non-www; verify consistent 301 to canonical | Not implemented |
| This page has no viewport tag | Yes | Current: Crawl parses meta viewport. Best method: Yes - HTML parse is best | Mobile viewport |
| Pages have too large HTML size | No | Add via Crawl: measure len(response.content) per page; flag above threshold e.g. 2MB | Not implemented |
| AMP pages have no canonical tag | Partial | Extend Crawl - if AMP detected, require amphtml/canonical pairing. Current: AMP / Web Stories is informational only. | AMP / Web Stories |
| Issues with hreflang values | Yes | Current: Crawl parses hreflang link tags + x-default. Best method: No - Full reciprocity validation needs cross-page crawl | hreflang |
| hreflang conflicts within page source code | Partial | Extend Crawl - detect duplicate hreflang langs and conflicting targets on same page. Current: basic hreflang + x-default check only. | hreflang |
| Issues with incorrect hreflang links | Partial | Extend Crawl - fetch each hreflang href and verify 200 + return hreflang. Current: does not validate target pages today. | hreflang |
| Non-secure pages | Yes | Current: Crawl checks TLS + HTTPS URL. Best method: Yes - Direct TLS/URL check is best | HTTPS / SSL |
| Issues with expiring or expired certificate | Partial | Extend Crawl - read cert notAfter via ssl.get_server_certificate. Current: tls_ok boolean only, no expiry date. | HTTPS / SSL |
| Issues with old security protocol | No | Add via Crawl: TLS handshake probe for minimum TLS 1.2 | Not implemented |
| Issues with incorrect certificate name | No | Add via Crawl: compare cert SAN/CN to hostname via ssl module | Not implemented |
| Issues with mixed content | Yes | Current: Crawl scans page resources for http:// on https pages. Best method: Yes - Resource scan is best | HTTPS / SSL |
| No redirect or canonical to HTTPS homepage from HTTP | Partial | Extend Crawl - explicit fetch http://homepage and assert 301/308 to https. Current: HTTPS check on audited URL only. | HTTPS / SSL |
| Pages with a broken canonical link | Yes | Current: Crawl parses canonical and compares to final URL. Best method: Yes - Parse + self-ref check is best for single page | Canonical tags |
| Pages have multiple canonical URLs | Partial | Extend Crawl - count all link rel=canonical tags; flag if > 1. Current: checks presence and self-ref only. | Canonical tags |
| Pages have a meta refresh tag | No | Add via Crawl: detect meta http-equiv=refresh in HTML | Not implemented |
| Issues with broken internal JavaScript and CSS files | No | Add via Crawl: HEAD/GET every script src and link rel=stylesheet on crawled pages | Not implemented |
| Subdomains don't support secure encryption algorithms | No | Add via Crawl: TLS cipher probe or SSL Labs API (free tier) | Not implemented |
| sitemap.xml files are too large | No | Add via Crawl: count URLs in sitemap; flag if > 50000 | Not implemented |
| Links couldn't be crawled (incorrect URL formats) | No | Add via Crawl: urlparse validation on all discovered href values | Not implemented |
| Structured data items are invalid | Yes | Current: Crawl validates JSON-LD types and required fields heuristically. Best method: No - Google Rich Results Test API would be more authoritative | Schema.org JSON-LD |
| Pages are missing the viewport width value | Yes | Current: Crawl checks width=device-width in viewport meta. Best method: Yes - HTML parse is best | Mobile viewport |
| Pages have slow load speed | Partial | Extend PSI + Crawl - combine PSI LCP/TTFB thresholds with crawl-measured TTFB. Current: PSI metrics exist but no Semrush-style slow-page flag. | CoreWebVitalsAgent |
### Warnings

| Parameter | In App? | How to measure / Is current method best? | Notes |
|---|---|---|---|
| External links are broken | Partial | Extend Crawl - HEAD/GET all external hrefs from full crawl. Current: Broken links focuses on internal sample. | Broken links |
| External images are broken | No | Add via Crawl: HEAD/GET external img src URLs | Not implemented |
| Links on HTTPS pages lead to HTTP page | Partial | Extend Crawl - scan all href/src for http:// on HTTPS pages. Current: mixed content check partially covers. | HTTPS / SSL |
| Pages don't have enough text within title tags | Yes | Current: Crawl title length 50-60 char heuristic. Best method: Yes - Length check is standard | Title tag |
| Pages have too much text within title tags | Yes | Current: Crawl title length check. Best method: Yes - Length check is standard | Title tag |
| Pages don't have an h1 heading | Yes | Current: Crawl heading hierarchy - require exactly one H1. Best method: Yes - HTML parse is best | Heading hierarchy |
| Pages have duplicate H1 and title tags | No | Add via Crawl: string compare normalized h1 text vs title text | Not implemented |
| Pages don't have meta descriptions | Yes | Current: Crawl parses meta description. Best method: Yes - HTML parse is best | Meta description |
| Pages have too many on-page links | No | Add via Crawl: count anchor tags; flag if > threshold e.g. 100 | Not implemented |
| URLs with a temporary redirect | Partial | Extend Crawl - full-site crawl records 302/307 chains. Current: HTTP status flags 302 on single URL only. | HTTP status & redirects |
| Images don't have alt attributes | Yes | Current: Crawl img alt coverage >= 90%. Best method: Yes - HTML parse is best | Image alt coverage |
| Pages have low text-HTML ratio | No | Add via Crawl: ratio visible_text bytes / html bytes; flag low ratio | Not implemented |
| Pages have too many parameters in their URLs | Yes | Current: Crawl URL structure <= 2 query params. Best method: Yes - URL parse is best | URL structure |
| Pages have no hreflang and lang attributes | Partial | Extend Crawl - check html lang attribute in addition to hreflang. Current: hreflang checked when present; lang not checked. | hreflang |
| Pages don't have character encoding declared | No | Add via Crawl: check meta charset or Content-Type charset header | Not implemented |
| Pages don't have doctype declared | No | Add via Crawl: assert HTML starts with <!DOCTYPE | Not implemented |
| Pages have a low word count | Yes | Current: Crawl word count + Gemini depth judgement. Best method: No - Competitive benchmark needs SERP comparison (GSC/LLM) | Word count / content depth |
| Pages have incompatible plugin content | No | Add via Crawl: detect object/embed/applet tags | Not implemented |
| Pages contain frames | No | Add via Crawl: detect frame tags (exclude iframe embeds) | Not implemented |
| Pages have underscores in the URL | Yes | Current: Crawl URL path underscore check. Best method: Yes - URL parse is best | URL structure |
| Outgoing internal links contain nofollow attribute | No | Add via Crawl: parse rel=nofollow on internal anchor tags | Not implemented |
| Sitemap.xml not indicated in robots.txt | Partial | Extend Crawl - parse Sitemap: directive in robots.txt. Current: robots.txt and sitemap checked separately. | robots.txt + sitemap.xml |
| Sitemap.xml not found | Yes | Current: Crawl fetches /sitemap.xml. Best method: Yes - Direct fetch is best | sitemap.xml |
| Homepage does not use HTTPS encryption | Partial | Extend Crawl - explicit homepage URL HTTPS verification. Current: HTTPS on any audited URL. | HTTPS / SSL |
| Subdomains don't support SNI | No | Add via Crawl: TLS SNI handshake probe via ssl library | Not implemented |
| HTTP URLs in sitemap.xml for HTTPS site | No | Add via Crawl: parse sitemap loc values; flag http:// on HTTPS property | Not implemented |
| Uncompressed pages | No | Add via Crawl: check Content-Encoding header on HTML responses | Not implemented |
| Issues with blocked internal resources in robots.txt | No | Add via Crawl: cross-reference JS/CSS URLs against robots Disallow rules | Not implemented |
| Issues with uncompressed JavaScript and CSS files | Partial | Extend PSI + Crawl - PSI audits plus Content-Encoding check on each asset. Current: PSI audits partial coverage. | PSI + Crawl |
| Issues with uncached JavaScript and CSS files | No | Add via Crawl: check Cache-Control on JS/CSS asset responses | Not implemented |
| Pages have JS/CSS total size too large | Partial | Extend PSI + Crawl - sum byte size of all script/stylesheet resources. Current: Third-party script PSI audit partial. | Third-party script impact |
| Pages use too many JavaScript and CSS files | No | Add via Crawl: count script and link rel=stylesheet tags per page | Not implemented |
| Issues with unminified JavaScript and CSS files | Partial | Extend PSI - PSI unminified-javascript and unminified-css audits. Current: PSI audit scores exist. | PSI |
| Link URLs are too long | Partial | Extend Crawl - measure each href string length; flag > 2000 chars. Current: URL structure checks page URL < 115 chars only. | URL structure |
### Notices

| Parameter | In App? | How to measure / Is current method best? | Notes |
|---|---|---|---|
| Pages have more than one H1 tag | Yes | Current: Crawl heading hierarchy - flag multiple H1. Best method: Yes - HTML parse is best | Heading hierarchy |
| Llms.txt not found | Yes | Current: Crawl fetches /llms.txt. Best method: Yes - Direct fetch is best | llms.txt |
| Pages are blocked from crawling | Yes | Current: Crawl meta robots + robots.txt + X-Robots-Tag. Best method: Yes - Combined check is best | Meta robots |
| Page URLs are longer than 200 characters | Partial | Extend Crawl - raise URL length threshold to 200 to match Semrush. Current: URL structure uses 115 char threshold. | URL structure |
| Outgoing external links contain nofollow attributes | No | Add via Crawl: parse rel=nofollow on external anchors | Not implemented |
| Robots.txt not found | Yes | Current: Crawl fetches /robots.txt. Best method: Yes - Direct fetch is best | robots.txt |
| Pages have hreflang language mismatch issues | Partial | Extend Crawl - compare hreflang href lang codes vs html lang attribute. Current: basic hreflang validation only. | hreflang |
| Subdomains don't support HSTS | Partial | Extend Crawl - verify Strict-Transport-Security on all subdomain responses. Current: HSTS checked on audited page response only. | HTTPS / SSL |
| Orphaned pages in Google Analytics | No | Add via GA4 + Crawl: compare GA4 pagePath set vs crawl graph + sitemap URLs | Not implemented |
| Orphaned pages in sitemaps | No | Add via Crawl: pages in sitemap with zero internal inlinks in crawl graph | Not implemented |
| Pages blocked by X-Robots-Tag: noindex HTTP header | Yes | Current: Crawl reads X-Robots-Tag response header. Best method: Yes - Header parse is best | Meta robots |
| Issues with blocked external resources in robots.txt | No | Add via Crawl: cross-reference CDN/external asset URLs vs robots Disallow | Not implemented |
| Issues with broken external JavaScript and CSS files | No | Add via Crawl: HEAD/GET external script and stylesheet URLs | Not implemented |
| Pages need more than 3 clicks to be reached | Yes | Current: Crawl BFS depth from homepage on ~25 pages. Best method: No - Full-site BFS is more accurate | Crawl depth |
| Pages have only one incoming internal link | Partial | Extend Crawl - build inlink count graph from full-site crawl. Current: Internal links checks descriptive anchors only. | Internal links + anchor text |
| URLs with a permanent redirect | Partial | Extend Crawl - site crawl inventory of 301/308 redirect chains. Current: redirect hop count on single URL only. | HTTP status & redirects |
| Resources are formatted as page link | No | Add via Crawl: detect anchor href pointing to non-text/html MIME types | Not implemented |
| Links on this page have no anchor text | Partial | Extend Crawl - flag empty anchor text on all internal links. Current: descriptive anchor % heuristic only. | Internal links + anchor text |
| Links have non-descriptive anchor text | Partial | Extend Crawl - flag anchors matching click here / read more patterns. Current: descriptive % heuristic only. | Internal links + anchor text |
| Links to external pages returned 403 HTTP status | No | Add via Crawl: HEAD/GET external links; record 403 responses | Not implemented |
| Llms.txt has formatting issues | Partial | Extend Crawl - validate llms.txt against spec (markdown structure, required sections). Current: existence check only. | llms.txt |
| Pages contain too much content | No | Add via Crawl: word count upper threshold e.g. > 10000 words | Not implemented |
| Pages have outdated content | Partial | Extend Crawl + GSC - date in HTML/schema; optional GSC URL Inspection lastCrawlTime. Current: date regex heuristic only. | Content freshness signals |
| Pages have low semantic HTML usage | Yes | Current: Crawl counts article/section/aside vs div ratio. Best method: Yes - HTML parse is best | Semantic HTML (GEO) |
| Pages require content optimization | Partial | Extend LLM + Paid - Gemini content quality score; Paid (Semrush) for parity with Semrush score. Current: LLM depth/keyword checks only. | Word count / LLM |
Section 2 totals: Yes 35, Partial 26, No 35

---

## Section 3 - Semrush AI Search Overview PDF
Source: Semrush-Site_Audit__Overview-optiorx_com-9th_Jun_2026.pdf

| Parameter | In App? | How to measure / Is current method best? | Notes |
|---|---|---|---|
| Site Health score (percentage) | Partial | Extend Crawl (derived) - aggregate issue counts from full-site crawl into % healthy pages. Current: category letter grade differs from Semrush %. | Scoring.py |
| AI Search Health score (percentage) | Partial | Extend Crawl (derived) - aggregate AI-bot allow/block across all crawled pages. Current: GEO final score uses different model. | GEO scoring |
| Crawled pages stats (Blocked/Redirect/Broken/Healthy) | No | Add via Crawl: full-site crawl bucket every URL by status, robots block, redirect | Single-page audit today |
| Pages blocked from AI search (aggregate %) | Partial | Extend Crawl - parse robots.txt for all AI user-agents across site; compute % blocked. Current: per-page AiBotCrawlabilityAgent only. | AiBotCrawlabilityAgent |
| ChatGPT-User bot blocking | No | Add via Crawl: robots.txt Disallow check for user-agent ChatGPT-User | Checks GPTBot not ChatGPT-User |
| OAI-SearchBot bot blocking | No | Add via Crawl: robots.txt Disallow check for user-agent OAI-SearchBot | Not in bot list |
| Googlebot blocking | No | Add via Crawl: robots.txt Disallow check for user-agent Googlebot | Only Google-Extended checked |
| Google-Extended bot blocking | Yes | Current: Crawl robots.txt parse for Google-Extended. Best method: Yes - robots.txt parse is the correct method | AiBotCrawlabilityAgent |
| PerplexityBot bot blocking | Yes | Current: Crawl robots.txt grouped with GPTBot/ClaudeBot. Best method: No - Should also check Perplexity-User separately | AiBotCrawlabilityAgent |
| Perplexity-User bot blocking | No | Add via Crawl: robots.txt Disallow check for user-agent Perplexity-User | Not in bot list |
| Claude-User bot blocking | No | Add via Crawl: robots.txt Disallow check for user-agent Claude-User | Checks ClaudeBot not Claude-User |
| Claude-SearchBot bot blocking | No | Add via Crawl: robots.txt Disallow check for user-agent Claude-SearchBot | Not in bot list |
| Top Issues list (Errors/Warnings dashboard) | Partial | Extend Crawl (derived) - aggregate and rank issue counts from full-site crawl by severity. Current: report lists failing params per page only. | Report view |
Section 3 totals: Yes 2, Partial 5, No 6

---

## Appendix - Summary Counts

| Section | Yes | Partial | No | Total |
|---|---|---|---|---|
| 1 - Performance Baseline | 3 | 6 | 14 | 23 |
| 2 - Semrush Full Site Audit | 35 | 26 | 35 | 96 |
| 3 - Semrush AI Search Overview | 2 | 5 | 6 | 13 |
| **Grand total** | **40** | **37** | **55** | **132** |
