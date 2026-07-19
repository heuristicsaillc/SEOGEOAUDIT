"""All 7 SEO category agents.

Each class is a self-contained BaseAgent subclass; the orchestrator runs them concurrently.
"""
from __future__ import annotations  # Forward references for typing
import re  # Date/phone pattern detection
from urllib.parse import urlparse  # URL structure analysis
from app.agents.base import (  # Agent framework + every shared helper
    AgentContext,
    BaseAgent,
    scored,
    manual,
    not_measured,
    first_party_empty,
    llm_scored,
    audit_numeric,
    audit_score,
    category_score,
    crux_metric,
    jsonld_types,
    type_present,
    block_mentions,
)
from app.models import Confidence, DetectionMethod, Priority, ParameterResult  # Enums + result


# ============================================================================
# crawlability
# ============================================================================

class CrawlabilityAgent(BaseAgent):
    """Checks robots, sitemaps, indexability directives, redirects and crawl depth."""

    key = "crawlability"  # Stable category key
    title = "Crawlability & Indexability"  # Display title
    kind = "seo"  # Belongs to the SEO report
    weight = 1.2  # Slightly higher weight: indexability is foundational

    async def analyze(self, ctx: AgentContext) -> list[ParameterResult]:
        """Return all Crawlability & Indexability parameter rows."""
        page = ctx.page  # Shorthand for the page signals
        results: list[ParameterResult] = []  # Accumulate rows

        # --- robots.txt present and not blocking the page ---
        robots_blocks = self._robots_blocks_all(page.robots_txt)  # Does robots Disallow: / for all?
        results.append(
            scored(
                "robots.txt",  # Parameter name
                "Correct disallow rules; no accidental crawl blocks on key pages",  # What to check
                meeting=page.robots_exists and not robots_blocks,  # Present and not site-wide blocked
                method=DetectionMethod.CRAWL,  # Detected by fetching /robots.txt
                detail=f"robots.txt {'found' if page.robots_exists else 'missing'}; "
                f"site-wide block: {robots_blocks}",  # Evidence
                recommendation="Add a robots.txt that allows key pages and references your sitemap.",
                priority=Priority.HIGH,  # Crawl blocking is high impact
            )
        )

        # --- sitemap.xml present, valid, lastmod populated ---
        sm = page.sitemap  # Sitemap discovery result
        if sm.blocked:
            sm_detail = (
                f"exists={sm.exists}, urls={sm.url_count}, lastmod={sm.lastmod_count}, "
                f"blocked=True, {sm.block_detail or 'bot_protection'}"
            )
            sm_rec = (
                "Sitemap URL could not be fetched due to bot protection (e.g. Cloudflare). "
                "Allowlist the auditor or ensure sitemap XML is reachable without a JS challenge."
            )
        else:
            sm_detail = f"exists={sm.exists}, urls={sm.url_count}, lastmod={sm.lastmod_count}"
            sm_rec = "Publish a sitemap.xml listing canonical URLs with <lastmod> dates."
        results.append(
            scored(
                "sitemap.xml",  # Parameter name
                "Present; no 4xx/5xx URLs; lastmod populated",  # What to check
                meeting=sm.exists and sm.url_count > 0 and sm.lastmod_count > 0,  # Full pass
                partial=sm.exists and sm.url_count > 0 and sm.lastmod_count == 0,  # Present, no lastmod
                method=DetectionMethod.CRAWL,  # Detected by fetching the sitemap
                detail=sm_detail,  # Evidence
                recommendation=sm_rec,
                priority=Priority.HIGH,
            )
        )

        # --- sitemap GSC-submission status (connected => measured, else manual) ---
        results.append(await self._sitemap_gsc(ctx))  # Delegate to a helper (connected-mode aware)

        # --- Meta robots / X-Robots-Tag: no unintended noindex/nofollow ---
        robots_meta = page.meta_robots.lower()  # Lower-cased meta robots
        x_robots = page.header("x-robots-tag").lower()  # Lower-cased header directive
        noindex = "noindex" in robots_meta or "noindex" in x_robots  # Page blocked from indexing?
        results.append(
            scored(
                "Meta robots",  # Parameter name
                "No unintended noindex/nofollow; check X-Robots-Tag header",  # What to check
                meeting=not noindex,  # Meeting when not noindexed
                method=DetectionMethod.CRAWL,  # Parsed from meta + headers
                detail=f"meta robots='{robots_meta}', x-robots-tag='{x_robots}'",  # Evidence
                recommendation="Remove noindex from indexable pages (meta robots and X-Robots-Tag).",
                priority=Priority.HIGH,
            )
        )

        # --- Canonical tag: present and self-referencing ---
        canonical_ok = bool(page.canonical) and self._same_url(page.canonical, page.final_url)  # Self-ref?
        results.append(
            scored(
                "Canonical tags",  # Parameter name
                "Self-referencing; no conflicting/chained canonicals",  # What to check
                meeting=canonical_ok,  # Meeting when self-referencing
                partial=bool(page.canonical) and not canonical_ok,  # Present but points elsewhere
                method=DetectionMethod.CRAWL,  # Parsed from <link rel=canonical>
                detail=f"canonical='{page.canonical or 'none'}'",  # Evidence
                recommendation="Add a self-referencing <link rel=canonical> to the page's clean URL.",
                priority=Priority.MEDIUM,
            )
        )

        # --- HTTP status & redirects: <=1 hop, prefer 301 for permanent ---
        hops = max(len(page.redirect_chain) - 1, 0)  # Redirect hops before the final URL
        has_302 = any(status == 302 for _, status in page.redirect_chain)  # Temporary redirect used?
        results.append(
            scored(
                "HTTP status & redirects",  # Parameter name
                "No redirect chains > 1 hop; 301 not 302 for permanent",  # What to check
                meeting=page.status_code == 200 and hops <= 1 and not has_302,  # Clean delivery
                partial=page.status_code == 200 and (hops > 1 or has_302),  # Reachable but messy
                method=DetectionMethod.CRAWL,  # Observed from the redirect chain
                detail=f"status={page.status_code}, hops={hops}, uses_302={has_302}",  # Evidence
                recommendation="Collapse redirect chains to a single 301 hop to the canonical URL.",
                priority=Priority.MEDIUM,
            )
        )

        # --- Crawl depth: key pages within 3 clicks ---
        max_depth = max(page.internal_depths.values()) if page.internal_depths else 0  # Deepest reached
        results.append(
            scored(
                "Crawl depth",  # Parameter name
                "Key pages reachable within 3 clicks from homepage",  # What to check
                meeting=max_depth <= 3,  # Within the 3-click budget
                method=DetectionMethod.CRAWL,  # From the shallow internal crawl
                detail=f"max observed depth={max_depth} across {len(page.internal_depths)} pages",
                recommendation="Flatten navigation so important pages are within 3 clicks of home.",
                priority=Priority.LOW,
            )
        )

        # --- Pagination handling: rel=next/prev present where paginated ---
        has_pagination = any(  # Look for rel=next/prev link relations in meta tags / links
            "next" in (l.rel or "").lower() or "prev" in (l.rel or "").lower() for l in page.links
        )
        results.append(
            scored(
                "Pagination handling",  # Parameter name
                "rel=next/prev or infinite-scroll pattern; no thin dupes",  # What to check
                meeting=has_pagination,  # Meeting when pagination relations exist
                partial=not has_pagination,  # Treat absence as partial (may be a single page)
                method=DetectionMethod.CRAWL,  # Parsed from link rel attributes
                detail=f"rel=next/prev present: {has_pagination}",  # Evidence
                recommendation="Use rel=next/prev (or canonical) on paginated series to avoid thin dupes.",
                priority=Priority.LOW,
                confidence=Confidence.MEDIUM,  # Pagination presence is a medium-confidence signal
            )
        )

        # --- Log file analysis (crawl frequency) - connected => measured, else manual ---
        results.append(await self._log_analysis(ctx))  # Delegate (GSC URL inspection when connected)

        # --- XML sitemap index detection ---
        results.append(
            scored(
                "XML sitemap index",  # Parameter name
                "Sitemap index pointing to sub-sitemaps (news/image/video)",  # What to check
                meeting=sm.is_index,  # Meeting when a <sitemapindex> was found
                partial=sm.exists and not sm.is_index,  # A flat sitemap is acceptable for small sites
                method=DetectionMethod.CRAWL,  # Parsed from sitemap XML
                detail=f"is_index={sm.is_index}, sub_sitemaps={len(sm.sub_sitemaps)}",  # Evidence
                recommendation="For large sites, use a sitemap index referencing typed sub-sitemaps.",
                priority=Priority.LOW,
            )
        )

        # --- noarchive / nosnippet not accidentally set ---
        suppressed = any(  # Detect snippet/cache suppression directives
            d in robots_meta or d in x_robots for d in ("noarchive", "nosnippet")
        )
        results.append(
            scored(
                "noarchive / nosnippet",  # Parameter name
                "No accidental suppression of snippets or cached pages",  # What to check
                meeting=not suppressed,  # Meeting when neither directive is present
                method=DetectionMethod.CRAWL,  # Parsed from robots directives + headers
                detail=f"noarchive/nosnippet present: {suppressed}",  # Evidence
                recommendation="Remove noarchive/nosnippet unless snippet suppression is intentional.",
                priority=Priority.LOW,
            )
        )

        return results  # All Crawlability rows

    # ---------- helpers ----------

    @staticmethod
    def _robots_blocks_all(robots_txt: str) -> bool:
        """Return True if robots.txt disallows the whole site for the default agent."""
        blocking = False  # Assume not blocking until proven otherwise
        applies = False  # Whether the current block targets User-agent: *
        for raw in robots_txt.splitlines():  # Scan each directive line
            line = raw.split("#", 1)[0].strip()  # Drop comments + surrounding whitespace
            if not line:  # Blank line resets nothing meaningful here
                continue  # Skip
            if line.lower().startswith("user-agent:"):  # Start of an agent block
                applies = line.split(":", 1)[1].strip() == "*"  # Targets all agents?
            elif applies and line.lower().startswith("disallow:"):  # Disallow within the * block
                if line.split(":", 1)[1].strip() == "/":  # Disallow: / blocks everything
                    blocking = True  # Site-wide block detected
        return blocking  # Final verdict

    @staticmethod
    def _same_url(a: str, b: str) -> bool:
        """Compare two URLs ignoring trailing slashes and fragments."""
        norm = lambda u: u.split("#")[0].rstrip("/").lower()  # Normaliser
        return norm(a) == norm(b)  # Equal after normalisation

    async def _sitemap_gsc(self, ctx: AgentContext) -> ParameterResult:
        """Sitemap GSC-submission status: Measured when connected, else Manual."""
        if not (ctx.is_connected and ctx.clients.gsc.enabled):
            return manual(
                "sitemap GSC-submission status",
                "Submitted to Google Search Console",
                "Domain not in connected_properties.json or Google credentials missing.",
                recommendation="Connect the domain via OAuth (scripts/google_auth.py) and add it to connected_properties.json.",
            )
        site_url = ctx.connection["gsc_site_url"]
        result = await ctx.clients.gsc.sitemaps(site_url)
        if not result.ok:
            return first_party_empty(
                "sitemap GSC-submission status",
                "Submitted to Google Search Console",
                f"GSC sitemaps API error: {result.error}",
                recommendation="Verify Search Console API is enabled and the OAuth token has access to this property.",
            )
        sitemaps = result.data or []
        paths = [str(s.get("path", "?")) for s in sitemaps]
        error_count = sum(int(s.get("errors") or 0) for s in sitemaps)
        warning_count = sum(int(s.get("warnings") or 0) for s in sitemaps)
        detail_parts = [f"{len(sitemaps)} sitemap(s) registered in GSC"]
        if paths:
            detail_parts.append("submitted: " + ", ".join(paths[:5]))
        if error_count:
            detail_parts.append(f"{error_count} GSC error(s) on submitted sitemap(s)")
        if warning_count:
            detail_parts.append(f"{warning_count} GSC warning(s)")
        submitted = len(sitemaps) > 0 and error_count == 0
        partial = len(sitemaps) > 0 and error_count > 0
        rec = "Submit a valid XML sitemap URL in Google Search Console (not the homepage)."
        if error_count:
            rec = "Fix sitemap errors in GSC — submitted URL must return XML, not an HTML page."
        return scored(
            "sitemap GSC-submission status",
            "Submitted to Google Search Console",
            meeting=submitted,
            partial=partial,
            method=DetectionMethod.FIRST_PARTY,
            detail="; ".join(detail_parts),
            recommendation=rec,
            priority=Priority.MEDIUM,
            confidence=Confidence.MEASURED,
        )

    async def _log_analysis(self, ctx: AgentContext) -> ParameterResult:
        """Log file analysis via GSC URL Inspection when connected, else Manual."""
        if not (ctx.is_connected and ctx.clients.gsc.enabled):
            return manual(
                "Log file analysis",
                "Googlebot visit frequency; crawl budget waste",
                "Requires server logs or a connected GSC property.",
                recommendation="Connect the domain in connected_properties.json to use GSC URL Inspection.",
            )
        site_url = ctx.connection["gsc_site_url"]
        page_url = ctx.page.final_url or ctx.page.url
        result = await ctx.clients.gsc.inspect_url(site_url, page_url)
        if not result.ok:
            return first_party_empty(
                "Log file analysis",
                "Googlebot visit frequency; crawl budget waste",
                f"GSC URL Inspection API error: {result.error}",
                recommendation="Ensure URL Inspection API access is enabled for your OAuth project.",
            )
        if not result.has_data:
            return first_party_empty(
                "Log file analysis",
                "Googlebot visit frequency; crawl budget waste",
                "GSC connected — URL Inspection returned no index status for this page yet.",
                recommendation="Request indexing in Search Console and retry after Googlebot crawls the page.",
            )
        inspection = result.data or {}
        idx = inspection.get("indexStatusResult") or {}
        last_crawl = idx.get("lastCrawlTime") or "not yet crawled"
        coverage = idx.get("coverageState") or "unknown"
        verdict = idx.get("verdict") or "unknown"
        fetch_state = idx.get("pageFetchState") or "unknown"
        robots_state = idx.get("robotsTxtState") or "unknown"
        matched = inspection.get("_matchedInspectionUrl", "")
        detail = (
            f"lastCrawlTime={last_crawl}; coverageState={coverage}; verdict={verdict}; "
            f"pageFetchState={fetch_state}; robotsTxtState={robots_state}"
        )
        if matched:
            detail += f"; inspectedUrl={matched}"
        indexed = verdict == "PASS" or "index" in coverage.lower()
        crawled = last_crawl != "not yet crawled"
        return scored(
            "Log file analysis",
            "Googlebot visit frequency; crawl budget waste",
            meeting=indexed and crawled,
            partial=crawled and not indexed,
            method=DetectionMethod.FIRST_PARTY,
            detail=detail,
            recommendation="Improve crawlability (valid sitemap, no noindex, fast TTFB) if lastCrawlTime is stale or missing.",
            priority=Priority.MEDIUM,
            confidence=Confidence.MEASURED,
        )

