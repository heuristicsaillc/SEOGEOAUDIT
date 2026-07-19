"""Developer-facing fix guidance: where to change and what to change.

Enrich ParameterResult rows so every PDF can show concrete engineering guidance
instead of a one-line recommendation.
"""

from __future__ import annotations

from urllib.parse import urljoin, urlparse

from app.models import ParameterResult, Rating, Report


# Parameter name -> (where template, change template).
# Templates may include {origin}, {page}, {host}, {path}.
_FIX_CATALOG: dict[str, tuple[str, str]] = {
    "robots.txt": (
        "{origin}/robots.txt (or your CMS/host robots editor)",
        "Publish a valid robots.txt that allows key pages and includes a Sitemap: line "
        "pointing to your XML sitemap. Remove blanket Disallow: / unless intentional.",
    ),
    "sitemap.xml": (
        "{origin}/sitemap.xml or the Sitemap: URL in robots.txt (often /sitemap_index.xml)",
        "Publish an XML sitemap (or sitemap index) listing canonical HTTPS URLs with "
        "<lastmod> dates. Ensure Cloudflare/WAF allows crawlers to fetch the XML "
        "(HTTP 200, application/xml — not a JS challenge page).",
    ),
    "XML sitemap index": (
        "Sitemap index URL declared in robots.txt (e.g. {origin}/sitemap_index.xml)",
        "For larger sites, use a <sitemapindex> that points to typed child sitemaps "
        "(pages/posts/images). Keep each child under 50k URLs.",
    ),
    "sitemap GSC-submission status": (
        "Google Search Console → Indexing → Sitemaps for the property",
        "Submit the exact XML sitemap URL (not the homepage). Fix any GSC sitemap errors "
        "so the submitted URL returns XML.",
    ),
    "Sitemap URL validation": (
        "URLs listed in your XML sitemap <loc> entries",
        "Remove or fix sitemap locs that return 4xx/5xx. Every <loc> should resolve to "
        "the canonical live page.",
    ),
    "Sitemap HTTP locs": (
        "XML sitemap <loc> values",
        "Rewrite http:// locs to https:// canonical URLs to match the live site.",
    ),
    "Sitemap size limit": (
        "XML sitemap file(s) on the origin / CMS sitemap settings",
        "Split sitemaps over 50,000 URLs (or ~50MB) into multiple files referenced by a sitemap index.",
    ),
    "Orphaned sitemap pages": (
        "Pages listed in the sitemap but missing internal links",
        "Add contextual internal links from relevant hub pages, or remove obsolete URLs from the sitemap.",
    ),
    "Meta robots": (
        "HTML <head> on {page} (or X-Robots-Tag response header from the server/CDN)",
        "Remove unintended noindex/nofollow. Keep index,follow for pages that should rank.",
    ),
    "noarchive / nosnippet": (
        "HTML <head> meta robots / googlebot on {page}, or X-Robots-Tag header",
        "Remove noarchive/nosnippet unless you intentionally want to suppress snippets/cache.",
    ),
    "HTTP status & redirects": (
        "Server/CDN redirect rules and the response for {page}",
        "Serve the canonical URL with HTTP 200. Collapse redirect chains to a single hop to HTTPS canonical.",
    ),
    "Canonical tags": (
        "HTML <head> on {page}: <link rel=\"canonical\">",
        "Add one absolute HTTPS canonical pointing to the preferred URL for this page.",
    ),
    "Title tag": (
        "HTML <head> on {page}: <title>",
        "Set a unique, descriptive title (~50–60 characters) that matches the primary intent.",
    ),
    "Title too long": (
        "HTML <head> on {page}: <title>",
        "Shorten the title so it is not truncated in SERPs (aim ≤60 characters).",
    ),
    "Title too short": (
        "HTML <head> on {page}: <title>",
        "Expand the title with a clear primary topic/benefit (aim ≥30 characters).",
    ),
    "Meta description": (
        "HTML <head> on {page}: <meta name=\"description\">",
        "Write a unique 150–160 character summary that encourages the click and matches intent.",
    ),
    "Heading hierarchy": (
        "HTML body headings on {page} (<h1>–<h6>)",
        "Use a single H1, then logical H2/H3 sections without skipping levels.",
    ),
    "Duplicate H1 and title": (
        "HTML <title> and <h1> on {page}",
        "Differentiate H1 from the title slightly while keeping the same primary topic.",
    ),
    "Mobile viewport": (
        "HTML <head> on {page}",
        "Add: <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">",
    ),
    "Image alt coverage": (
        "Image markup on {page} (<img alt=\"...\">) and CMS media fields",
        "Add concise, descriptive alt text for informative images; use empty alt=\"\" only for decorative images.",
    ),
    "Broken links": (
        "Anchor hrefs on {page} (and linked internal/external destinations)",
        "Update or remove links that return real 4xx/5xx (not bot-challenge blocks). Prefer stable canonical destinations.",
    ),
    "Pages returned 4XX status code": (
        "Internal URLs returning HTTP 4xx in the crawl sample",
        "Fix or redirect those URLs. Do not treat Cloudflare/bot-challenge 403s as site errors — those are verification limits.",
    ),
    "Pages returned 5XX status code": (
        "Internal URLs returning HTTP 5xx in the crawl sample",
        "Check origin/server logs and hosting/CDN errors for the listed URLs and restore HTTP 200 responses.",
    ),
    "Broken internal images": (
        "Image src URLs on {page} / media library",
        "Fix or replace image URLs returning errors; re-upload missing media.",
    ),
    "Broken external images": (
        "Hotlinked external image URLs on {page}",
        "Host critical images on your origin or replace dead third-party image URLs.",
    ),
    "Broken internal assets": (
        "JS/CSS asset URLs referenced by {page}",
        "Fix build/deploy paths so scripts and stylesheets return HTTP 200.",
    ),
    "Broken external assets": (
        "Third-party JS/CSS URLs on {page}",
        "Update or remove failing third-party asset URLs; prefer self-hosting critical assets.",
    ),
    "Uncached assets": (
        "CDN/server Cache-Control headers for JS/CSS/image assets",
        "Set long-lived cache headers (and fingerprint filenames) for static assets.",
    ),
    "Uncompressed assets": (
        "CDN/server compression (gzip/br) for text assets",
        "Enable Brotli or gzip for HTML/CSS/JS responses.",
    ),
    "HTML compression": (
        "Origin/CDN Content-Encoding for HTML responses",
        "Enable gzip/Brotli compression for HTML.",
    ),
    "HTML byte size": (
        "Page template / CMS content for {page}",
        "Reduce HTML weight (remove unused markup, defer non-critical widgets, paginate heavy lists).",
    ),
    "Server response time": (
        "Origin/hosting TTFB for {page}",
        "Improve server/TTFB (caching, leaner backend, closer edge, fewer blocking origin calls).",
    ),
    "HTTPS / SSL": (
        "TLS certificate and HTTPS redirect at the host/CDN for {host}",
        "Serve the site exclusively over HTTPS with a valid certificate covering the live hostname.",
    ),
    "HTTP homepage HTTPS redirect": (
        "Host/CDN redirect from http://{host}/ to https://{host}/",
        "301/308 redirect the HTTP homepage to the HTTPS canonical homepage.",
    ),
    "WWW resolve": (
        "DNS + CDN/host redirects between www and apex for {host}",
        "Pick one canonical host (www or apex) and 301 the other to it consistently.",
    ),
    "Certificate hostname": (
        "TLS certificate CN/SAN for {host}",
        "Reissue the certificate so it includes the live hostname (and www/apex variants you use).",
    ),
    "TLS protocol version": (
        "CDN/host TLS configuration for {host}",
        "Disable outdated TLS versions; allow TLS 1.2+ (prefer 1.3).",
    ),
    "Security headers": (
        "CDN/origin response headers for {page}",
        "Add security headers (at least HSTS where appropriate, plus nosniff / frame controls as needed).",
    ),
    "Schema.org JSON-LD": (
        "HTML <head> or end of <body> on {page}: <script type=\"application/ld+json\">",
        "Add valid JSON-LD for the page type (Organization/WebPage/Article/Product/FAQ as applicable).",
    ),
    "Breadcrumb schema": (
        "JSON-LD on {page}",
        "Add BreadcrumbList JSON-LD matching the visible breadcrumb trail.",
    ),
    "FAQ section": (
        "Page content + FAQPage JSON-LD on {page}",
        "Add a visible FAQ with clear Q/A pairs and matching FAQPage schema when appropriate.",
    ),
    "OG / Twitter cards": (
        "HTML <head> meta tags on {page}",
        "Add og:title, og:description, og:image, and twitter:card tags with absolute image URLs.",
    ),
    "llms.txt": (
        "{origin}/llms.txt",
        "Publish an llms.txt that summarizes the site for AI crawlers and links key content.",
    ),
    "llms-full.txt": (
        "{origin}/llms-full.txt",
        "Optionally publish llms-full.txt with expanded machine-readable site guidance.",
    ),
    "GPTBot / ClaudeBot / PerplexityBot": (
        "{origin}/robots.txt user-agent rules",
        "Allow major AI crawlers (GPTBot, ClaudeBot, PerplexityBot) unless there is a deliberate block policy.",
    ),
    "AI blocked pages aggregate": (
        "{origin}/robots.txt and page-level robots meta/X-Robots-Tag",
        "Stop blocking major AI bots site-wide; allow crawl/index of pages you want cited in AI answers.",
    ),
    "Publish + updated dates": (
        "Visible byline/date UI and Article/WebPage schema on {page}",
        "Show a clear published/updated date and mirror it in datePublished/dateModified JSON-LD.",
    ),
    "Author + credentials": (
        "Byline / author bio block on {page}",
        "Name the author and link to a credentials/bio page; add Person schema when possible.",
    ),
    "Concise top answer": (
        "Opening content block under the H1 on {page}",
        "Lead with a 40–60 word direct answer to the primary query before deeper detail.",
    ),
    "TL;DR / summary box": (
        "Top-of-page summary component on {page}",
        "Add a short TL;DR/summary box that states the answer and key takeaways.",
    ),
    "Lists & tables": (
        "Body content structure on {page}",
        "Convert dense prose into scannable lists/tables for extractable facts.",
    ),
    "Internal links + anchor text": (
        "In-content anchors on {page}",
        "Add descriptive internal links to related money/hub pages; avoid generic 'click here' anchors.",
    ),
    "Crawl depth": (
        "Internal linking / navigation IA site-wide",
        "Ensure important URLs are reachable within a few clicks from the homepage.",
    ),
    "JavaScript rendering": (
        "Frontend render strategy for {page}",
        "Server-render or prerender critical content so crawlers see primary text without executing JS.",
    ),
    "Lighthouse scores": (
        "Page experience / front-end performance for {page}",
        "Improve Lighthouse performance/accessibility/SEO audits (reduce JS, optimize images, fix a11y).",
    ),
    "Field data (CrUX)": (
        "Real-user CWV for the origin in Search Console / CrUX",
        "Improve LCP/INP/CLS site-wide (image priorities, less main-thread work, stable layouts).",
    ),
}


