"""Build SEO_GEO_Coverage_Comparison.md with detailed measurement column."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "SEO_GEO_Coverage_Comparison.md"


def row(param, status, measure_or_best, notes=""):
    """Return a table row tuple."""
    return (param, status, measure_or_best, notes)


def gap(source, detail):
    return f"Add via {source}: {detail}"


def partial_extend(source, detail, current=""):
    cur = f" Current: {current}." if current else ""
    return f"Extend {source} - {detail}.{cur}"


def yes_best(is_best, current, reason):
    verdict = "Yes" if is_best else "No"
    return f"Current: {current}. Best method: {verdict} - {reason}"


HEADER = """# SEO & GEO Auditor - Coverage Comparison

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

"""


def render_table(rows):
    lines = [
        "| Parameter | In App? | How to measure / Is current method best? | Notes |",
        "|---|---|---|---|",
    ]
    for p, s, m, n in rows:
        lines.append(f"| {p} | {s} | {m} | {n} |")
    return "\n".join(lines) + "\n"


# --- Section 1 ---
S1 = [
    row("Engagement Rate", "Partial",
        partial_extend("GA4", "runReport metric engagementRate as standalone KPI (property or page level)",
                       "embedded in Pogo-sticking risk only"),
        "UxAgent"),
    row("Total Users", "No",
        gap("GA4", "runReport metric totalUsers at property level with dateRange"),
        "Not in Ga4Client"),
    row("New Users", "No",
        gap("GA4", "runReport metric newUsers at property level"),
        "Not in Ga4Client"),
    row("Average Session Duration", "Partial",
        partial_extend("GA4", "already available via Connected Mode - expose as standalone metric",
                       "Dwell time / scroll depth per page"),
        "UxAgent"),
    row("Bounce Rate", "Partial",
        partial_extend("GA4", "already available via Connected Mode - expose as standalone metric",
                       "Bounce rate in context per page"),
        "UxAgent"),
    row("Clicks by Device (Mobile/Desktop/Tablet)", "No",
        gap("GSC", "searchAnalytics.query with dimension device"),
        "Not implemented"),
    row("Clicks by Country", "No",
        gap("GSC", "searchAnalytics.query with dimension country"),
        "Not implemented"),
    row("Organic traffic trend (top pages traffic %)", "No",
        gap("GSC + Paid", "GSC searchAnalytics with page dimension for clicks; Paid (Semrush) only for traffic % estimates"),
        "No dashboard"),
    row("Traffic by source (organic/direct/referral)", "No",
        gap("GA4", "runReport with dimension sessionDefaultChannelGroup"),
        "Not implemented"),
    row("Session source breakdown (google/bing/yahoo/etc.)", "No",
        gap("GA4", "runReport with dimension sessionSource, sorted by users"),
        "Not implemented"),
    row("Organic Social traffic", "No",
        gap("GA4", "runReport filter sessionDefaultChannelGroup = Organic Social"),
        "Not implemented"),
    row("Session primary channel group", "No",
        gap("GA4", "runReport with dimension sessionPrimaryChannelGroup"),
        "Not implemented"),
    row("Top ranking keywords (CTR, position, clicks, impressions)", "Partial",
        partial_extend("GSC", "searchAnalytics.query with query dimension, top 20 by clicks",
                       "page-level CTR only via Click-through rate"),
        "UxAgent / GSC"),
    row("Bounce rate trend (time series)", "No",
        gap("GA4", "runReport with date dimension + bounceRate metric over 28/90 days"),
        "No time series"),
    row("Average engagement time trend (time series)", "No",
        gap("GA4", "runReport with date dimension + averageSessionDuration"),
        "No time series"),
    row("Pages per session", "No",
        gap("GA4", "runReport metric screenPageViewsPerSession or views/sessions"),
        "Not in Ga4Client"),
    row("Mobile vs Desktop traffic split", "Partial",
        partial_extend("GA4", "runReport with deviceCategory dimension for users/sessions",
                       "Mobile vs desktop delta compares CWV only, not traffic"),
        "CoreWebVitalsAgent"),
    row("LCP (Core Web Vitals)", "Yes",
        yes_best(True, "PSI lab + CrUX via CoreWebVitalsAgent", "PSI is the Google-standard source for LCP"),
        "CoreWebVitalsAgent"),
    row("CLS (Core Web Vitals)", "Yes",
        yes_best(True, "PSI lab + CrUX via CoreWebVitalsAgent", "PSI is the standard source for CLS"),
        "CoreWebVitalsAgent"),
    row("INP (Core Web Vitals)", "Yes",
        yes_best(True, "PSI CrUX field INP with TBT lab fallback", "PSI/CrUX is the correct source for INP"),
        "CoreWebVitalsAgent"),
    row("Page load speed - Desktop", "Partial",
        partial_extend("PSI", "expose Lighthouse performance score + LCP as dedicated load-speed KPI",
                       "LCP/TTFB/Lighthouse exist but not labeled as load speed"),
        "CoreWebVitalsAgent"),
    row("Page load speed - Mobile", "Partial",
        partial_extend("PSI", "same as desktop using strategy=mobile", "PSI mobile run exists"),
        "CoreWebVitalsAgent"),
    row("Form submissions by type", "No",
        gap("GA4", "runReport with eventName dimension filtered to form_submit or custom conversion events"),
        "Not implemented"),
    row("Top exit pages", "No",
        gap("GA4", "runReport pagePath + sessions or exitRate metric, sorted descending"),
        "Not implemented"),
]

# --- Section 2 Errors ---
S2E = [
    row("Pages returned 5XX status code", "Partial",
        partial_extend("Crawl", "full-site crawl: HEAD/GET every sitemap URL and record status >= 500",
                       "Broken links samples ~25 pages only"),
        "Broken links / HTTP status"),
    row("Pages returned 4XX status code", "Partial",
        partial_extend("Crawl", "full-site crawl status inventory for all internal URLs",
                       "Broken links on crawl sample only"),
        "Broken links"),
    row("Pages don't have title tags", "Yes",
        yes_best(True, "Crawl parses <title> on audited page", "Direct HTML parse is the correct method"),
        "Title tag"),
    row("Issues with duplicate title tags", "Partial",
        partial_extend("Crawl", "hash all titles across full-site crawl and flag duplicates",
                       "checks single page title length only"),
        "Title tag"),
    row("Pages have duplicate content issues", "Partial",
        partial_extend("Crawl + LLM", "simhash/content fingerprint across crawled pages + canonical check",
                       "Duplicate content checks canonical on one page only"),
        "Duplicate content"),
    row("Internal links are broken", "Yes",
        yes_best(False, "Crawl samples link_status on ~25 pages", "Full-site link check is more complete than sample"),
        "Broken links"),
    row("Pages couldn't be crawled", "No",
        gap("Crawl", "full-site crawl with failure taxonomy: timeout, DNS, robots block, 403"),
        "Not implemented"),
    row("Pages couldn't be crawled (DNS resolution issues)", "No",
        gap("Crawl", "socket.getaddrinfo before fetch; record NXDOMAIN failures"),
        "Not implemented"),
    row("Pages couldn't be crawled (incorrect URL formats)", "Partial",
        partial_extend("Crawl", "validate all sitemap and discovered URLs with urlparse",
                       "URL structure checks current URL only"),
        "URL structure"),
    row("Internal images are broken", "No",
        gap("Crawl", "HEAD/GET each img src from every crawled page"),
        "Image alt only today"),
    row("Pages have duplicate meta descriptions", "Partial",
        partial_extend("Crawl", "hash meta descriptions across full-site crawl",
                       "Meta description on single page only"),
        "Meta description"),
    row("Robots.txt file has format errors", "Yes",
        yes_best(True, "Crawl fetches and parses /robots.txt", "Direct fetch + parse is best"),
        "robots.txt"),
    row("sitemap.xml files have format errors", "Yes",
        yes_best(True, "Crawl fetches and parses sitemap XML", "Direct fetch + parse is best"),
        "sitemap.xml"),
    row("Incorrect pages found in sitemap.xml", "Partial",
        partial_extend("Crawl", "fetch each sitemap loc URL and verify status 200",
                       "sitemap checks existence and lastmod count only"),
        "sitemap.xml"),
    row("Pages have a WWW resolve issue", "No",
        gap("Crawl", "fetch http://www and http://non-www; verify consistent 301 to canonical"),
        "Not implemented"),
    row("This page has no viewport tag", "Yes",
        yes_best(True, "Crawl parses meta viewport", "HTML parse is best"),
        "Mobile viewport"),
    row("Pages have too large HTML size", "No",
        gap("Crawl", "measure len(response.content) per page; flag above threshold e.g. 2MB"),
        "Not implemented"),
    row("AMP pages have no canonical tag", "Partial",
        partial_extend("Crawl", "if AMP detected, require amphtml/canonical pairing",
                       "AMP / Web Stories is informational only"),
        "AMP / Web Stories"),
    row("Issues with hreflang values", "Yes",
        yes_best(False, "Crawl parses hreflang link tags + x-default", "Full reciprocity validation needs cross-page crawl"),
        "hreflang"),
    row("hreflang conflicts within page source code", "Partial",
        partial_extend("Crawl", "detect duplicate hreflang langs and conflicting targets on same page",
                       "basic hreflang + x-default check only"),
        "hreflang"),
    row("Issues with incorrect hreflang links", "Partial",
        partial_extend("Crawl", "fetch each hreflang href and verify 200 + return hreflang",
                       "does not validate target pages today"),
        "hreflang"),
    row("Non-secure pages", "Yes",
        yes_best(True, "Crawl checks TLS + HTTPS URL", "Direct TLS/URL check is best"),
        "HTTPS / SSL"),
    row("Issues with expiring or expired certificate", "Partial",
        partial_extend("Crawl", "read cert notAfter via ssl.get_server_certificate",
                       "tls_ok boolean only, no expiry date"),
        "HTTPS / SSL"),
    row("Issues with old security protocol", "No",
        gap("Crawl", "TLS handshake probe for minimum TLS 1.2"),
        "Not implemented"),
    row("Issues with incorrect certificate name", "No",
        gap("Crawl", "compare cert SAN/CN to hostname via ssl module"),
        "Not implemented"),
    row("Issues with mixed content", "Yes",
        yes_best(True, "Crawl scans page resources for http:// on https pages", "Resource scan is best"),
        "HTTPS / SSL"),
    row("No redirect or canonical to HTTPS homepage from HTTP", "Partial",
        partial_extend("Crawl", "explicit fetch http://homepage and assert 301/308 to https",
                       "HTTPS check on audited URL only"),
        "HTTPS / SSL"),
    row("Pages with a broken canonical link", "Yes",
        yes_best(True, "Crawl parses canonical and compares to final URL", "Parse + self-ref check is best for single page"),
        "Canonical tags"),
    row("Pages have multiple canonical URLs", "Partial",
        partial_extend("Crawl", "count all link rel=canonical tags; flag if > 1",
                       "checks presence and self-ref only"),
        "Canonical tags"),
    row("Pages have a meta refresh tag", "No",
        gap("Crawl", "detect meta http-equiv=refresh in HTML"),
        "Not implemented"),
    row("Issues with broken internal JavaScript and CSS files", "No",
        gap("Crawl", "HEAD/GET every script src and link rel=stylesheet on crawled pages"),
        "Not implemented"),
    row("Subdomains don't support secure encryption algorithms", "No",
        gap("Crawl", "TLS cipher probe or SSL Labs API (free tier)"),
        "Not implemented"),
    row("sitemap.xml files are too large", "No",
        gap("Crawl", "count URLs in sitemap; flag if > 50000"),
        "Not implemented"),
    row("Links couldn't be crawled (incorrect URL formats)", "No",
        gap("Crawl", "urlparse validation on all discovered href values"),
        "Not implemented"),
    row("Structured data items are invalid", "Yes",
        yes_best(False, "Crawl validates JSON-LD types and required fields heuristically", "Google Rich Results Test API would be more authoritative"),
        "Schema.org JSON-LD"),
    row("Pages are missing the viewport width value", "Yes",
        yes_best(True, "Crawl checks width=device-width in viewport meta", "HTML parse is best"),
        "Mobile viewport"),
    row("Pages have slow load speed", "Partial",
        partial_extend("PSI + Crawl", "combine PSI LCP/TTFB thresholds with crawl-measured TTFB",
                       "PSI metrics exist but no Semrush-style slow-page flag"),
        "CoreWebVitalsAgent"),
]

S2W = [
    row("External links are broken", "Partial",
        partial_extend("Crawl", "HEAD/GET all external hrefs from full crawl",
                       "Broken links focuses on internal sample"),
        "Broken links"),
    row("External images are broken", "No",
        gap("Crawl", "HEAD/GET external img src URLs"),
        "Not implemented"),
    row("Links on HTTPS pages lead to HTTP page", "Partial",
        partial_extend("Crawl", "scan all href/src for http:// on HTTPS pages",
                       "mixed content check partially covers"),
        "HTTPS / SSL"),
    row("Pages don't have enough text within title tags", "Yes",
        yes_best(True, "Crawl title length 50-60 char heuristic", "Length check is standard"),
        "Title tag"),
    row("Pages have too much text within title tags", "Yes",
        yes_best(True, "Crawl title length check", "Length check is standard"),
        "Title tag"),
    row("Pages don't have an h1 heading", "Yes",
        yes_best(True, "Crawl heading hierarchy - require exactly one H1", "HTML parse is best"),
        "Heading hierarchy"),
    row("Pages have duplicate H1 and title tags", "No",
        gap("Crawl", "string compare normalized h1 text vs title text"),
        "Not implemented"),
    row("Pages don't have meta descriptions", "Yes",
        yes_best(True, "Crawl parses meta description", "HTML parse is best"),
        "Meta description"),
    row("Pages have too many on-page links", "No",
        gap("Crawl", "count anchor tags; flag if > threshold e.g. 100"),
        "Not implemented"),
    row("URLs with a temporary redirect", "Partial",
        partial_extend("Crawl", "full-site crawl records 302/307 chains",
                       "HTTP status flags 302 on single URL only"),
        "HTTP status & redirects"),
    row("Images don't have alt attributes", "Yes",
        yes_best(True, "Crawl img alt coverage >= 90%", "HTML parse is best"),
        "Image alt coverage"),
    row("Pages have low text-HTML ratio", "No",
        gap("Crawl", "ratio visible_text bytes / html bytes; flag low ratio"),
        "Not implemented"),
    row("Pages have too many parameters in their URLs", "Yes",
        yes_best(True, "Crawl URL structure <= 2 query params", "URL parse is best"),
        "URL structure"),
    row("Pages have no hreflang and lang attributes", "Partial",
        partial_extend("Crawl", "check html lang attribute in addition to hreflang",
                       "hreflang checked when present; lang not checked"),
        "hreflang"),
    row("Pages don't have character encoding declared", "No",
        gap("Crawl", "check meta charset or Content-Type charset header"),
        "Not implemented"),
    row("Pages don't have doctype declared", "No",
        gap("Crawl", "assert HTML starts with <!DOCTYPE"),
        "Not implemented"),
    row("Pages have a low word count", "Yes",
        yes_best(False, "Crawl word count + Gemini depth judgement", "Competitive benchmark needs SERP comparison (GSC/LLM)"),
        "Word count / content depth"),
    row("Pages have incompatible plugin content", "No",
        gap("Crawl", "detect object/embed/applet tags"),
        "Not implemented"),
    row("Pages contain frames", "No",
        gap("Crawl", "detect frame tags (exclude iframe embeds)"),
        "Not implemented"),
    row("Pages have underscores in the URL", "Yes",
        yes_best(True, "Crawl URL path underscore check", "URL parse is best"),
        "URL structure"),
    row("Outgoing internal links contain nofollow attribute", "No",
        gap("Crawl", "parse rel=nofollow on internal anchor tags"),
        "Not implemented"),
    row("Sitemap.xml not indicated in robots.txt", "Partial",
        partial_extend("Crawl", "parse Sitemap: directive in robots.txt",
                       "robots.txt and sitemap checked separately"),
        "robots.txt + sitemap.xml"),
    row("Sitemap.xml not found", "Yes",
        yes_best(True, "Crawl fetches /sitemap.xml", "Direct fetch is best"),
        "sitemap.xml"),
    row("Homepage does not use HTTPS encryption", "Partial",
        partial_extend("Crawl", "explicit homepage URL HTTPS verification",
                       "HTTPS on any audited URL"),
        "HTTPS / SSL"),
    row("Subdomains don't support SNI", "No",
        gap("Crawl", "TLS SNI handshake probe via ssl library"),
        "Not implemented"),
    row("HTTP URLs in sitemap.xml for HTTPS site", "No",
        gap("Crawl", "parse sitemap loc values; flag http:// on HTTPS property"),
        "Not implemented"),
    row("Uncompressed pages", "No",
        gap("Crawl", "check Content-Encoding header on HTML responses"),
        "Not implemented"),
    row("Issues with blocked internal resources in robots.txt", "No",
        gap("Crawl", "cross-reference JS/CSS URLs against robots Disallow rules"),
        "Not implemented"),
    row("Issues with uncompressed JavaScript and CSS files", "Partial",
        partial_extend("PSI + Crawl", "PSI audits plus Content-Encoding check on each asset",
                       "PSI audits partial coverage"),
        "PSI + Crawl"),
    row("Issues with uncached JavaScript and CSS files", "No",
        gap("Crawl", "check Cache-Control on JS/CSS asset responses"),
        "Not implemented"),
    row("Pages have JS/CSS total size too large", "Partial",
        partial_extend("PSI + Crawl", "sum byte size of all script/stylesheet resources",
                       "Third-party script PSI audit partial"),
        "Third-party script impact"),
    row("Pages use too many JavaScript and CSS files", "No",
        gap("Crawl", "count script and link rel=stylesheet tags per page"),
        "Not implemented"),
    row("Issues with unminified JavaScript and CSS files", "Partial",
        partial_extend("PSI", "PSI unminified-javascript and unminified-css audits",
                       "PSI audit scores exist"),
        "PSI"),
    row("Link URLs are too long", "Partial",
        partial_extend("Crawl", "measure each href string length; flag > 2000 chars",
                       "URL structure checks page URL < 115 chars only"),
        "URL structure"),
]

S2N = [
    row("Pages have more than one H1 tag", "Yes",
        yes_best(True, "Crawl heading hierarchy - flag multiple H1", "HTML parse is best"),
        "Heading hierarchy"),
    row("Llms.txt not found", "Yes",
        yes_best(True, "Crawl fetches /llms.txt", "Direct fetch is best"),
        "llms.txt"),
    row("Pages are blocked from crawling", "Yes",
        yes_best(True, "Crawl meta robots + robots.txt + X-Robots-Tag", "Combined check is best"),
        "Meta robots"),
    row("Page URLs are longer than 200 characters", "Partial",
        partial_extend("Crawl", "raise URL length threshold to 200 to match Semrush",
                       "URL structure uses 115 char threshold"),
        "URL structure"),
    row("Outgoing external links contain nofollow attributes", "No",
        gap("Crawl", "parse rel=nofollow on external anchors"),
        "Not implemented"),
    row("Robots.txt not found", "Yes",
        yes_best(True, "Crawl fetches /robots.txt", "Direct fetch is best"),
        "robots.txt"),
    row("Pages have hreflang language mismatch issues", "Partial",
        partial_extend("Crawl", "compare hreflang href lang codes vs html lang attribute",
                       "basic hreflang validation only"),
        "hreflang"),
    row("Subdomains don't support HSTS", "Partial",
        partial_extend("Crawl", "verify Strict-Transport-Security on all subdomain responses",
                       "HSTS checked on audited page response only"),
        "HTTPS / SSL"),
    row("Orphaned pages in Google Analytics", "No",
        gap("GA4 + Crawl", "compare GA4 pagePath set vs crawl graph + sitemap URLs"),
        "Not implemented"),
    row("Orphaned pages in sitemaps", "No",
        gap("Crawl", "pages in sitemap with zero internal inlinks in crawl graph"),
        "Not implemented"),
    row("Pages blocked by X-Robots-Tag: noindex HTTP header", "Yes",
        yes_best(True, "Crawl reads X-Robots-Tag response header", "Header parse is best"),
        "Meta robots"),
    row("Issues with blocked external resources in robots.txt", "No",
        gap("Crawl", "cross-reference CDN/external asset URLs vs robots Disallow"),
        "Not implemented"),
    row("Issues with broken external JavaScript and CSS files", "No",
        gap("Crawl", "HEAD/GET external script and stylesheet URLs"),
        "Not implemented"),
    row("Pages need more than 3 clicks to be reached", "Yes",
        yes_best(False, "Crawl BFS depth from homepage on ~25 pages", "Full-site BFS is more accurate"),
        "Crawl depth"),
    row("Pages have only one incoming internal link", "Partial",
        partial_extend("Crawl", "build inlink count graph from full-site crawl",
                       "Internal links checks descriptive anchors only"),
        "Internal links + anchor text"),
    row("URLs with a permanent redirect", "Partial",
        partial_extend("Crawl", "site crawl inventory of 301/308 redirect chains",
                       "redirect hop count on single URL only"),
        "HTTP status & redirects"),
    row("Resources are formatted as page link", "No",
        gap("Crawl", "detect anchor href pointing to non-text/html MIME types"),
        "Not implemented"),
    row("Links on this page have no anchor text", "Partial",
        partial_extend("Crawl", "flag empty anchor text on all internal links",
                       "descriptive anchor % heuristic only"),
        "Internal links + anchor text"),
    row("Links have non-descriptive anchor text", "Partial",
        partial_extend("Crawl", "flag anchors matching click here / read more patterns",
                       "descriptive % heuristic only"),
        "Internal links + anchor text"),
    row("Links to external pages returned 403 HTTP status", "No",
        gap("Crawl", "HEAD/GET external links; record 403 responses"),
        "Not implemented"),
    row("Llms.txt has formatting issues", "Partial",
        partial_extend("Crawl", "validate llms.txt against spec (markdown structure, required sections)",
                       "existence check only"),
        "llms.txt"),
    row("Pages contain too much content", "No",
        gap("Crawl", "word count upper threshold e.g. > 10000 words"),
        "Not implemented"),
    row("Pages have outdated content", "Partial",
        partial_extend("Crawl + GSC", "date in HTML/schema; optional GSC URL Inspection lastCrawlTime",
                       "date regex heuristic only"),
        "Content freshness signals"),
    row("Pages have low semantic HTML usage", "Yes",
        yes_best(True, "Crawl counts article/section/aside vs div ratio", "HTML parse is best"),
        "Semantic HTML (GEO)"),
    row("Pages require content optimization", "Partial",
        partial_extend("LLM + Paid", "Gemini content quality score; Paid (Semrush) for parity with Semrush score",
                       "LLM depth/keyword checks only"),
        "Word count / LLM"),
]

S3 = [
    row("Site Health score (percentage)", "Partial",
        partial_extend("Crawl (derived)", "aggregate issue counts from full-site crawl into % healthy pages",
                       "category letter grade differs from Semrush %"),
        "Scoring.py"),
    row("AI Search Health score (percentage)", "Partial",
        partial_extend("Crawl (derived)", "aggregate AI-bot allow/block across all crawled pages",
                       "GEO final score uses different model"),
        "GEO scoring"),
    row("Crawled pages stats (Blocked/Redirect/Broken/Healthy)", "No",
        gap("Crawl", "full-site crawl bucket every URL by status, robots block, redirect"),
        "Single-page audit today"),
    row("Pages blocked from AI search (aggregate %)", "Partial",
        partial_extend("Crawl", "parse robots.txt for all AI user-agents across site; compute % blocked",
                       "per-page AiBotCrawlabilityAgent only"),
        "AiBotCrawlabilityAgent"),
    row("ChatGPT-User bot blocking", "No",
        gap("Crawl", "robots.txt Disallow check for user-agent ChatGPT-User"),
        "Checks GPTBot not ChatGPT-User"),
    row("OAI-SearchBot bot blocking", "No",
        gap("Crawl", "robots.txt Disallow check for user-agent OAI-SearchBot"),
        "Not in bot list"),
    row("Googlebot blocking", "No",
        gap("Crawl", "robots.txt Disallow check for user-agent Googlebot"),
        "Only Google-Extended checked"),
    row("Google-Extended bot blocking", "Yes",
        yes_best(True, "Crawl robots.txt parse for Google-Extended", "robots.txt parse is the correct method"),
        "AiBotCrawlabilityAgent"),
    row("PerplexityBot bot blocking", "Yes",
        yes_best(False, "Crawl robots.txt grouped with GPTBot/ClaudeBot", "Should also check Perplexity-User separately"),
        "AiBotCrawlabilityAgent"),
    row("Perplexity-User bot blocking", "No",
        gap("Crawl", "robots.txt Disallow check for user-agent Perplexity-User"),
        "Not in bot list"),
    row("Claude-User bot blocking", "No",
        gap("Crawl", "robots.txt Disallow check for user-agent Claude-User"),
        "Checks ClaudeBot not Claude-User"),
    row("Claude-SearchBot bot blocking", "No",
        gap("Crawl", "robots.txt Disallow check for user-agent Claude-SearchBot"),
        "Not in bot list"),
    row("Top Issues list (Errors/Warnings dashboard)", "Partial",
        partial_extend("Crawl (derived)", "aggregate and rank issue counts from full-site crawl by severity",
                       "report lists failing params per page only"),
        "Report view"),
]


def main():
    parts = [HEADER]
    parts.append("## Section 1 - Performance Baseline PDF\n")
    parts.append("Source: Performance_Baseline-Traffic__Engagement__SEO___Web_Vitals___Feb_20__20-21st_May_2026.pdf\n\n")
    parts.append(render_table(S1))
    parts.append("Section 1 totals: Yes 3, Partial 6, No 14\n\n---\n\n")

    parts.append("## Section 2 - Semrush Full Site Audit PDF\n")
    parts.append("Source: Semrush-Full_Site_Audit_Report-optiorx_com-6th_Feb_2026.pdf\n\n")
    parts.append("### Errors\n\n")
    parts.append(render_table(S2E))
    parts.append("### Warnings\n\n")
    parts.append(render_table(S2W))
    parts.append("### Notices\n\n")
    parts.append(render_table(S2N))
    parts.append("Section 2 totals: Yes 35, Partial 26, No 35\n\n---\n\n")

    parts.append("## Section 3 - Semrush AI Search Overview PDF\n")
    parts.append("Source: Semrush-Site_Audit__Overview-optiorx_com-9th_Jun_2026.pdf\n\n")
    parts.append(render_table(S3))
    parts.append("Section 3 totals: Yes 2, Partial 5, No 6\n\n---\n\n")

    parts.append("""## Appendix - Summary Counts

| Section | Yes | Partial | No | Total |
|---|---|---|---|---|
| 1 - Performance Baseline | 3 | 6 | 14 | 23 |
| 2 - Semrush Full Site Audit | 35 | 26 | 35 | 96 |
| 3 - Semrush AI Search Overview | 2 | 5 | 6 | 13 |
| **Grand total** | **40** | **37** | **55** | **132** |
""")

    OUT.write_text("".join(parts), encoding="utf-8")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