# ============================================================================
# onpage
# ============================================================================

import re  # Detect date patterns for freshness signals


# Regex matching common visible date formats (ISO and long-form) for freshness checks
_DATE_RE = re.compile(
    r"\b(\d{4}-\d{2}-\d{2}|\d{1,2}\s+\w+\s+\d{4}|\w+\s+\d{1,2},\s+\d{4})\b"
)


class OnPageAgent(BaseAgent):
    """Title, meta, headings, content depth, links, freshness and on-page E-E-A-T."""

    key = "onpage"  # Category key
    title = "On-Page Signals"  # Display title
    kind = "seo"  # SEO report
    weight = 1.2  # On-page signals are high-value

    async def analyze(self, ctx: AgentContext) -> list[ParameterResult]:
        """Return all On-Page Signals parameter rows."""
        page = ctx.page  # Page signals shorthand
        gem = ctx.clients.gemini  # Gemini client for LLM-judged rows
        results: list[ParameterResult] = []  # Accumulate rows

        # --- Title tag: 50-60 chars, has a <title> ---
        title_len = len(page.title)  # Character length of the title
        results.append(
            scored(
                "Title tag",  # Parameter name
                "50-60 chars, primary keyword near front, unique",  # What to check
                meeting=50 <= title_len <= 60,  # Ideal length window
                partial=bool(page.title) and not (50 <= title_len <= 60),  # Present but off-length
                method=DetectionMethod.CRAWL,  # Parsed from <title>
                detail=f"title length={title_len}: '{page.title[:80]}'",  # Evidence
                recommendation="Rewrite the title to 50-60 chars with the primary keyword near the front.",
                priority=Priority.HIGH,
            )
        )

        # --- Meta description: 150-160 chars ---
        desc_len = len(page.meta_description)  # Length of the meta description
        results.append(
            scored(
                "Meta description",  # Parameter name
                "150-160 chars, action-oriented, includes target keyword",  # What to check
                meeting=150 <= desc_len <= 160,  # Ideal window
                partial=bool(page.meta_description) and not (150 <= desc_len <= 160),  # Off-length
                method=DetectionMethod.CRAWL,  # Parsed from meta description
                detail=f"meta description length={desc_len}",  # Evidence
                recommendation="Write a 150-160 char meta description with a call to action + keyword.",
                priority=Priority.MEDIUM,
            )
        )

        # --- Heading hierarchy: exactly one H1; H2/H3 present ---
        h1_count = len(page.headings.get("h1", []))  # Number of H1s
        results.append(
            scored(
                "Heading hierarchy",  # Parameter name
                "Single H1; logical H2->H3; no skipped levels",  # What to check
                meeting=h1_count == 1,  # Exactly one H1 is ideal
                partial=h1_count > 1,  # Multiple H1s is a partial pass
                method=DetectionMethod.CRAWL,  # Parsed from heading tree
                detail=f"h1={h1_count}, h2={len(page.headings.get('h2', []))}",  # Evidence
                recommendation="Use exactly one H1 and a logical H2->H3 structure without skipping levels.",
                priority=Priority.MEDIUM,
            )
        )

        # --- Word count / content depth (heuristic + Gemini) ---
        results.append(
            await llm_scored(
                "Word count / content depth",  # Parameter name
                "Matches competitive benchmark; no thin content",  # What to check
                gemini=gem,  # Gemini judges depth
                signal=f"Page title: {page.title}. Word count: {page.word_count}. "
                f"First 1500 chars: {page.visible_text[:1500]}. "
                "Is this content sufficiently deep and non-thin for its topic?",  # Judge prompt
                fallback_meeting=page.word_count >= 600,  # Heuristic: 600+ words is non-thin
                fallback_detail=f"word count={page.word_count}",  # Fallback evidence
                recommendation="Expand thin content to comprehensively cover the topic (aim 800+ words).",
                priority=Priority.MEDIUM,
            )
        )

        # --- Image alt coverage ---
        informational = [i for i in page.images if i.get("src")]  # Images with a source
        with_alt = [i for i in informational if i.get("alt") not in (None,)]  # alt attribute present
        coverage = (len(with_alt) / len(informational)) if informational else 1.0  # Ratio (1.0 if none)
        results.append(
            scored(
                "Image alt coverage",  # Parameter name
                'Informational images have alts; decorative use alt=""',  # What to check
                meeting=coverage >= 0.9,  # 90%+ alt coverage
                partial=0.5 <= coverage < 0.9,  # Partial coverage
                method=DetectionMethod.CRAWL,  # Parsed from <img alt>
                detail=f"alt coverage={coverage:.0%} over {len(informational)} images",  # Evidence
                recommendation="Add descriptive alt text to informational images; alt=\"\" for decorative.",
                priority=Priority.MEDIUM,
                evidence={"coverage": round(coverage, 2), "images": len(informational)},  # UI data
            )
        )

        # --- Internal links + anchor text ---
        internal = page.internal_links  # Internal links discovered
        descriptive = [l for l in internal if len(l.anchor) >= 3]  # Anchors with real text
        results.append(
            scored(
                "Internal links + anchor text",  # Parameter name
                "Keyword-rich anchors; no orphan pages; logical graph",  # What to check
                meeting=len(internal) >= 5 and len(descriptive) >= 0.7 * max(len(internal), 1),  # Healthy
                partial=len(internal) >= 1,  # Some internal links exist
                method=DetectionMethod.CRAWL,  # Parsed from links
                detail=f"{len(internal)} internal links, {len(descriptive)} with descriptive anchors",
                recommendation="Add internal links with descriptive, keyword-rich anchor text.",
                priority=Priority.MEDIUM,
            )
        )

        # --- Keyword usage (Gemini semantic check) ---
        first_100 = " ".join(page.visible_text.split()[:100])  # First 100 words of the body
        results.append(
            await llm_scored(
                "Keyword usage",  # Parameter name
                "Primary keyword in title/H1/first 100 words; related terms",  # What to check
                gemini=gem,  # Gemini judges semantic keyword placement
                signal=f"Title: {page.title}. H1: {page.headings.get('h1', [])}. "
                f"First 100 words: {first_100}. "
                "Is a clear primary keyword present in the title/H1/intro with related terms?",
                fallback_meeting=bool(page.title and page.headings.get("h1")),  # Has title + H1
                fallback_detail="Heuristic: title and H1 present.",  # Fallback evidence
                recommendation="Place the primary keyword in the title, H1 and first 100 words.",
                priority=Priority.MEDIUM,
            )
        )

        # --- Duplicate content (canonical-based heuristic) ---
        results.append(
            scored(
                "Duplicate content",  # Parameter name
                "Near-duplicate pages consolidated via canonical/301",  # What to check
                meeting=bool(page.canonical),  # A canonical reduces duplicate risk
                partial=not page.canonical,  # No canonical => potential risk
                method=DetectionMethod.CRAWL,  # From canonical presence
                detail=f"canonical present: {bool(page.canonical)}",  # Evidence
                recommendation="Consolidate near-duplicates with canonical tags or 301 redirects.",
                priority=Priority.LOW,
                confidence=Confidence.MEDIUM,
            )
        )

        # --- Content freshness signals (visible dates) ---
        has_dates = bool(_DATE_RE.search(page.visible_text[:4000]))  # Date near the top of content
        results.append(
            scored(
                "Content freshness signals",  # Parameter name
                "Visible publish + last-updated dates",  # What to check
                meeting=has_dates,  # Meeting when a date is visible
                method=DetectionMethod.CRAWL,  # Detected by regex over visible text
                detail=f"visible date found: {has_dates}",  # Evidence
                recommendation="Show visible publish and last-updated dates on content pages.",
                priority=Priority.LOW,
            )
        )

        # --- Table of contents (in-page anchor links to section IDs) ---
        # A ToC is detected when several links target in-page fragments (same page + #anchor)
        base = (page.final_url or page.url).split("#")[0]  # Page URL without any fragment
        fragment_links = [l for l in page.links if "#" in l.url and l.url.split("#")[0] in ("", base)]
        has_toc = len(fragment_links) >= 3  # Three or more in-page anchors suggests a ToC
        results.append(
            scored(
                "Table of contents",  # Parameter name
                "Anchor-linked ToC on long-form pages",  # What to check
                meeting=has_toc or page.word_count < 1200,  # Long pages need a ToC; short pages exempt
                partial=not has_toc and page.word_count >= 1200,  # Long page lacking a ToC
                method=DetectionMethod.CRAWL,  # From in-page anchor links
                detail=f"toc anchors detected: {has_toc}, words={page.word_count}",  # Evidence
                recommendation="Add an anchor-linked table of contents to long-form articles.",
                priority=Priority.LOW,
            )
        )

        # --- E-E-A-T signals on-page (Gemini) ---
        results.append(
            await llm_scored(
                "E-E-A-T signals on-page",  # Parameter name
                "Author bio, credentials, About page, attribution",  # What to check
                gemini=gem,  # Gemini judges E-E-A-T cues
                signal=f"Page text (first 2000 chars): {page.visible_text[:2000]}. "
                "Are author, credentials, About/attribution signals present (E-E-A-T)?",
                fallback_meeting="author" in page.visible_text.lower(),  # Heuristic: mentions an author
                fallback_detail="Heuristic: 'author' mention check.",  # Fallback evidence
                recommendation="Add author bios, credentials and clear attribution to demonstrate E-E-A-T.",
                priority=Priority.MEDIUM,
            )
        )

        # --- Outbound link quality (Gemini relevance) ---
        outbound = page.outbound_links  # External links
        results.append(
            await llm_scored(
                "Outbound link quality",  # Parameter name
                "Links to authoritative, topically relevant external sources",  # What to check
                gemini=gem,  # Gemini judges relevance/authority
                signal=f"Outbound link domains: {[l.url for l in outbound][:15]}. "
                f"Page topic from title: {page.title}. "
                "Do outbound links point to authoritative, topically relevant sources?",
                fallback_meeting=len(outbound) >= 2,  # Heuristic: cites a couple of sources
                fallback_detail=f"{len(outbound)} outbound links.",  # Fallback evidence
                recommendation="Cite authoritative, topically relevant external sources.",
                priority=Priority.LOW,
            )
        )

        # --- Multimedia coverage (images/video present) ---
        has_video = bool(page.soup and page.soup.find(["video", "iframe"]))  # Video/embeds present?
        results.append(
            scored(
                "Multimedia coverage",  # Parameter name
                "Video, images, or infographics present",  # What to check
                meeting=len(page.images) >= 1 or has_video,  # Some media present
                method=DetectionMethod.CRAWL,  # Detected media elements
                detail=f"images={len(page.images)}, video/iframe={has_video}",  # Evidence
                recommendation="Enrich content with relevant images, video or infographics.",
                priority=Priority.LOW,
            )
        )

        # --- LSI / semantic coverage (Gemini topic completeness) ---
        results.append(
            await llm_scored(
                "LSI / semantic coverage",  # Parameter name
                "Topic completeness vs top-ranking pages",  # What to check
                gemini=gem,  # Gemini judges topic completeness
                signal=f"Title: {page.title}. Headings: {page.headings.get('h2', [])[:12]}. "
                "Does the page cover the subtopics a comprehensive resource on this topic would?",
                fallback_meeting=len(page.headings.get("h2", [])) >= 4,  # Heuristic: several subsections
                fallback_detail=f"{len(page.headings.get('h2', []))} H2 sections.",  # Fallback evidence
                recommendation="Cover missing subtopics that top-ranking pages address.",
                priority=Priority.MEDIUM,
            )
        )

        return results  # All On-Page rows