def _origin(page_url: str) -> str:
    parts = urlparse(page_url or "")
    if not parts.scheme or not parts.netloc:
        return ""
    return f"{parts.scheme}://{parts.netloc}"


def _host(page_url: str) -> str:
    return urlparse(page_url or "").netloc.lower()


def _format_template(template: str, *, page_url: str) -> str:
    origin = _origin(page_url) or page_url
    host = _host(page_url) or "your-domain"
    path = urlparse(page_url or "").path or "/"
    return template.format(origin=origin, page=page_url or origin, host=host, path=path)


def _sample_urls(param: ParameterResult, *, limit: int = 5) -> list[str]:
    evidence = param.evidence or {}
    for key in ("broken_sample", "sample", "urls", "pages", "locs"):
        value = evidence.get(key)
        if isinstance(value, list) and value:
            return [str(v) for v in value[:limit]]
        if isinstance(value, str) and value.startswith("http"):
            return [value]
    return []


def infer_fix_where(param: ParameterResult, *, page_url: str = "") -> str:
    """Infer a developer location for the change."""
    if param.fix_where:
        return param.fix_where
    page_url = page_url or ""
    catalog = _FIX_CATALOG.get(param.name)
    if catalog:
        return _format_template(catalog[0], page_url=page_url)

    name = param.name.lower()
    origin = _origin(page_url) or page_url or "the audited site"
    if "robots" in name:
        return f"{origin}/robots.txt"
    if "sitemap" in name:
        return f"{origin}/sitemap.xml (or Sitemap: URL in robots.txt)"
    if "llms" in name:
        return f"{origin}/llms.txt"
    if "schema" in name or "json-ld" in name:
        return f"JSON-LD on {page_url or origin}"
    if "meta" in name or "title" in name or "canonical" in name or "viewport" in name or "og /" in name:
        return f"HTML <head> on {page_url or origin}"
    if "header" in name or "tls" in name or "https" in name or "certificate" in name:
        return f"CDN/origin TLS & header config for {_host(page_url) or 'the site'}"
    if "image" in name or "asset" in name or "link" in name:
        samples = _sample_urls(param)
        if samples:
            return "Affected URLs: " + ", ".join(samples)
        return f"Page markup / linked resources on {page_url or origin}"
    return f"Page / template for {page_url or origin}"


