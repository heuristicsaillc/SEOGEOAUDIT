"""Parameter catalogs for the three supplementary reference-style PDF reports.

Maps each external PDF metric to existing SEO/GEO auditor parameter names.
Uncalculated metrics are exported as Manual with a documented reason.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RefParameter:
    """One row in a supplementary reference PDF."""

    name: str
    pdf: str  # baseline | site_audit_full | ai_search_overview
    section: str
    app_keys: tuple[str, ...]
    manual_reason: str


def _b(name: str, keys: tuple[str, ...], reason: str) -> RefParameter:
    return RefParameter(name, "baseline", "Metrics", keys, reason)


def _s(name: str, section: str, keys: tuple[str, ...], reason: str) -> RefParameter:
    return RefParameter(name, "site_audit_full", section, keys, reason)


def _o(name: str, keys: tuple[str, ...], reason: str) -> RefParameter:
    return RefParameter(name, "site_audit_full", "Overview", keys, reason)


def _a(name: str, keys: tuple[str, ...], reason: str) -> RefParameter:
    return RefParameter(name, "ai_search_overview", "AI Search", keys, reason)


BASELINE_PARAMS: list[RefParameter] = [
    _b("Engagement Rate", ("Pogo-sticking risk",), "Requires GA4 Connected Mode with property-level engagementRate (also used by Pogo-sticking risk)."),
    _b("Total Users", (), "Requires GA4 runReport totalUsers at property level."),
    _b("New Users", (), "Requires GA4 runReport newUsers at property level."),
    _b("Average Session Duration", ("Dwell time / scroll depth",), "Property-level GA4 averageSessionDuration when Connected Mode is active."),
    _b("Bounce Rate", ("Bounce rate in context",), "Requires GA4 Connected Mode with session data for this page."),
    _b("Clicks by Device (Mobile/Desktop/Tablet)", (), "Requires GSC searchAnalytics with device dimension."),
    _b("Clicks by Country", (), "Requires GSC searchAnalytics with country dimension."),
    _b("Organic traffic trend (top pages traffic %)", (), "Requires GSC page-level analytics dashboard or paid traffic estimates."),
    _b("Traffic by source (organic/direct/referral)", (), "Requires GA4 sessionDefaultChannelGroup dimension."),
    _b("Session source breakdown (google/bing/yahoo/etc.)", (), "Requires GA4 sessionSource dimension."),
    _b("Organic Social traffic", (), "Requires GA4 Organic Social channel filter."),
    _b("Session primary channel group", (), "Requires GA4 sessionPrimaryChannelGroup dimension."),
    _b("Top ranking keywords (CTR, position, clicks, impressions)", (), "Requires GSC query dimension for keyword top-20 list."),
    _b(
        "Bounce rate & Average engagement time (charts)",
        (),
        "GA4 daily bounceRate and averageSessionDuration charts (Semrush section title).",
    ),
    _b("Pages per session", (), "Requires GA4 screenPageViewsPerSession metric."),
    _b("Mobile vs Desktop traffic split", ("Mobile vs desktop delta",), "Requires GA4 deviceCategory split (app only compares CWV delta today)."),
    _b("LCP (Core Web Vitals)", ("LCP",), "Requires PageSpeed Insights API."),
    _b("CLS (Core Web Vitals)", ("CLS",), "Requires PageSpeed Insights API."),
    _b("INP (Core Web Vitals)", ("INP",), "Requires PageSpeed Insights API."),
    _b("Page load speed - Desktop", ("Lighthouse scores", "LCP", "TTFB"), "Requires PSI; no dedicated load-speed KPI label."),
    _b("Page load speed - Mobile", ("Lighthouse scores", "LCP", "TTFB"), "Requires PSI mobile run; no dedicated load-speed KPI label."),
    _b("Form submissions by type", (), "Requires GA4 event/conversion tracking by form type."),
    _b("Top exit pages", (), "Requires GA4 exit page report."),
]

SITE_AUDIT_FULL_PARAMS: list[RefParameter] = [
    _o("Internal Link Distribution", ("Internal link distribution",), "Requires inlink graph from multi-page crawl."),
    _s("Pages returned 5XX status code", "Errors", ("Broken links", "HTTP status & redirects"), "Requires full-site crawl status inventory."),
    _s("Pages returned 4XX status code", "Errors", ("Broken links",), "Requires full-site 4XX page inventory."),
    _s("Pages don't have title tags", "Errors", ("Title tag",), "Single-page crawl only when not calculated."),
    _s("Issues with duplicate title tags", "Errors", ("Title tag",), "Requires cross-site title deduplication."),
    _s("Pages have duplicate content issues", "Errors", ("Duplicate content",), "Requires site-wide near-duplicate fingerprinting."),
    _s("Internal links are broken", "Errors", ("Broken links",), "Samples internal links only (~25 pages)."),
    _s("Pages couldn't be crawled", "Errors", ("Crawl failures",), "Requires full-site crawl failure taxonomy."),
    _s("Pages couldn't be crawled (DNS resolution issues)", "Errors", ("DNS resolution",), "Requires DNS pre-check on crawl."),
    _s("Pages couldn't be crawled (incorrect URL formats)", "Errors", ("Malformed link URLs", "URL structure"), "Requires site-wide URL validation."),
    _s("Internal images are broken", "Errors", ("Broken internal images",), "Requires HEAD/GET on all image URLs."),
    _s("Pages have duplicate meta descriptions", "Errors", ("Meta description",), "Requires cross-site meta deduplication."),
    _s("Robots.txt file has format errors", "Errors", ("robots.txt",), "Not calculated on this audit."),
    _s("sitemap.xml files have format errors", "Errors", ("sitemap.xml",), "Not calculated on this audit."),
    _s("Incorrect pages found in sitemap.xml", "Errors", ("Sitemap URL validation",), "Requires validating every sitemap URL status."),
    _s("Pages have a WWW resolve issue", "Errors", ("WWW resolve",), "Requires www vs non-www redirect comparison."),
    _s("This page has no viewport tag", "Errors", ("Mobile viewport",), "Not calculated on this audit."),
    _s("Pages have too large HTML size", "Errors", ("HTML byte size",), "Requires per-page HTML byte size threshold."),
    _s("AMP pages have no canonical tag", "Errors", ("AMP canonical tag",), "AMP check is informational only."),
    _s("Issues with hreflang values", "Errors", ("hreflang",), "Not calculated on this audit."),
    _s("hreflang conflicts within page source code", "Errors", ("hreflang",), "Requires full hreflang conflict detection."),
    _s("Issues with incorrect hreflang links", "Errors", ("hreflang",), "Requires fetching hreflang target URLs."),
    _s("Non-secure pages", "Errors", ("HTTPS / SSL",), "Not calculated on this audit."),
    _s("Issues with expiring or expired certificate", "Errors", ("HTTPS / SSL",), "Requires certificate expiry date parsing."),
    _s("Issues with old security protocol", "Errors", ("TLS protocol version",), "Requires TLS version probe."),
    _s("Issues with incorrect certificate name", "Errors", ("Certificate hostname",), "Requires cert CN/SAN vs hostname check."),
    _s("Issues with mixed content", "Errors", ("HTTPS / SSL",), "Not calculated on this audit."),
    _s("No redirect or canonical to HTTPS homepage from HTTP", "Errors", ("HTTP homepage HTTPS redirect",), "Requires explicit HTTP homepage fetch."),
    _s("Pages with a broken canonical link", "Errors", ("Canonical tags",), "Not calculated on this audit."),
    _s("Pages have multiple canonical URLs", "Errors", ("Canonical tags",), "Requires counting multiple canonical tags."),
    _s("Pages have a meta refresh tag", "Errors", ("Meta refresh tag",), "Requires meta refresh detection."),
    _s("Issues with broken internal JavaScript and CSS files", "Errors", ("Broken internal assets",), "Requires asset URL status checks."),
    _s("Subdomains don't support secure encryption algorithms", "Errors", ("TLS subdomain ciphers",), "Requires TLS cipher audit."),
    _s("sitemap.xml files are too large", "Errors", ("Sitemap size limit",), "Requires sitemap URL count vs 50k limit."),
    _s("Links couldn't be crawled (incorrect URL formats)", "Errors", ("Malformed link URLs",), "Requires site-wide link URL validation."),
    _s("Structured data items are invalid", "Errors", ("Schema.org JSON-LD", "Rich result eligibility"), "Not calculated on this audit."),
    _s("Pages are missing the viewport width value", "Errors", ("Mobile viewport",), "Not calculated on this audit."),
    _s("Pages have slow load speed", "Errors", ("LCP", "TTFB", "Lighthouse scores"), "Requires combined PSI LCP/TTFB slow-page threshold."),
    _s("External links are broken", "Warnings", ("Broken links",), "Internal link sample only."),
    _s("External images are broken", "Warnings", ("Broken external images",), "Requires external image URL checks."),
    _s("Links on HTTPS pages lead to HTTP page", "Warnings", ("HTTPS / SSL",), "Mixed-content scan is partial coverage."),
    _s("Pages don't have enough text within title tags", "Warnings", ("Title too short",), "Not calculated on this audit."),
    _s("Pages have too much text within title tags", "Warnings", ("Title too long",), "Not calculated on this audit."),
    _s("Pages don't have an h1 heading", "Warnings", ("Heading hierarchy",), "Not calculated on this audit."),
    _s("Pages have duplicate H1 and title tags", "Warnings", ("Duplicate H1 and title",), "Requires H1 vs title string comparison."),
    _s("Pages don't have meta descriptions", "Warnings", ("Meta description",), "Not calculated on this audit."),
    _s("Pages have too many on-page links", "Warnings", ("On-page link count",), "Requires on-page link count threshold."),
    _s("URLs with a temporary redirect", "Warnings", ("HTTP status & redirects",), "Single-URL redirect check only."),
    _s("Images don't have alt attributes", "Warnings", ("Image alt coverage",), "Not calculated on this audit."),
    _s("Pages have low text-HTML ratio", "Warnings", ("Text-HTML ratio",), "Requires text-to-HTML ratio metric."),
    _s("Pages have too many parameters in their URLs", "Warnings", ("URL structure",), "Not calculated on this audit."),
    _s("Pages have no hreflang and lang attributes", "Warnings", ("hreflang",), "html lang attribute not checked."),
    _s("Pages don't have character encoding declared", "Warnings", ("Character encoding",), "Requires charset meta/header check."),
    _s("Pages don't have doctype declared", "Warnings", ("DOCTYPE",), "Requires DOCTYPE detection."),
    _s("Pages have a low word count", "Warnings", ("Word count / content depth",), "Not calculated on this audit."),
    _s("Pages have incompatible plugin content", "Warnings", ("Plugin content",), "Requires object/embed detection."),
    _s("Pages contain frames", "Warnings", ("Frame tags",), "Requires frame tag detection."),
    _s("Pages have underscores in the URL", "Warnings", ("URL structure",), "Not calculated on this audit."),
    _s("Outgoing internal links contain nofollow attribute", "Warnings", ("Internal nofollow links",), "Requires rel=nofollow parse on internal links."),
    _s("Sitemap.xml not indicated in robots.txt", "Warnings", ("robots.txt", "sitemap.xml"), "Does not cross-reference Sitemap: directive."),
    _s("Sitemap.xml not found", "Warnings", ("sitemap.xml",), "Not calculated on this audit."),
    _s("Homepage does not use HTTPS encryption", "Warnings", ("HTTPS / SSL",), "Checks audited URL only, not homepage-specific."),
    _s("Subdomains don't support SNI", "Warnings", ("TLS subdomain SNI",), "Requires TLS SNI probe."),
    _s("HTTP URLs in sitemap.xml for HTTPS site", "Warnings", ("Sitemap HTTP locs",), "Requires sitemap loc scheme audit."),
    _s("Uncompressed pages", "Warnings", ("HTML compression",), "Requires Content-Encoding header check."),
    _s("Issues with blocked internal resources in robots.txt", "Warnings", ("Robots blocked internal resources",), "Requires robots vs resource cross-reference."),
    _s("Issues with uncompressed JavaScript and CSS files", "Warnings", ("Uncompressed assets", "Render-blocking resources"), "PSI partial coverage only."),
    _s("Issues with uncached JavaScript and CSS files", "Warnings", ("Uncached assets",), "Requires Cache-Control on assets."),
    _s("Pages have JS/CSS total size too large", "Warnings", ("JS CSS total size PSI", "Third-party script impact"), "PSI partial coverage only."),
    _s("Pages use too many JavaScript and CSS files", "Warnings", ("Script stylesheet count",), "Requires script/stylesheet count."),
    _s("Issues with unminified JavaScript and CSS files", "Warnings", ("Unminified assets PSI", "Render-blocking resources"), "PSI audit partial coverage."),
    _s("Link URLs are too long", "Warnings", ("URL structure",), "Checks page URL length, not link href length."),
    _s("Pages have more than one H1 tag", "Notices", ("Heading hierarchy",), "Not calculated on this audit."),
    _s("Llms.txt not found", "Notices", ("llms.txt",), "Not calculated on this audit."),
    _s("Pages are blocked from crawling", "Notices", ("Meta robots", "robots.txt"), "Not calculated on this audit."),
    _s("Page URLs are longer than 200 characters", "Notices", ("URL structure",), "App uses 115-char threshold."),
    _s("Outgoing external links contain nofollow attributes", "Notices", ("External nofollow links",), "Requires external rel=nofollow parse."),
    _s("Robots.txt not found", "Notices", ("robots.txt",), "Not calculated on this audit."),
    _s("Pages have hreflang language mismatch issues", "Notices", ("hreflang",), "Requires full language mismatch check."),
    _s("Subdomains don't support HSTS", "Notices", ("HTTPS / SSL",), "HSTS checked on audited page only."),
    _s("Orphaned pages in Google Analytics", "Notices", ("GA4 orphaned pages",), "Requires GA4 page inventory vs crawl graph."),
    _s("Orphaned pages in sitemaps", "Notices", ("Orphaned sitemap pages",), "Requires site-wide inlink graph."),
    _s("Pages blocked by X-Robots-Tag: noindex HTTP header", "Notices", ("Meta robots",), "Not calculated on this audit."),
    _s("Issues with blocked external resources in robots.txt", "Notices", ("Robots blocked external resources",), "Requires external resource robots cross-ref."),
    _s("Issues with broken external JavaScript and CSS files", "Notices", ("Broken external assets",), "Requires external asset status checks."),
    _s("Pages need more than 3 clicks to be reached", "Notices", ("Crawl depth",), "Shallow crawl (~25 pages) only."),
    _s("Pages have only one incoming internal link", "Notices", ("Internal inlink count",), "Requires site-wide inlink counts."),
    _s("URLs with a permanent redirect", "Notices", ("HTTP status & redirects",), "Single-URL redirect check only."),
    _s("Resources are formatted as page link", "Notices", ("Resource page links",), "Requires MIME type vs anchor check."),
    _s("Links on this page have no anchor text", "Notices", ("Internal links + anchor text",), "Descriptive % heuristic only."),
    _s("Links have non-descriptive anchor text", "Notices", ("Internal links + anchor text",), "Descriptive % heuristic only."),
    _s("Links to external pages returned 403 HTTP status", "Notices", ("External link 403",), "Requires external link 403 monitoring."),
    _s("Llms.txt has formatting issues", "Notices", ("llms.txt",), "Existence check only; no format validation."),
    _s("Pages contain too much content", "Notices", ("Excessive word count",), "Requires upper word-count threshold."),
    _s("Pages have outdated content", "Notices", ("Content freshness signals",), "Date regex heuristic only."),
    _s("Pages have low semantic HTML usage", "Notices", ("Semantic HTML",), "Not calculated on this audit."),
    _s("Pages require content optimization", "Notices", ("Word count / content depth",), "No SEO GEO Auditor optimization score."),
]

AI_SEARCH_OVERVIEW_PARAMS: list[RefParameter] = [
    _a("AI Search Health score (percentage)", ("AI Search Health score",), "Five-pillar AI Search Health model from crawl + GEO agents."),
    _a("Crawled pages stats (Blocked/Redirect/Broken/Healthy)", ("Crawl status inventory",), "Shallow-crawl page status breakdown in AI Overview PDF."),
    _a("Pages blocked from AI search (aggregate %)", ("AI blocked pages aggregate",), "Aggregate % of crawled pages blocked for major AI bots via robots.txt."),
    _a("ChatGPT-User bot blocking", ("ChatGPT-User bot blocking",), "Parsed from robots.txt User-agent rules."),
    _a("OAI-SearchBot bot blocking", ("OAI-SearchBot bot blocking",), "Parsed from robots.txt User-agent rules."),
    _a("Googlebot blocking", ("Googlebot blocking",), "Parsed from robots.txt User-agent rules."),
    _a("Google-Extended bot blocking", ("Google-Extended bot blocking",), "Parsed from robots.txt User-agent rules."),
    _a("PerplexityBot bot blocking", ("PerplexityBot bot blocking",), "Parsed from robots.txt User-agent rules."),
    _a("Perplexity-User bot blocking", ("Perplexity-User bot blocking",), "Parsed from robots.txt User-agent rules."),
    _a("Claude-User bot blocking", ("Claude-User bot blocking",), "Parsed from robots.txt User-agent rules."),
    _a("Claude-SearchBot bot blocking", ("Claude-SearchBot bot blocking",), "Parsed from robots.txt User-agent rules."),
    _a("Top Issues list (Errors/Warnings dashboard)", ("Site Health score",), "Not Meeting rows from resolved AI Overview catalog."),
]

CATALOG_BY_PDF: dict[str, list[RefParameter]] = {
    "performance_baseline": BASELINE_PARAMS,
    "site_audit_full": SITE_AUDIT_FULL_PARAMS,
    "ai_search_overview": AI_SEARCH_OVERVIEW_PARAMS,
}

PDF_TITLES: dict[str, str] = {
    "performance_baseline": "Performance Baseline — Traffic, Engagement, SEO & Web Vitals",
    "site_audit_full": "Heuristics AI — Full Site Audit",
    "ai_search_overview": "Heuristics AI — AI Search Overview",
}

PDF_FILENAMES: dict[str, str] = {
    "performance_baseline": "performance-baseline",
    "site_audit_full": "heuristics-full-site-audit",
    "ai_search_overview": "heuristics-ai-search-overview",
}