# ============================================================================
# technical
# ============================================================================

from urllib.parse import urlparse  # Inspect the URL structure



class TechnicalAgent(BaseAgent):
    """HTTPS, viewport, URL hygiene, hreflang, broken links, protocol and headers."""

    key = "technical"  # Category key
    title = "Technical SEO"  # Display title
    kind = "seo"  # SEO report
    weight = 1.1  # Technical foundations matter

    async def analyze(self, ctx: AgentContext) -> list[ParameterResult]:
        """Return all Technical SEO parameter rows."""
        page = ctx.page  # Page signals shorthand
        psi = page.psi_mobile  # Mobile PSI payload (may be empty if no key/quota)
        psi_ok = bool(psi)  # Whether PSI data is available
        results: list[ParameterResult] = []  # Accumulate rows

        # --- HTTPS / SSL + HSTS + no obvious mixed content ---
        hsts = bool(page.header("strict-transport-security"))  # HSTS header present?
        mixed = "http://" in page.html and page.tls_ok  # HTTP resources on an HTTPS page?
        results.append(
            scored(
                "HTTPS / SSL",  # Parameter name
                "Valid cert; no mixed content; HSTS header",  # What to check
                meeting=page.tls_ok and hsts and not mixed,  # All three satisfied
                partial=page.tls_ok and (not hsts or mixed),  # HTTPS but missing HSTS / mixed content
                method=DetectionMethod.CRAWL,  # From TLS + headers + resources
                detail=f"https={page.tls_ok}, hsts={hsts}, mixed_content={mixed}",  # Evidence
                recommendation="Serve all resources over HTTPS and add a Strict-Transport-Security header.",
                priority=Priority.HIGH,
            )
        )

        # --- Mobile viewport meta tag ---
        viewport = page.meta_tags.get("viewport", "")  # <meta name=viewport> content
        results.append(
            scored(
                "Mobile viewport",  # Parameter name
                "Meta viewport; no horizontal scroll; tap targets >= 44px",  # What to check
                meeting="width=device-width" in viewport,  # Responsive viewport configured
                method=DetectionMethod.CRAWL,  # Parsed from the viewport meta
                detail=f"viewport='{viewport or 'missing'}'",  # Evidence
                recommendation='Add <meta name="viewport" content="width=device-width, initial-scale=1">.',
                priority=Priority.HIGH,
            )
        )

        # --- URL structure (lowercase, hyphens, short, no junk params) ---
        parsed = urlparse(page.final_url or page.url)  # Decompose the final URL
        path = parsed.path  # Path component
        url_clean = (  # All structural conditions
            path == path.lower()  # Lowercase path
            and "_" not in path  # Hyphens, not underscores
            and len(page.final_url) < 115  # Reasonably short
            and parsed.query.count("&") <= 2  # Few query params
        )
        results.append(
            scored(
                "URL structure",  # Parameter name
                "Lowercase, hyphens, keyword-rich, < 115 chars, no junk params",  # What to check
                meeting=url_clean,  # Clean structure
                partial=not url_clean and len(page.final_url) < 200,  # Usable but imperfect
                method=DetectionMethod.CRAWL,  # From the URL string
                detail=f"len={len(page.final_url)}, path='{path}'",  # Evidence
                recommendation="Use short, lowercase, hyphenated URLs without tracking/junk parameters.",
                priority=Priority.LOW,
            )
        )

        # --- hreflang (only relevant for multi-region sites) ---
        hreflang_links = [l for l in (page.soup.find_all("link", rel="alternate") if page.soup else [])
                          if l.get("hreflang")]  # <link rel=alternate hreflang=...>
        has_xdefault = any(l.get("hreflang") == "x-default" for l in hreflang_links)  # x-default set?
        results.append(
            scored(
                "hreflang",  # Parameter name
                "Correct lang/region; self-referencing; x-default set",  # What to check
                meeting=(len(hreflang_links) == 0) or has_xdefault,  # None needed, or correctly set
                partial=len(hreflang_links) > 0 and not has_xdefault,  # Present but missing x-default
                method=DetectionMethod.CRAWL,  # Parsed from hreflang tags
                detail=f"hreflang tags={len(hreflang_links)}, x-default={has_xdefault}",  # Evidence
                recommendation="For multi-region sites, add self-referencing hreflang + an x-default.",
                priority=Priority.LOW,
                confidence=Confidence.MEDIUM,
            )
        )

        # --- Broken links (real internal 4xx/5xx only; exclude bot-protection blocks) ---
        from app.crawl import STATUS_BOT_BLOCKED, is_reportable_http_error

        broken = [u for u, s in page.link_status.items() if is_reportable_http_error(s)]
        broken_4xx = [u for u, s in page.link_status.items() if is_reportable_http_error(s) and 400 <= s < 500]
        broken_5xx = [u for u, s in page.link_status.items() if is_reportable_http_error(s) and s >= 500]
        bot_blocked = [
            u
            for u, s in page.link_status.items()
            if s == STATUS_BOT_BLOCKED or s in (401, 403, 429)
        ]
        unverified = [u for u, s in page.link_status.items() if s == 0]
        detail = (
            f"{len(broken)} broken of {len(page.link_status)} sampled links "
            f"(4xx={len(broken_4xx)}, 5xx={len(broken_5xx)}, "
            f"bot_blocked={len(bot_blocked)}, unreachable={len(unverified)})"
        )
        results.append(
            scored(
                "Broken links",  # Parameter name
                "0 internal 4xx; external link monitoring",  # What to check
                meeting=len(broken) == 0,  # No real broken links in the sample
                partial=0 < len(broken) <= 2,  # A couple of broken links
                method=DetectionMethod.CRAWL,  # From the crawl link-status sample
                detail=detail,
                recommendation="Fix or remove links returning real 4xx/5xx status codes.",
                priority=Priority.MEDIUM,
                evidence={
                    "broken_sample": broken[:10],
                    "broken_4xx": broken_4xx[:10],
                    "broken_5xx": broken_5xx[:10],
                    "bot_blocked_sample": bot_blocked[:5],
                    "count": len(broken),
                    "count_4xx": len(broken_4xx),
                    "count_5xx": len(broken_5xx),
                },
            )
        )

        # --- Render-blocking resources (PSI audit) ---
        results.append(
            self._psi_row(
                psi_ok,  # Whether PSI data is available
                "Render-blocking resources",  # Parameter name
                "CSS/JS deferred or async; critical CSS inlined",  # What to check
                audit_score(psi, "render-blocking-resources"),  # 0..1 audit score (1 = good)
                recommendation="Defer/async non-critical CSS/JS and inline critical CSS.",
            )
        )

        # --- JavaScript rendering (raw vs rendered text diff) ---
        raw_words = len(page.raw_soup.get_text(" ", strip=True).split()) if page.raw_soup else 0  # Pre-JS
        rendered_words = page.word_count  # Post-JS word count
        # Critical content is JS-only when the raw HTML has far fewer words than the rendered DOM
        js_dependent = rendered_words > 0 and raw_words < 0.5 * rendered_words and page.rendered_html != ""
        results.append(
            scored(
                "JavaScript rendering",  # Parameter name
                "Critical content not JS-only",  # What to check
                meeting=not js_dependent,  # Meeting when content exists pre-JS
                method=DetectionMethod.CRAWL,  # From the raw vs rendered diff
                detail=f"raw words={raw_words}, rendered words={rendered_words}",  # Evidence
                recommendation="Server-render or pre-render critical content so it exists without JS.",
                priority=Priority.MEDIUM,
                confidence=Confidence.MEDIUM,
            )
        )

        # --- HTTP/2 or HTTP/3 ---
        modern_proto = page.http_version in ("HTTP/2", "HTTP/3")  # Modern protocol negotiated?
        results.append(
            scored(
                "HTTP/2 or HTTP/3",  # Parameter name
                "Protocol version check",  # What to check
                meeting=modern_proto,  # Meeting on HTTP/2 or HTTP/3
                method=DetectionMethod.CRAWL,  # From the negotiated protocol
                detail=f"protocol={page.http_version or 'unknown'}",  # Evidence
                recommendation="Enable HTTP/2 (or HTTP/3) on your server/CDN.",
                priority=Priority.LOW,
            )
        )

        # --- Server response time (measured TTFB) ---
        results.append(
            scored(
                "Server response time",  # Parameter name
                "TTFB < 200ms; server-side caching",  # What to check
                meeting=0 < page.ttfb_ms <= 200,  # Fast TTFB
                partial=200 < page.ttfb_ms <= 800,  # Acceptable TTFB
                method=DetectionMethod.CRAWL,  # Measured during fetch
                detail=f"measured TTFB={page.ttfb_ms:.0f}ms",  # Evidence
                recommendation="Reduce TTFB with server-side caching, a CDN and faster backend responses.",
                priority=Priority.MEDIUM,
            )
        )

        # --- Image compression & format (PSI audits) ---
        results.append(
            self._psi_row(
                psi_ok,  # PSI availability
                "Image compression & format",  # Parameter name
                "WebP/AVIF; lazy loading; explicit width/height",  # What to check
                audit_score(psi, "uses-optimized-images"),  # Optimised-images audit score
                recommendation="Serve WebP/AVIF, lazy-load offscreen images and set width/height.",
            )
        )

        # --- Third-party script impact (PSI audit) ---
        results.append(
            self._psi_row(
                psi_ok,  # PSI availability
                "Third-party script impact",  # Parameter name
                "Defer non-critical scripts",  # What to check
                audit_score(psi, "third-party-summary"),  # Third-party impact audit score
                recommendation="Defer/remove non-critical third-party scripts to reduce main-thread work.",
            )
        )

        # --- Security headers (CSP / X-Frame-Options / Referrer-Policy) ---
        sec = [  # Presence of each recommended security header
            bool(page.header("content-security-policy")),
            bool(page.header("x-frame-options")),
            bool(page.header("referrer-policy")),
        ]
        results.append(
            scored(
                "Security headers",  # Parameter name
                "CSP, X-Frame-Options, Referrer-Policy",  # What to check
                meeting=all(sec),  # All three present
                partial=any(sec),  # At least one present
                method=DetectionMethod.CRAWL,  # From response headers
                detail=f"CSP={sec[0]}, X-Frame-Options={sec[1]}, Referrer-Policy={sec[2]}",  # Evidence
                recommendation="Add CSP, X-Frame-Options and Referrer-Policy response headers.",
                priority=Priority.LOW,
            )
        )

        # --- AMP / Web Stories (optional; absence is not penalised) ---
        head = page.html[:600].lower()  # The opening <html> tag lives near the top of the document
        is_amp = "<html amp" in head or "⚡" in head or 'amphtml' in page.html.lower()  # AMP markers
        results.append(
            scored(
                "AMP / Web Stories",  # Parameter name
                "Valid AMP markup + AMP-canonical pairing",  # What to check
                meeting=True,  # AMP is optional; treat as Meeting unless present-but-broken
                method=DetectionMethod.CRAWL,  # Detected AMP markup
                detail=f"AMP markup detected: {is_amp} (AMP is optional)",  # Evidence
                confidence=Confidence.LOW,
            )
        )

        return results  # All Technical SEO rows

    @staticmethod
    def _psi_row(
        psi_ok: bool,
        name: str,
        what: str,
        score: float | None,
        *,
        recommendation: str,
    ) -> ParameterResult:
        """Build a row from a PSI audit score, or Not Measured when PSI is unavailable."""
        if not psi_ok or score is None:  # No PSI data / audit missing
            return not_measured(
                name, what, DetectionMethod.PSI, "PageSpeed Insights unavailable (no key/quota/audit)."
            )
        # Lighthouse audit scores are 0..1; >=0.9 good, 0.5-0.9 partial, else failing
        return scored(
            name,
            what,
            meeting=score >= 0.9,  # Good audit score
            partial=0.5 <= score < 0.9,  # Needs improvement
            method=DetectionMethod.PSI,  # Detected via PSI
            detail=f"PSI audit score={score:.2f}",  # Evidence
            recommendation=recommendation,  # Concrete fix
            priority=Priority.MEDIUM,
            confidence=Confidence.HIGH,
        )