def infer_fix_change(param: ParameterResult, *, page_url: str = "") -> str:
    """Infer a concrete change instruction."""
    if param.recommendation and not _looks_like_raw_evidence(param.recommendation):
        return param.recommendation
    catalog = _FIX_CATALOG.get(param.name)
    if catalog:
        return _format_template(catalog[1], page_url=page_url)
    if param.what_to_check:
        return f"Bring this in line with: {param.what_to_check}"
    return "Apply the SEO/GEO best practice for this parameter and re-audit the URL."


def _looks_like_raw_evidence(text: str) -> bool:
    """True when text is measurement noise rather than a developer instruction."""
    lowered = (text or "").strip().lower()
    if not lowered:
        return True
    if lowered.startswith(("exists=", "urls=", "blocked=", "score=", "ratio=", "count=")):
        return True
    if "=" in lowered and all(part for part in lowered.replace(";", ",").split(",") if "=" in part or not part.strip()):
        # detail-like key=value blobs
        if " " not in lowered.split("=", 1)[0]:
            return True
    return False


def developer_fix_text(param: ParameterResult, *, page_url: str = "") -> str:
    """Build a multi-line developer fix block for PDFs and UI."""
    if param.rating == Rating.MEETING:
        return ""
    where = infer_fix_where(param, page_url=page_url)
    change = infer_fix_change(param, page_url=page_url)
    lines = [f"Where: {where}", f"Change: {change}"]
    if param.detail and param.detail.strip() and param.detail.strip() != change:
        lines.append(f"Evidence: {param.detail.strip()}")
    samples = _sample_urls(param)
    if samples and "Affected URLs:" not in where:
        lines.append("Affected URLs: " + ", ".join(samples))
    if param.effort:
        lines.append(f"Effort: {param.effort}")
    return "\n".join(lines)


def enrich_parameter(param: ParameterResult, *, page_url: str = "") -> ParameterResult:
    """Fill fix_where and strengthen empty/weak recommendations in place."""
    if param.rating == Rating.MEETING:
        return param
    param.fix_where = infer_fix_where(param, page_url=page_url)
    if not param.recommendation or _looks_like_raw_evidence(param.recommendation):
        param.recommendation = infer_fix_change(param, page_url=page_url)
    return param


def enrich_report(report: Report, *, page_url: str = "") -> None:
    """Enrich every actionable parameter in a report."""
    for category in report.categories:
        for param in category.parameters:
            enrich_parameter(param, page_url=page_url)
