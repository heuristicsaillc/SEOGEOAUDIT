"""HeuristicsAI Full Site Audit supplementary checks (crawl/GSC/PSI; no GA4).

These parameters populate the HeuristicsAI site audit PDF manual appendix.
Category weight is zero so they do not affect the main SEO score.
"""

from __future__ import annotations

from urllib.parse import urlparse

from app.agents.base import AgentContext, BaseAgent, audit_score, manual, not_measured, scored
from app.agents.geo_agents import AiBotCrawlabilityAgent
from app.crawl import registrable_host
from app.internal_link_distribution import (
    compute_internal_link_distribution,
    count_single_inlink_pages,
)
from app.models import DetectionMethod, ParameterResult, Rating

_W = 0.0  # Exclude from category scoring denominator impact


class SiteAuditSupplementAgent(BaseAgent):
    """Crawl-derived checks mapped to HeuristicsAI Full Site Audit parameters."""

    key = "site_audit_supplement"
    title = "Site Audit Supplementary Checks"
    kind = "seo"
    weight = 0.0

    async def analyze(self, ctx: AgentContext) -> list[ParameterResult]:
        page = ctx.page
        soup = page.soup
        results: list[ParameterResult] = []

        # --- Tier A: single-page HTML checks ---
        results.append(
            scored(
                "Meta refresh tag",
                "No meta http-equiv=refresh redirects",
                meeting=not page.has_meta_refresh,
                method=DetectionMethod.CRAWL,
                detail="present" if page.has_meta_refresh else "absent",
                weight=_W,
            )
        )
        results.append(
            scored(
                "Character encoding",
                "Charset declared in meta or Content-Type header",
                meeting=page.has_charset,
                method=DetectionMethod.CRAWL,
                detail=f"content-type={page.header('content-type') or 'missing'}",
                weight=_W,
            )
        )
        results.append(
            scored(
                "DOCTYPE",
                "HTML document declares a DOCTYPE",
                meeting=page.has_doctype,
                method=DetectionMethod.CRAWL,
                weight=_W,
            )
        )
        plugin_tags = {"object", "embed"}
        has_plugins = bool(soup and soup.find(plugin_tags)) if soup else False
        results.append(
            scored(
                "Plugin content",
                "No legacy object/embed plugin content",
                meeting=not has_plugins,
                method=DetectionMethod.CRAWL,
                weight=_W,
            )
        )
        has_frames = bool(soup and soup.find(["frame", "iframe", "frameset"])) if soup else False
        results.append(
            scored(
                "Frame tags",
                "No frame/iframe layout tags",
                meeting=not has_frames,
                method=DetectionMethod.CRAWL,
                weight=_W,
            )
        )
        h1_text = (page.headings.get("h1") or [""])[0].strip().lower()
        title_text = page.title.strip().lower()
        dup_h1_title = bool(h1_text and title_text and h1_text == title_text)
        results.append(
            scored(
                "Duplicate H1 and title",
                "H1 text differs from the title tag",
                meeting=not dup_h1_title,
                partial=dup_h1_title,
                method=DetectionMethod.CRAWL,
                detail=f"h1='{(page.headings.get('h1') or [''])[0][:80]}'",
                weight=_W,
            )
        )
        link_count = len(page.links)
        results.append(
            scored(
                "On-page link count",
                "Fewer than 3000 on-page links",
                meeting=link_count < 3000,
                partial=3000 <= link_count < 5000,
                method=DetectionMethod.CRAWL,
                detail=f"links={link_count}",
                weight=_W,
            )
        )
        text_bytes = len((page.visible_text or "").encode("utf-8"))
        html_bytes = max(page.html_byte_size, len((page.html or page.raw_html or "").encode("utf-8")))
        ratio = (text_bytes / html_bytes) if html_bytes else 0.0
        results.append(
            scored(
                "Text-HTML ratio",
                "Visible text is at least 10% of HTML size",
                meeting=ratio >= 0.10,
                partial=0.05 <= ratio < 0.10,
                method=DetectionMethod.CRAWL,
                detail=f"ratio={ratio:.2%}, text_bytes={text_bytes}, html_bytes={html_bytes}",
                weight=_W,
            )
        )
        results.append(
            scored(
                "Excessive word count",
                "Page word count below 5000 words",
                meeting=page.word_count <= 5000,
                partial=5000 < page.word_count <= 8000,
                method=DetectionMethod.CRAWL,
                detail=f"words={page.word_count}",
                weight=_W,
            )
        )
        internal_nofollow = [l for l in page.internal_links if "nofollow" in l.rel.lower()]
        results.append(
            scored(
                "Internal nofollow links",
                "Internal links should not use rel=nofollow",
                meeting=len(internal_nofollow) == 0,
                partial=0 < len(internal_nofollow) <= 3,
                method=DetectionMethod.CRAWL,
                detail=f"count={len(internal_nofollow)}",
                weight=_W,
            )
        )
        external_nofollow = [l for l in page.outbound_links if "nofollow" in l.rel.lower()]
        results.append(
            scored(
                "External nofollow links",
                "Document whether external links use rel=nofollow",
                meeting=True,
                partial=len(external_nofollow) > 0,
                method=DetectionMethod.CRAWL,
                detail=f"count={len(external_nofollow)}",
                weight=_W,
            )
        )
        encoding = (page.content_encoding or "").lower()
        compressed = encoding in ("gzip", "br", "deflate")
        results.append(
            scored(
                "HTML compression",
                "HTML response uses Content-Encoding compression",
                meeting=compressed,
                method=DetectionMethod.CRAWL,
                detail=f"encoding={page.content_encoding or 'none'}",
                weight=_W,
            )
        )
        asset_count = len(page.script_urls) + len(page.stylesheet_urls)
        results.append(
            scored(
                "Script stylesheet count",
                "Fewer than 50 JS/CSS file references",
                meeting=asset_count < 50,
                partial=50 <= asset_count < 80,
                method=DetectionMethod.CRAWL,
                detail=f"count={asset_count}",
                weight=_W,
            )
        )
        results.append(
            scored(
                "HTML byte size",
                "HTML payload below 2 MB",
                meeting=page.html_byte_size < 2_000_000,
                partial=2_000_000 <= page.html_byte_size < 3_000_000,
                method=DetectionMethod.CRAWL,
                detail=f"bytes={page.html_byte_size}",
                weight=_W,
            )
        )

        # --- Tier B: asset and link probes ---
        page_host = registrable_host(urlparse(page.final_url or page.url).netloc)
        broken_internal_images = [
            url
            for url, status in page.image_status.items()
            if status >= 400 and registrable_host(urlparse(url).netloc) == page_host
        ]
        broken_external_images = [
            url
            for url, status in page.image_status.items()
            if status >= 400 and registrable_host(urlparse(url).netloc) != page_host
        ]
        results.append(
            scored(
                "Broken internal images",
                "All internal image URLs return HTTP < 400",
                meeting=len(broken_internal_images) == 0,
                partial=0 < len(broken_internal_images) <= 2,
                method=DetectionMethod.CRAWL,
                detail=f"broken={len(broken_internal_images)}",
                evidence={"sample": broken_internal_images[:3]},
                weight=_W,
            )
        )
        results.append(
            scored(
                "Broken external images",
                "External image URLs return HTTP < 400",
                meeting=len(broken_external_images) == 0,
                partial=0 < len(broken_external_images) <= 2,
                method=DetectionMethod.CRAWL,
                detail=f"broken={len(broken_external_images)}",
                weight=_W,
            )
        )
        broken_internal_assets = [
            url
            for url, status in page.asset_status.items()
            if status >= 400 and registrable_host(urlparse(url).netloc) == page_host
        ]
        broken_external_assets = [
            url
            for url, status in page.asset_status.items()
            if status >= 400 and registrable_host(urlparse(url).netloc) != page_host
        ]
        results.append(
            scored(
                "Broken internal assets",
                "Internal JS/CSS assets return HTTP < 400",
                meeting=len(broken_internal_assets) == 0,
                partial=0 < len(broken_internal_assets) <= 2,
                method=DetectionMethod.CRAWL,
                detail=f"broken={len(broken_internal_assets)}",
                weight=_W,
            )
        )
        results.append(
            scored(
                "Broken external assets",
                "External JS/CSS assets return HTTP < 400",
                meeting=len(broken_external_assets) == 0,
                partial=0 < len(broken_external_assets) <= 2,
                method=DetectionMethod.CRAWL,
                detail=f"broken={len(broken_external_assets)}",
                weight=_W,
            )
        )
        uncached = [
            url
            for url, cache in page.asset_cache.items()
            if not cache or "max-age=0" in cache.lower() or cache.lower() == "no-cache"
        ]
        results.append(
            scored(
                "Uncached assets",
                "JS/CSS assets have Cache-Control max-age",
                meeting=len(uncached) == 0,
                partial=0 < len(uncached) <= 5,
                method=DetectionMethod.CRAWL,
                detail=f"uncached={len(uncached)}",
                weight=_W,
            )
        )
        uncompressed_assets = [
            url
            for url, enc in page.asset_encoding.items()
            if page.asset_status.get(url, 0) < 400
            and (enc or "").lower() not in ("gzip", "br", "deflate")
        ]
        results.append(
            scored(
                "Uncompressed assets",
                "JS/CSS assets served with Content-Encoding compression",
                meeting=len(uncompressed_assets) == 0,
                partial=0 < len(uncompressed_assets) <= 5,
                method=DetectionMethod.CRAWL,
                detail=f"uncompressed={len(uncompressed_assets)}",
                weight=_W,
            )
        )
        external_403 = [url for url, status in page.external_link_status.items() if status == 403]
        results.append(
            scored(
                "External link 403",
                "External links do not return HTTP 403",
                meeting=len(external_403) == 0,
                method=DetectionMethod.CRAWL,
                detail=f"count={len(external_403)}",
                weight=_W,
            )
        )
        results.append(
            scored(
                "Malformed link URLs",
                "All anchor hrefs are valid http(s) URLs",
                meeting=len(page.malformed_links) == 0,
                method=DetectionMethod.CRAWL,
                detail=f"count={len(page.malformed_links)}",
                weight=_W,
            )
        )
        crawl_errors = [f for f in page.crawl_failures if f.get("reason") != "unreachable" or not page.dns_ok]
        results.append(
            scored(
                "Crawl failures",
                "Sampled internal URLs are reachable",
                meeting=len(page.crawl_failures) == 0,
                partial=0 < len(page.crawl_failures) <= 3,
                method=DetectionMethod.CRAWL,
                detail=f"failures={len(page.crawl_failures)}",
                evidence={"sample": page.crawl_failures[:3]},
                weight=_W,
            )
        )
        results.append(
            scored(
                "DNS resolution",
                "Primary host resolves via DNS",
                meeting=page.dns_ok,
                method=DetectionMethod.CRAWL,
                weight=_W,
            )
        )
        results.append(
            scored(
                "Robots blocked internal resources",
                "robots.txt does not block internal JS/CSS/images",
                meeting=len(page.robots_blocked_internal) == 0,
                method=DetectionMethod.CRAWL,
                detail=f"blocked={len(page.robots_blocked_internal)}",
                weight=_W,
            )
        )
        results.append(
            scored(
                "Robots blocked external resources",
                "robots.txt does not block third-party assets",
                meeting=len(page.robots_blocked_external) == 0,
                method=DetectionMethod.CRAWL,
                detail=f"blocked={len(page.robots_blocked_external)}",
                weight=_W,
            )
        )

        # --- Tier C: TLS / WWW / sitemap ---
        results.append(
            scored(
                "WWW resolve",
                "www and non-www hostnames resolve to the same site",
                meeting=page.www_resolve_ok,
                method=DetectionMethod.CRAWL,
                weight=_W,
            )
        )
        cert_ok = page.tls_cert_hostname_ok and (
            page.tls_cert_days_remaining is None or page.tls_cert_days_remaining > 0
        )
        cert_partial = page.tls_cert_hostname_ok and (
            page.tls_cert_days_remaining is not None and 0 < page.tls_cert_days_remaining <= 30
        )
        results.append(
            scored(
                "Certificate hostname",
                "TLS certificate CN/SAN matches hostname; not expired",
                meeting=cert_ok and not cert_partial,
                partial=cert_partial,
                method=DetectionMethod.CRAWL,
                detail=f"hostname_ok={page.tls_cert_hostname_ok}, days={page.tls_cert_days_remaining}",
                weight=_W,
            )
        )
        tls_ok = page.tls_version in ("TLSv1.2", "TLSv1.3") if page.tls_version else page.tls_ok
        results.append(
            scored(
                "TLS protocol version",
                "TLS 1.2 or newer negotiated",
                meeting=tls_ok,
                partial=page.tls_version in ("TLSv1.1",) if page.tls_version else False,
                method=DetectionMethod.CRAWL,
                detail=f"version={page.tls_version or 'unknown'}",
                weight=_W,
            )
        )
        weak_cipher_hosts = [
            row["host"] for row in page.tls_hosts if row.get("weak_cipher") and not row.get("error")
        ]
        results.append(
            scored(
                "TLS subdomain ciphers",
                "Discovered subdomains use TLS 1.2+ and strong cipher suites",
                meeting=len(weak_cipher_hosts) == 0,
                partial=0 < len(weak_cipher_hosts) <= 1,
                method=DetectionMethod.CRAWL,
                detail=f"weak_hosts={weak_cipher_hosts[:5]}",
                evidence={"hosts": weak_cipher_hosts[:5]},
                weight=_W,
            )
        )
        sni_bad_hosts = [
            row["host"] for row in page.tls_hosts if row.get("sni_ok") is False and not row.get("error")
        ]
        results.append(
            scored(
                "TLS subdomain SNI",
                "Discovered subdomains support SNI for virtual-host TLS",
                meeting=len(sni_bad_hosts) == 0,
                partial=0 < len(sni_bad_hosts) <= 1,
                method=DetectionMethod.CRAWL,
                detail=f"sni_issues={sni_bad_hosts[:5]}",
                evidence={"hosts": sni_bad_hosts[:5]},
                weight=_W,
            )
        )
        results.append(
            scored(
                "Resource page links",
                "Binary/media files are not linked via plain anchor tags",
                meeting=len(page.resource_page_links) == 0,
                method=DetectionMethod.CRAWL,
                detail=f"count={len(page.resource_page_links)}",
                evidence={"sample": page.resource_page_links[:5]},
                weight=_W,
            )
        )
        sitemap = page.sitemap
        results.append(
            scored(
                "Sitemap size limit",
                "Sitemap contains fewer than 50,000 URLs",
                meeting=not sitemap.exists or sitemap.url_count < 50_000,
                method=DetectionMethod.CRAWL,
                detail=f"urls={sitemap.url_count}",
                weight=_W,
            )
        )
        results.append(
            scored(
                "Sitemap HTTP locs",
                "HTTPS sites use https:// locs in sitemap.xml",
                meeting=sitemap.http_loc_count == 0,
                method=DetectionMethod.CRAWL,
                detail=f"http_locs={sitemap.http_loc_count}",
                weight=_W,
            )
        )
        bad_sitemap = [
            url for url, status in sitemap.loc_status.items() if status == 0 or status >= 400
        ]
        results.append(
            scored(
                "Sitemap URL validation",
                "Sampled sitemap URLs return HTTP 200",
                meeting=len(bad_sitemap) == 0,
                partial=0 < len(bad_sitemap) <= 3,
                method=DetectionMethod.CRAWL,
                detail=f"bad={len(bad_sitemap)}",
                weight=_W,
            )
        )

        # --- Tier D: orphaned sitemap pages (GSC enrichment when connected) ---
        orphaned = list(page.orphaned_sitemap_pages)
        if ctx.is_connected and ctx.connection:
            gsc_site = ctx.connection.get("gsc_site_url", "")
            if gsc_site and ctx.clients.gsc.enabled:
                gsc_result = await ctx.clients.gsc.search_analytics_report(
                    gsc_site,
                    dimensions=["page"],
                    row_limit=100,
                    days=90,
                )
                if gsc_result.ok:
                    gsc_pages = {row["keys"][0].rstrip("/") for row in gsc_result.data if row.get("keys")}
                    reachable = {u.rstrip("/") for u in page.internal_depths}
                    for loc in sitemap.locs[:100]:
                        norm = loc.rstrip("/")
                        if norm in gsc_pages and norm not in reachable and loc not in orphaned:
                            orphaned.append(loc)
        results.append(
            scored(
                "Orphaned sitemap pages",
                "Sitemap URLs have internal inlinks or GSC impressions",
                meeting=len(orphaned) == 0,
                partial=0 < len(orphaned) <= 5,
                method=DetectionMethod.FIRST_PARTY if ctx.is_connected else DetectionMethod.CRAWL,
                detail=f"orphaned={len(orphaned)}",
                evidence={"sample": orphaned[:5]},
                weight=_W,
            )
        )

        # --- Tier E: PSI fallbacks for asset optimization rows ---
        psi = page.psi_mobile
        if psi:
            unmin_js = audit_score(psi, "unminified-javascript")
            unmin_css = audit_score(psi, "unminified-css")
            results.append(
                scored(
                    "Unminified assets PSI",
                    "PSI reports no unminified JS/CSS",
                    meeting=(unmin_js is None or unmin_js >= 0.9) and (unmin_css is None or unmin_css >= 0.9),
                    partial=(unmin_js is not None and unmin_js < 0.9) or (unmin_css is not None and unmin_css < 0.9),
                    method=DetectionMethod.PSI,
                    detail=f"js={unmin_js}, css={unmin_css}",
                    weight=_W,
                )
            )
            unused_js = audit_score(psi, "unused-javascript")
            results.append(
                scored(
                    "JS CSS total size PSI",
                    "PSI unused JavaScript score acceptable",
                    meeting=unused_js is None or unused_js >= 0.5,
                    partial=unused_js is not None and unused_js < 0.5,
                    method=DetectionMethod.PSI,
                    detail=f"unused_js={unused_js}",
                    weight=_W,
                )
            )
        else:
            results.append(
                not_measured(
                    "Unminified assets PSI",
                    "PSI unavailable for unminified asset check",
                    weight=_W,
                )
            )
            results.append(
                not_measured(
                    "JS CSS total size PSI",
                    "PSI unavailable for JS/CSS size check",
                    weight=_W,
                )
            )

        # --- AMP canonical (when AMP markup present) ---
        head = (page.html or "")[:5000].lower()
        is_amp = "<html amp" in head or "amphtml" in head
        amp_canonical_ok = True
        if is_amp and soup:
            amp_canonical_ok = bool(soup.find("link", rel=lambda v: v and "canonical" in v.lower()))
        results.append(
            scored(
                "AMP canonical tag",
                "AMP pages declare a canonical link to the non-AMP URL",
                meeting=not is_amp or amp_canonical_ok,
                partial=False,
                method=DetectionMethod.CRAWL,
                detail="no AMP markup" if not is_amp else f"canonical={'yes' if amp_canonical_ok else 'no'}",
                weight=_W,
            )
        )

        # --- HTTP homepage must resolve to HTTPS ---
        results.append(
            scored(
                "HTTP homepage HTTPS redirect",
                "HTTP homepage redirects or canonicals to HTTPS",
                meeting=page.http_homepage_https_ok,
                method=DetectionMethod.CRAWL,
                detail=page.http_homepage_detail or "ok",
                weight=_W,
            )
        )

        # --- Title length across shallow crawl ---
        short_titles = [url for url, title in page.crawled_titles.items() if len(title) < 30]
        long_titles = [url for url, title in page.crawled_titles.items() if len(title) > 60]
        results.append(
            scored(
                "Title too short",
                "Title tags are at least 30 characters on crawled pages",
                meeting=len(short_titles) == 0,
                partial=0 < len(short_titles) <= 2,
                method=DetectionMethod.CRAWL,
                detail=f"short={len(short_titles)}",
                evidence={"sample": short_titles[:5]},
                weight=_W,
            )
        )
        results.append(
            scored(
                "Title too long",
                "Title tags are at most 60 characters on crawled pages",
                meeting=len(long_titles) == 0,
                partial=0 < len(long_titles) <= 2,
                method=DetectionMethod.CRAWL,
                detail=f"long={len(long_titles)}",
                evidence={"sample": long_titles[:5]},
                weight=_W,
            )
        )

        # --- Internal link distribution (overview chart data) ---
        crawled_urls = list(page.internal_depths.keys())
        buckets = compute_internal_link_distribution(crawled_urls, page.internal_inlink_counts)
        single_inlink = count_single_inlink_pages(crawled_urls, page.internal_inlink_counts)
        results.append(
            scored(
                "Internal link distribution",
                "Incoming internal link counts bucketed across crawled pages",
                meeting=True,
                method=DetectionMethod.CRAWL,
                detail=f"crawled={len(crawled_urls)}",
                evidence={"buckets": buckets, "total_pages": len(crawled_urls)},
                weight=_W,
            )
        )
        results.append(
            scored(
                "Internal inlink count",
                "Crawled pages with only one incoming internal link",
                meeting=single_inlink == 0,
                partial=0 < single_inlink <= 5,
                method=DetectionMethod.CRAWL,
                detail=f"single_inlink_pages={single_inlink}",
                evidence={"count": single_inlink},
                weight=_W,
            )
        )

        # --- GA4 orphaned pages (sessions but no internal inlinks in crawl graph) ---
        ga_orphans: list[str] = []
        ga_detail = "orphans=0"
        if ctx.is_connected and ctx.connection:
            prop = ctx.connection.get("ga4_property_id", "")
            if prop and ctx.clients.ga4.enabled:
                inventory = await ctx.clients.ga4.fetch_page_inventory(prop)
                reachable_paths: set[str] = set()
                for url in page.internal_depths:
                    path = urlparse(url).path or "/"
                    base = path.rstrip("/") or "/"
                    reachable_paths.update({base, base + "/", path, path.rstrip("/") + "/"})
                for row in inventory:
                    path = row.get("pagePath", "")
                    try:
                        sessions = int(float(row.get("sessions", 0)))
                    except (TypeError, ValueError):
                        sessions = 0
                    if sessions <= 0:
                        continue
                    norm = path.rstrip("/") or "/"
                    if norm not in reachable_paths and path not in reachable_paths:
                        ga_orphans.append(path)
                ga_detail = f"orphans={len(ga_orphans)}"
            else:
                ga_detail = "GA4 client not configured"
        else:
            results.append(
                manual(
                    "GA4 orphaned pages",
                    "GA4 pages with sessions are reachable via internal crawl",
                    "Requires Connected Mode GA4 property for page inventory",
                )
            )
            ga_orphans = None

        if ga_orphans is not None:
            results.append(
                scored(
                    "GA4 orphaned pages",
                    "GA4 pages with sessions are reachable via internal crawl",
                    meeting=len(ga_orphans) == 0,
                    partial=0 < len(ga_orphans) <= 5,
                    method=DetectionMethod.FIRST_PARTY,
                    detail=ga_detail,
                    evidence={"sample": ga_orphans[:5], "count": len(ga_orphans)},
                    weight=_W,
                )
            )

        # --- Site-wide health score (zero-weight, for AI overview PDF) ---
        issue_count = sum(
            1
            for r in results
            if r.rating in (Rating.NOT_MEETING, Rating.PARTIAL)
        )
        crawled = max(1, len(page.internal_depths))
        broken = sum(
            1
            for status in page.crawl_page_status.values()
            if status == 0 or status >= 500
        )
        redirected = sum(1 for status in page.crawl_page_status.values() if 300 <= status < 400)
        have_issues = min(crawled, issue_count)
        healthy = max(0, crawled - broken - have_issues)
        results.append(
            scored(
                "Crawl status inventory",
                "Blocked/redirect/broken/healthy counts across shallow crawl",
                meeting=True,
                method=DetectionMethod.CRAWL,
                detail=(
                    f"crawled={crawled}; healthy={healthy}; broken={broken}; "
                    f"redirected={redirected}; have_issues={have_issues}"
                ),
                evidence={
                    "crawled": crawled,
                    "healthy": healthy,
                    "broken": broken,
                    "redirected": redirected,
                    "have_issues": have_issues,
                },
                weight=_W,
            )
        )

        groups = AiBotCrawlabilityAgent._parse_robots(page.robots_txt)
        major_blocked = [
            bot
            for bot in ("GPTBot", "ClaudeBot", "PerplexityBot")
            if AiBotCrawlabilityAgent._blocked(groups, bot)
        ]
        blocked_pages = crawled if major_blocked else 0
        meta = (page.meta_robots or "").lower()
        if not blocked_pages and ("noindex" in meta or "noai" in meta):
            blocked_pages = 1
        blocked_pct = (blocked_pages / crawled * 100.0) if crawled else 0.0
        results.append(
            scored(
                "AI blocked pages aggregate",
                "Share of crawled pages blocked from major AI crawlers",
                meeting=blocked_pages == 0,
                partial=0 < blocked_pages < crawled,
                method=DetectionMethod.CRAWL,
                detail=f"blocked={blocked_pages}; crawled={crawled}; pct={blocked_pct:.1f}%",
                evidence={
                    "blocked": blocked_pages,
                    "crawled": crawled,
                    "pct": round(blocked_pct, 1),
                    "bots": major_blocked,
                },
                weight=_W,
            )
        )

        site_health = max(0.0, min(100.0, 100.0 - (issue_count / crawled) * 100.0))
        results.append(
            scored(
                "Site Health score",
                "Site-wide issue density across shallow crawl",
                meeting=site_health >= 90,
                partial=70 <= site_health < 90,
                method=DetectionMethod.CRAWL,
                detail=f"score={site_health:.0f}%; issues={issue_count}; crawled={crawled}",
                evidence={"score": site_health, "crawled": crawled},
                weight=_W,
            )
        )

        return results