# ============================================================================
# cwv
# ============================================================================

class CoreWebVitalsAgent(BaseAgent):
    """Reads PSI lab + CrUX field data to score LCP, CLS, INP, TTFB and Lighthouse."""

    key = "cwv"  # Category key
    title = "Core Web Vitals & Performance"  # Display title
    kind = "seo"  # SEO report
    weight = 1.0  # Standard weight

    async def analyze(self, ctx: AgentContext) -> list[ParameterResult]:
        """Return all CWV & Performance rows and populate the SEO report's CWV panel."""
        page = ctx.page  # Page signals shorthand
        mobile = page.psi_mobile  # Mobile PSI payload
        desktop = page.psi_desktop  # Desktop PSI payload
        results: list[ParameterResult] = []  # Accumulate rows

        if not mobile:  # PSI could not run at all (no key/quota/network)
            # Emit Not Measured for every CWV parameter so the category is transparent, not blank
            for name, what in self._param_catalog():  # Iterate the parameter catalog
                results.append(
                    not_measured(name, what, DetectionMethod.PSI, "PageSpeed Insights unavailable.")
                )
            return results  # Nothing measurable

        # --- LCP (lab) <= 2.5s ---
        lcp = audit_numeric(mobile, "largest-contentful-paint")  # LCP in milliseconds
        results.append(self._threshold_row(
            "LCP", "<= 2.5s; main image/text block is largest element", lcp, 2500, 4000, "ms",
            "Optimise the largest element (image/text) and reduce render-blocking work.",
        ))

        # --- CLS <= 0.1 ---
        cls = audit_numeric(mobile, "cumulative-layout-shift")  # CLS score (unitless)
        results.append(self._threshold_row(
            "CLS", "<= 0.1; reserve space for media/embeds", cls, 0.1, 0.25, "",
            "Set explicit dimensions for media/embeds and avoid injecting content above existing content.",
            lower_is_better=True,
        ))

        # --- INP <= 200ms (prefer CrUX field; fall back to lab TBT proxy) ---
        inp_field = crux_metric(mobile, "INTERACTION_TO_NEXT_PAINT").get("percentile")  # Field INP (ms)
        inp = inp_field if isinstance(inp_field, (int, float)) else audit_numeric(mobile, "total-blocking-time")
        results.append(self._threshold_row(
            "INP", "<= 200ms; replaces FID", inp, 200, 500, "ms",
            "Reduce long tasks and main-thread blocking to improve interaction responsiveness.",
        ))

        # --- TTFB <= 800ms (lab server-response-time) ---
        ttfb = audit_numeric(mobile, "server-response-time")  # Server response time (ms)
        results.append(self._threshold_row(
            "TTFB", "<= 800ms; server + CDN tuning", ttfb, 800, 1800, "ms",
            "Lower TTFB with caching, a CDN and faster server responses.",
        ))

        # --- Lighthouse scores (all four categories >= 90) ---
        scores = {c: category_score(mobile, c) for c in ("performance", "accessibility", "best-practices", "seo")}
        valid = [s for s in scores.values() if s is not None]  # Available category scores
        all_high = bool(valid) and all(s >= 90 for s in valid)  # All categories >= 90?
        results.append(
            scored(
                "Lighthouse scores",  # Parameter name
                "Performance, Accessibility, Best Practices, SEO >= 90",  # What to check
                meeting=all_high,  # Meeting when every category is >= 90
                partial=bool(valid) and not all_high and all(s >= 70 for s in valid),  # All >= 70
                method=DetectionMethod.PSI,  # From PSI category scores
                detail=", ".join(f"{k}={v}" for k, v in scores.items() if v is not None),  # Evidence
                recommendation="Raise each Lighthouse category to >= 90 (perf, a11y, best practices, SEO).",
                priority=Priority.MEDIUM,
                confidence=Confidence.HIGH,
                evidence=scores,  # Surface the scores to the UI panel
            )
        )

        # --- Field data (CrUX) presence ---
        has_crux = (mobile.get("loadingExperience", {}).get("metrics")) is not None  # Field data present?
        results.append(
            scored(
                "Field data (CrUX)",  # Parameter name
                "Real-user field data; lab != real users",  # What to check
                meeting=bool(has_crux),  # Meeting when CrUX field data exists
                method=DetectionMethod.PSI,  # From PSI loadingExperience
                detail=f"CrUX field data available: {bool(has_crux)}",  # Evidence
                recommendation="Drive enough real traffic to qualify for CrUX field data, then optimise it.",
                priority=Priority.LOW,
                confidence=Confidence.HIGH,
            )
        )

        # --- Mobile vs desktop delta ---
        mobile_perf = category_score(mobile, "performance")  # Mobile performance score
        desktop_perf = category_score(desktop, "performance") if desktop else None  # Desktop score
        delta = (abs(mobile_perf - desktop_perf) if (mobile_perf is not None and desktop_perf is not None) else None)
        results.append(
            scored(
                "Mobile vs desktop delta",  # Parameter name
                "Run CWV separately for mobile and desktop",  # What to check
                meeting=delta is not None and delta <= 20,  # Small gap between devices
                partial=delta is not None and 20 < delta <= 40,  # Noticeable gap
                method=DetectionMethod.PSI,  # PSI run twice
                detail=f"mobile perf={mobile_perf}, desktop perf={desktop_perf}, delta={delta}",  # Evidence
                recommendation="Close the mobile/desktop performance gap (usually mobile needs work).",
                priority=Priority.LOW,
                confidence=Confidence.HIGH,
            )
        )

        # --- Font loading strategy (font-display + preload) ---
        html_lower = page.html.lower()  # Lower-cased HTML for cheap substring checks
        good_fonts = "font-display" in html_lower or 'rel="preload"' in html_lower  # Swap/preload present
        results.append(
            scored(
                "Font loading strategy",  # Parameter name
                "font-display: swap; preload key fonts; fallbacks",  # What to check
                meeting=good_fonts,  # Meeting when font-display/preload is used
                method=DetectionMethod.CRAWL,  # From markup/CSS
                detail=f"font-display/preload present: {good_fonts}",  # Evidence
                recommendation="Use font-display: swap, preload key fonts and define fallbacks.",
                priority=Priority.LOW,
            )
        )

        # Populate the SEO report's Core Web Vitals panel for the UI
        self._panel = {  # Store a compact panel summary on the agent for the orchestrator to read
            "lcp_ms": lcp,
            "cls": cls,
            "inp_ms": inp,
            "ttfb_ms": ttfb,
            "lighthouse": scores,
            "has_field_data": bool(has_crux),
        }
        return results  # All CWV rows

    # The orchestrator reads this after analyze() to attach the SEO panel
    _panel: dict = {}  # Compact CWV summary for the report panel

    @staticmethod
    def _param_catalog() -> list[tuple[str, str]]:
        """The (name, what-to-check) list used when PSI is entirely unavailable."""
        return [
            ("LCP", "<= 2.5s; main image/text block is largest element"),
            ("CLS", "<= 0.1; reserve space for media/embeds"),
            ("INP", "<= 200ms; replaces FID"),
            ("TTFB", "<= 800ms; server + CDN tuning"),
            ("Lighthouse scores", "Performance, Accessibility, Best Practices, SEO >= 90"),
            ("Field data (CrUX)", "Real-user field data; lab != real users"),
            ("Mobile vs desktop delta", "Run CWV separately for mobile and desktop"),
            ("Font loading strategy", "font-display: swap; preload key fonts; fallbacks"),
        ]

    @staticmethod
    def _threshold_row(
        name: str,
        what: str,
        value: float | None,
        good: float,
        poor: float,
        unit: str,
        recommendation: str,
        *,
        lower_is_better: bool = True,
    ) -> ParameterResult:
        """Build a CWV row by comparing a measured value to good/poor thresholds."""
        if value is None:  # Audit value missing from PSI
            return not_measured(name, what, DetectionMethod.PSI, "Metric not present in PSI payload.")
        meeting = value <= good  # At or below the 'good' threshold (lower is better for CWV)
        partial = good < value <= poor  # Between good and poor => needs improvement
        return scored(
            name,
            what,
            meeting=meeting,  # Good
            partial=partial,  # Needs improvement
            method=DetectionMethod.PSI,  # From PSI lab/field data
            detail=f"measured={value:.3f}{unit} (good<= {good}{unit}, poor> {poor}{unit})",  # Evidence
            recommendation=recommendation,  # Concrete fix
            priority=Priority.HIGH if not meeting else Priority.LOW,  # CWV failures are high priority
            confidence=Confidence.HIGH,  # PSI is a high-confidence source
            evidence={"value": value, "unit": unit, "good": good, "poor": poor},  # UI data
        )

# ============================================================================
# structured data
# ============================================================================

class StructuredDataAgent(BaseAgent):
    """Validates JSON-LD coverage, social cards, favicon and rich-result eligibility."""

    key = "structured_data"  # Category key
    title = "Structured Data & Social"  # Display title
    kind = "seo"  # SEO report
    weight = 0.9  # Slightly lower weight

    async def analyze(self, ctx: AgentContext) -> list[ParameterResult]:
        """Return all Structured Data & Social rows."""
        page = ctx.page  # Page signals shorthand
        types = jsonld_types(page)  # All schema @type values present
        results: list[ParameterResult] = []  # Accumulate rows

        # --- Schema.org JSON-LD present (any meaningful type) ---
        core_types = {"Article", "Product", "FAQPage", "HowTo", "BreadcrumbList", "Organization", "LocalBusiness"}
        has_core = bool(types & core_types)  # Intersection with recognised core types
        results.append(
            scored(
                "Schema.org JSON-LD",  # Parameter name
                "Article, Product, FAQ, HowTo, BreadcrumbList, Organization, LocalBusiness",  # What to check
                meeting=has_core,  # Meeting when a core type exists
                partial=bool(types) and not has_core,  # Some JSON-LD, but not a core type
                method=DetectionMethod.CRAWL,  # Parsed JSON-LD
                detail=f"types present: {sorted(types) or 'none'}",  # Evidence
                recommendation="Add relevant Schema.org JSON-LD (Article/Product/FAQ/Organization, etc.).",
                priority=Priority.MEDIUM,
                evidence={"types": sorted(types)},  # UI data
            )
        )

        # --- OG / Twitter cards ---
        og_ok = all(k in page.meta_tags for k in ("og:title", "og:image", "og:description"))  # Core OG
        twitter_ok = "twitter:card" in page.meta_tags  # Twitter card type present
        results.append(
            scored(
                "OG / Twitter cards",  # Parameter name
                "og:title, og:image (1200x630), og:description, twitter:card",  # What to check
                meeting=og_ok and twitter_ok,  # Both OG core + Twitter card
                partial=og_ok or twitter_ok,  # One of the two present
                method=DetectionMethod.CRAWL,  # Parsed from meta tags
                detail=f"og_core={og_ok}, twitter_card={twitter_ok}",  # Evidence
                recommendation="Add og:title/og:image/og:description and a twitter:card meta tag.",
                priority=Priority.MEDIUM,
            )
        )

        # --- Favicon (icon + apple-touch-icon) ---
        icons = page.soup.find_all("link", rel=lambda v: v and "icon" in v.lower()) if page.soup else []
        apple = any("apple-touch-icon" in " ".join(i.get("rel", [])).lower() for i in icons)  # Apple icon?
        results.append(
            scored(
                "Favicon",  # Parameter name
                "SVG + 32px PNG + apple-touch-icon",  # What to check
                meeting=len(icons) > 0 and apple,  # Icon plus apple-touch-icon
                partial=len(icons) > 0,  # At least one icon
                method=DetectionMethod.CRAWL,  # Detected favicon link tags
                detail=f"icon links={len(icons)}, apple-touch-icon={apple}",  # Evidence
                recommendation="Provide a favicon (SVG + 32px PNG) and an apple-touch-icon.",
                priority=Priority.LOW,
            )
        )

        # --- Rich result eligibility (heuristic: core schema present + required keys) ---
        article_ok = self._has_keys(page, "Article", ["headline"])  # Article needs a headline
        results.append(
            scored(
                "Rich result eligibility",  # Parameter name
                "Warnings/errors check",  # What to check
                meeting=has_core and (("Article" not in types) or article_ok),  # Core present + valid Article
                partial=has_core,  # Core present but possibly incomplete
                method=DetectionMethod.CRAWL,  # Validated against simple rules
                detail=f"core schema={has_core}, article headline ok={article_ok}",  # Evidence
                recommendation="Ensure schema includes all required properties for its rich-result type.",
                priority=Priority.LOW,
                confidence=Confidence.MEDIUM,
            )
        )

        # --- Breadcrumb schema ---
        results.append(
            scored(
                "Breadcrumb schema",  # Parameter name
                "BreadcrumbList on interior pages",  # What to check
                meeting="BreadcrumbList" in types,  # BreadcrumbList present
                method=DetectionMethod.CRAWL,  # Parsed JSON-LD
                detail=f"BreadcrumbList present: {'BreadcrumbList' in types}",  # Evidence
                recommendation="Add BreadcrumbList JSON-LD to interior pages.",
                priority=Priority.LOW,
            )
        )

        # --- Sitelinks searchbox (WebSite + SearchAction) ---
        has_searchaction = any(  # Look for a potentialAction of type SearchAction
            self._mentions(block, "SearchAction") for block in page.jsonld
        )
        results.append(
            scored(
                "Sitelinks searchbox",  # Parameter name
                "WebSite schema with potentialAction SearchAction",  # What to check
                meeting=("WebSite" in types) and has_searchaction,  # WebSite + SearchAction
                method=DetectionMethod.CRAWL,  # Parsed JSON-LD
                detail=f"WebSite={'WebSite' in types}, SearchAction={has_searchaction}",  # Evidence
                recommendation="Add WebSite schema with a SearchAction potentialAction for a sitelinks searchbox.",
                priority=Priority.LOW,
            )
        )

        # --- Review / Rating schema ---
        has_rating = any(self._mentions(block, "AggregateRating") for block in page.jsonld)  # AggregateRating?
        results.append(
            scored(
                "Review / Rating schema",  # Parameter name
                "AggregateRating on product/service pages",  # What to check
                meeting=has_rating,  # AggregateRating present
                partial=("Product" not in types),  # Not a product page => rating may be N/A
                method=DetectionMethod.CRAWL,  # Parsed JSON-LD
                detail=f"AggregateRating present: {has_rating}",  # Evidence
                recommendation="Add AggregateRating/Review schema to product/service pages.",
                priority=Priority.LOW,
                confidence=Confidence.MEDIUM,
            )
        )

        # --- Video schema ---
        results.append(
            scored(
                "Video schema",  # Parameter name
                "VideoObject with thumbnail, duration, uploadDate",  # What to check
                meeting="VideoObject" in types,  # VideoObject present
                partial=not bool(page.soup and page.soup.find(["video", "iframe"])),  # No video => N/A
                method=DetectionMethod.CRAWL,  # Parsed JSON-LD
                detail=f"VideoObject present: {'VideoObject' in types}",  # Evidence
                recommendation="Add VideoObject schema (thumbnail, duration, uploadDate) for video content.",
                priority=Priority.LOW,
                confidence=Confidence.MEDIUM,
            )
        )

        return results  # All Structured Data rows

    @staticmethod
    def _has_keys(page, type_name: str, keys: list[str]) -> bool:
        """Return True if a JSON-LD block of `type_name` contains all `keys`."""
        for block in page.jsonld:  # Iterate JSON-LD blocks
            t = block.get("@type")  # The block's type(s)
            matches = t == type_name or (isinstance(t, list) and type_name in t)  # Type match
            if matches and all(k in block for k in keys):  # Type matches and has all keys
                return True  # Found a complete block
        return False  # None matched

    @staticmethod
    def _mentions(block: dict, needle: str) -> bool:
        """Return True if the JSON-LD `block` mentions `needle` anywhere in its values."""
        try:  # Serialising arbitrary JSON-LD can rarely fail
            import json  # Local import: only needed for this cheap containment check

            return needle.lower() in json.dumps(block).lower()  # Substring match over the block
        except Exception:  # Non-serialisable content
            return False  # Treat as not present

# ============================================================================
# offpage
# ============================================================================

import re  # Detect phone numbers for on-page NAP


# Loose phone-number pattern used to detect on-page NAP (Name/Address/Phone)
_PHONE_RE = re.compile(r"(\+?\d[\d\-\s().]{7,}\d)")


class OffPageAgent(BaseAgent):
    """Topical authority + on-page NAP are scored; off-site signals stay Manual."""

    key = "offpage"  # Category key
    title = "Off-Page & Authority"  # Display title
    kind = "seo"  # SEO report
    weight = 0.7  # Lower weight: most off-page data is unavailable to a crawler

    async def analyze(self, ctx: AgentContext) -> list[ParameterResult]:
        """Return all Off-Page & Authority rows (Manual where data is off-site)."""
        page = ctx.page  # Page signals shorthand
        gem = ctx.clients.gemini  # Gemini for topical authority
        results: list[ParameterResult] = []  # Accumulate rows

        # --- Backlink profile (Manual: needs an off-site link index) ---
        results.append(manual(
            "Backlink profile",  # Parameter name
            "Domain authority distribution; toxic ratio; anchor diversity",  # What to check
            "Requires an off-site link index (e.g. Ahrefs/Majestic); not crawlable.",  # Why manual
        ))

        # --- Referring domain count (Manual) ---
        results.append(manual(
            "Referring domain count",  # Parameter name
            "Unique linking root domains; trend",  # What to check
            "Requires an off-site link index.",  # Why manual
        ))

        # --- Topical authority (Automated: internal graph + Gemini) ---
        internal_anchors = [l.anchor for l in page.internal_links if l.anchor][:30]  # Anchor sample
        results.append(
            await llm_scored(
                "Topical authority",  # Parameter name
                "Topic cluster breadth; hub-spoke internal linking",  # What to check
                gemini=gem,  # Gemini judges topical breadth
                signal=f"Page title: {page.title}. Internal link anchors: {internal_anchors}. "
                "Do the internal links indicate a coherent topic cluster / hub-and-spoke structure?",
                fallback_meeting=len(page.internal_links) >= 10,  # Heuristic: a real internal graph
                fallback_detail=f"{len(page.internal_links)} internal links.",  # Fallback evidence
                recommendation="Build topic clusters with hub-and-spoke internal linking.",
                priority=Priority.MEDIUM,
            )
        )

        # --- Brand mentions (unlinked) (Manual) ---
        results.append(manual(
            "Brand mentions (unlinked)",  # Parameter name
            "Citation signals across the web",  # What to check
            "Requires off-site monitoring; not exposed by a crawl/GA4/GSC.",  # Why manual
        ))

        # --- Competitor link gap (Manual) ---
        results.append(manual(
            "Competitor link gap",  # Parameter name
            "Links competitors have that you lack",  # What to check
            "Requires an off-site link index + competitor data.",  # Why manual
        ))

        # --- NAP consistency (on-page) (Automated) ---
        text = page.visible_text  # Visible body text
        has_phone = bool(_PHONE_RE.search(text))  # Phone number present?
        # An address heuristic: a postal-code-like token or common address words
        has_address = bool(re.search(r"\b\d{4,6}\b", text)) and any(
            w in text.lower() for w in ("street", "st.", "ave", "road", "rd", "suite", "floor")
        )
        nap_count = sum([bool(page.title or page.host), has_phone, has_address])  # Name+phone+address
        results.append(
            scored(
                "NAP consistency (local) - on-page",  # Parameter name
                "Name/Address/Phone present and consistent on page",  # What to check
                meeting=nap_count == 3,  # All three present
                partial=nap_count == 2,  # Two of three present
                method=DetectionMethod.CRAWL,  # Parsed on-page
                detail=f"name={bool(page.title)}, phone={has_phone}, address={has_address}",  # Evidence
                recommendation="Show consistent Name, Address and Phone (NAP) on the page (and in schema).",
                priority=Priority.LOW,
            )
        )

        # --- NAP consistency (cross-directory) (Manual) ---
        results.append(manual(
            "NAP consistency (local) - cross-directory",  # Parameter name
            "Identical across external directories",  # What to check
            "Requires external directory data (Yelp, GBP, etc.).",  # Why manual
        ))

        # --- Google Business Profile (Manual) ---
        results.append(manual(
            "Google Business Profile",  # Parameter name
            "Verified, complete listing; reviews; posts",  # What to check
            "Requires Business Profile ownership/listing data.",  # Why manual
        ))

        return results  # All Off-Page rows

# ============================================================================
# ux
# ============================================================================

from urllib.parse import urlparse  # Extract the page path for GA4 queries



class UxAgent(BaseAgent):
    """CTR/engagement come from GA4+GSC when connected; intent is judged by Gemini."""

    key = "ux"  # Category key
    title = "UX & Engagement Signals"  # Display title
    kind = "seo"  # SEO report
    weight = 0.8  # Engagement is secondary to core SEO foundations

    async def analyze(self, ctx: AgentContext) -> list[ParameterResult]:
        """Return all UX & Engagement rows (Measured when connected, else Manual)."""
        page = ctx.page  # Page signals shorthand
        results: list[ParameterResult] = []  # Accumulate rows

        # Fetch first-party data once if the property is connected
        ga4_data: dict = {}
        gsc_result = None
        if ctx.is_connected:
            path = urlparse(page.final_url or page.url).path or "/"
            prop = ctx.connection.get("ga4_property_id", "")
            site = ctx.connection.get("gsc_site_url", "")
            ga4_data = await ctx.clients.ga4.engagement(prop, path)
            gsc_result = await ctx.clients.gsc.query_search_analytics(site, page.final_url or page.url)

        results.append(self._ctr_row(ctx, gsc_result))

        # --- Dwell time / scroll depth ---
        results.append(self._ga4_row(
            ctx, ga4_data, "Dwell time / scroll depth", "GA4 engagement proxy",
            metric="averageSessionDuration", good=lambda v: v >= 30,  # >=30s avg session is healthy
            recommendation="Increase on-page engagement (clearer intro, media, internal links).",
        ))

        # --- Bounce rate in context ---
        results.append(self._ga4_row(
            ctx, ga4_data, "Bounce rate in context", "High bounce interpreted by page type",
            metric="bounceRate", good=lambda v: v <= 0.6,  # <=60% bounce is acceptable (lower is better)
            recommendation="Match content to intent and add clear next steps to reduce bounce.",
            lower_is_better=True,
        ))

        # --- Pogo-sticking risk (derived from GA4 engagementRate) ---
        if ctx.is_connected and ga4_data:  # Derive when connected
            engagement_rate = float(ga4_data.get("engagementRate", 0.0))  # Engagement rate (0..1)
            results.append(
                scored(
                    "Pogo-sticking risk",  # Parameter name
                    "Users returning to SERP quickly = intent mismatch",  # What to check
                    meeting=engagement_rate >= 0.5,  # High engagement => low pogo risk
                    partial=engagement_rate >= 0.3,  # Moderate engagement
                    method=DetectionMethod.FIRST_PARTY,  # GA4 + GSC derived
                    detail=f"engagementRate={engagement_rate:.2%}",  # Evidence
                    recommendation="Align the page with search intent so users do not bounce back to the SERP.",
                    priority=Priority.MEDIUM,
                    confidence=Confidence.MEASURED,
                )
            )
        else:  # Not connected => Manual
            results.append(manual(
                "Pogo-sticking risk", "Users returning to SERP quickly = intent mismatch",
                "Requires GA4 + GSC data (domain not connected).",
            ))

        # --- Search intent alignment (Gemini, always automated) ---
        results.append(
            await llm_scored(
                "Search intent alignment",  # Parameter name
                "Informational/navigational/commercial/transactional match",  # What to check
                gemini=ctx.clients.gemini,  # Gemini judges intent vs page type
                signal=f"Title: {page.title}. H1: {page.headings.get('h1', [])}. "
                f"Intro: {' '.join(page.visible_text.split()[:120])}. "
                "Does the page content match the likely search intent for its topic?",
                fallback_meeting=bool(page.title and page.word_count > 200),  # Heuristic
                fallback_detail="Heuristic: title present and non-trivial content.",  # Fallback evidence
                recommendation="Reshape content to match the dominant search intent for the target query.",
                priority=Priority.MEDIUM,
            )
        )

        return results  # All UX rows

    @staticmethod
    def _format_gsc_analytics(row: dict) -> str:
        """Human-readable Search Analytics evidence string."""
        ctr = float(row.get("ctr", 0.0))
        position = float(row.get("position", 99))
        clicks = int(row.get("clicks", 0))
        impressions = int(row.get("impressions", 0))
        parts = [
            f"clicks={clicks}",
            f"impressions={impressions}",
            f"ctr={ctr:.2%}",
            f"avg position={position:.1f}",
        ]
        matched = row.get("_matchedPageUrl")
        if matched:
            parts.append(f"matchedUrl={matched}")
        return "; ".join(parts)

    def _ctr_row(self, ctx: AgentContext, gsc_result) -> ParameterResult:
        """Click-through rate from GSC Search Analytics when connected."""
        name = "Click-through rate (CTR)"
        what = "GSC CTR vs position benchmark"
        if not ctx.is_connected:
            return manual(
                name, what,
                "Domain not in connected_properties.json.",
                recommendation="Add the domain to connected_properties.json and sign in via scripts/google_auth.py.",
            )
        if gsc_result is None or not gsc_result.ok:
            err = gsc_result.error if gsc_result else "GSC client unavailable"
            return first_party_empty(
                name, what,
                f"GSC Search Analytics API error: {err}",
                recommendation="Verify Search Console API access and OAuth token for this property.",
            )
        if not gsc_result.has_data:
            return scored(
                name,
                what,
                meeting=False,
                method=DetectionMethod.FIRST_PARTY,
                detail=(
                    "GSC connected — no search performance data for this page yet "
                    "(0 impressions in Search Console)."
                ),
                recommendation=(
                    "Ensure the page is indexed and receiving impressions; "
                    "GSC data typically lags 2–3 days."
                ),
                priority=Priority.MEDIUM,
                confidence=Confidence.MEASURED,
            )
        row = gsc_result.data or {}
        ctr = float(row.get("ctr", 0.0))
        position = float(row.get("position", 99))
        benchmark = self._ctr_benchmark(position)
        return scored(
            name, what,
            meeting=ctr >= benchmark,
            partial=ctr >= benchmark * 0.5,
            method=DetectionMethod.FIRST_PARTY,
            detail=self._format_gsc_analytics(row),
            recommendation="Improve titles/meta descriptions to lift CTR for the page's position.",
            priority=Priority.MEDIUM,
            confidence=Confidence.MEASURED,
        )

    @staticmethod
    def _ctr_benchmark(position: float) -> float:
        """A rough expected CTR for a given average SERP position."""
        if position <= 1:  # Position 1
            return 0.25  # ~25% expected CTR
        if position <= 3:  # Top 3
            return 0.10  # ~10%
        if position <= 10:  # First page
            return 0.03  # ~3%
        return 0.01  # Beyond page 1

    def _ga4_row(
        self,
        ctx: AgentContext,
        ga4_data: dict,
        name: str,
        what: str,
        *,
        metric: str,
        good,  # Callable[[float], bool] deciding "Meeting"
        recommendation: str,
        lower_is_better: bool = False,
    ) -> ParameterResult:
        """Build a GA4-backed engagement row, or Manual when not connected."""
        if not (ctx.is_connected and ga4_data):  # No first-party data
            return manual(name, what, "Requires GA4 access (domain not connected).")  # Manual fallback
        try:  # GA4 returns metric values as strings
            value = float(ga4_data.get(metric, 0.0))  # Parse the metric value
        except (TypeError, ValueError):  # Unexpected format
            return manual(name, what, "GA4 metric unavailable for this page.")  # Treat as manual
        meeting = good(value)  # Apply the threshold predicate
        return scored(
            name, what,
            meeting=meeting,  # Threshold satisfied
            partial=not meeting and (value > 0),  # Has data but below threshold
            method=DetectionMethod.FIRST_PARTY,  # From GA4
            detail=f"{metric}={value:.3f}",  # Evidence
            recommendation=recommendation,  # Concrete fix
            priority=Priority.MEDIUM,
            confidence=Confidence.MEASURED,  # First-party measured
        )
