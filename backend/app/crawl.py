"""Fetch + render + parse the target page into a single shared `PageContext`.

This module owns all page I/O and all DOM-to-data extraction:
  1. PageContext  - the data object every agent reads from
  2. parser       - pure BeautifulSoup -> structured fields (no I/O)
  3. Fetcher      - httpx fetch + Playwright/Firecrawl render + robots/sitemap/llms + crawl

Agents are pure consumers of the resulting PageContext plus their own API calls,
which keeps each agent small and independently testable.
"""

from __future__ import annotations  # Forward references for typing

import asyncio  # Concurrency primitives for parallel fetching
import json  # Parse JSON-LD script blocks
import time  # Measure time-to-first-byte
import xml.etree.ElementTree as ET  # Parse sitemap XML
from dataclasses import dataclass, field  # Lightweight containers
from urllib.parse import urljoin, urlparse  # Resolve relative links + decompose URLs

import httpx  # Async HTTP client
from bs4 import BeautifulSoup  # HTML parsing

from app.clients import FirecrawlClient  # Render fallback
from app.config import Settings  # Crawl tunables


# ============================================================================
# 1. PageContext + supporting structures
# ============================================================================


@dataclass
class LinkInfo:
    """A single hyperlink discovered on the page."""

    url: str  # Absolute resolved URL
    anchor: str  # Visible anchor text (stripped)
    rel: str  # Value of the rel attribute (e.g. "nofollow")
    is_internal: bool  # True when the link stays on the same registrable host


@dataclass
class SitemapInfo:
    """Result of fetching and validating the sitemap(s)."""

    exists: bool = False  # Whether any sitemap was found
    is_index: bool = False  # Whether the sitemap is a <sitemapindex>
    url: str = ""  # The sitemap URL that was used
    url_count: int = 0  # Number of <loc> URLs discovered
    lastmod_count: int = 0  # How many entries carried a <lastmod>
    sub_sitemaps: list[str] = field(default_factory=list)  # Child sitemaps when an index


@dataclass
class PageContext:
    """All signals derived from the audited page, shared by every agent."""

    # --- Identity / network ---
    url: str  # The URL requested by the user (normalised)
    final_url: str = ""  # URL after redirects were followed
    status_code: int = 0  # Final HTTP status code
    redirect_chain: list[tuple[str, int]] = field(default_factory=list)  # (url, status) hops
    http_version: str = ""  # Negotiated protocol, e.g. "HTTP/2"
    ttfb_ms: float = 0.0  # Time-to-first-byte in milliseconds
    headers: dict[str, str] = field(default_factory=dict)  # Final response headers (lower-cased keys)
    tls_ok: bool = False  # Whether the connection used valid HTTPS

    # --- Markup ---
    raw_html: str = ""  # HTML exactly as returned by httpx (pre-JS)
    rendered_html: str = ""  # HTML after Playwright rendering (post-JS), if available
    html: str = ""  # Best available HTML (rendered if present, else raw)
    soup: BeautifulSoup | None = None  # Parsed DOM of `html`
    raw_soup: BeautifulSoup | None = None  # Parsed DOM of `raw_html` (for JS-render diffing)

    # --- Extracted text + structure ---
    title: str = ""  # <title> text
    meta_description: str = ""  # <meta name=description> content
    meta_robots: str = ""  # <meta name=robots> content
    canonical: str = ""  # <link rel=canonical> href
    lang: str = ""  # <html lang> value
    headings: dict[str, list[str]] = field(default_factory=dict)  # h1..h6 -> list of texts
    visible_text: str = ""  # Concatenated visible text of the page
    word_count: int = 0  # Number of words in `visible_text`
    paragraphs: list[str] = field(default_factory=list)  # Paragraph texts (<p>)

    # --- Links / media / data ---
    links: list[LinkInfo] = field(default_factory=list)  # All discovered links
    images: list[dict] = field(default_factory=list)  # {src, alt, has_dims, lazy}
    jsonld: list[dict] = field(default_factory=list)  # Parsed JSON-LD blocks
    meta_tags: dict[str, str] = field(default_factory=dict)  # name/property -> content

    # --- Site-level resources ---
    robots_txt: str = ""  # Contents of /robots.txt ("" if missing)
    robots_exists: bool = False  # Whether /robots.txt returned 200
    llms_txt_exists: bool = False  # Whether /llms.txt exists
    llms_full_txt_exists: bool = False  # Whether /llms-full.txt exists
    sitemap: SitemapInfo = field(default_factory=SitemapInfo)  # Sitemap discovery result

    # --- Shallow internal crawl ---
    internal_depths: dict[str, int] = field(default_factory=dict)  # url -> clicks-from-home depth
    link_status: dict[str, int] = field(default_factory=dict)  # checked url -> status code

    # --- PageSpeed Insights (filled by the orchestrator before agents run) ---
    psi_mobile: dict = field(default_factory=dict)  # Raw PSI response (mobile strategy)
    psi_desktop: dict = field(default_factory=dict)  # Raw PSI response (desktop strategy)

    # --- Errors collected while building the context ---
    errors: list[str] = field(default_factory=list)  # Non-fatal crawl errors

    @property
    def host(self) -> str:
        """Return the host of the final URL (e.g. "example.com")."""
        return urlparse(self.final_url or self.url).netloc.lower()  # Lower-cased network location

    @property
    def origin(self) -> str:
        """Return scheme://host for the audited page (used to build robots/sitemap URLs)."""
        parts = urlparse(self.final_url or self.url)  # Parse the effective URL
        return f"{parts.scheme}://{parts.netloc}"  # Reassemble the origin

    @property
    def internal_links(self) -> list[LinkInfo]:
        """All links that stay on the same host."""
        return [link for link in self.links if link.is_internal]  # Filter to internal links

    @property
    def outbound_links(self) -> list[LinkInfo]:
        """All links that point to a different host."""
        return [link for link in self.links if not link.is_internal]  # Filter to external links

    def header(self, name: str) -> str:
        """Case-insensitively fetch a response header value (or "")."""
        return self.headers.get(name.lower(), "")  # Headers are stored lower-cased


# ============================================================================
# 2. Parser (pure DOM -> data; no network calls)
# ============================================================================


def parse_into_context(ctx: PageContext) -> None:
    """Populate `ctx` text/structure fields from `ctx.html` in place."""
    # Choose rendered HTML when available, else the raw HTML
    html = ctx.html or ctx.rendered_html or ctx.raw_html
    soup = BeautifulSoup(html, "lxml") if html else BeautifulSoup("", "lxml")  # Parse best HTML
    ctx.soup = soup  # Store the parsed DOM for agents to query
    # Also parse the raw (pre-JS) HTML separately so the technical agent can diff JS rendering
    ctx.raw_soup = BeautifulSoup(ctx.raw_html, "lxml") if ctx.raw_html else soup

    _parse_head(ctx, soup)  # Title, meta description/robots, canonical, lang, meta tags
    _parse_headings(ctx, soup)  # h1..h6 trees
    _parse_text(ctx, soup)  # Visible text, paragraphs, word count
    _parse_links(ctx, soup)  # Internal/external links with anchors + rel
    _parse_images(ctx, soup)  # Image src/alt/dimensions/lazy
    _parse_jsonld(ctx, soup)  # JSON-LD structured data blocks


def _parse_head(ctx: PageContext, soup: BeautifulSoup) -> None:
    """Extract <title>, meta description/robots, canonical, lang and all meta tags."""
    title_tag = soup.find("title")  # The document title element
    ctx.title = title_tag.get_text(strip=True) if title_tag else ""  # Title text or ""

    html_tag = soup.find("html")  # Root element carries the lang attribute
    ctx.lang = (html_tag.get("lang", "") if html_tag else "").strip()  # Page language

    # Walk every <meta> tag and index it by name or property for fast lookup
    for meta in soup.find_all("meta"):  # Iterate all meta elements
        key = (meta.get("name") or meta.get("property") or "").lower()  # Prefer name, else property
        if not key:  # Skip meta tags without a name/property (e.g. charset)
            continue  # Nothing to index
        ctx.meta_tags[key] = meta.get("content", "")  # Record the content value

    ctx.meta_description = ctx.meta_tags.get("description", "")  # Standard meta description
    ctx.meta_robots = ctx.meta_tags.get("robots", "")  # Meta robots directives

    canonical = soup.find("link", rel=lambda v: v and "canonical" in v)  # <link rel=canonical>
    ctx.canonical = urljoin(ctx.final_url, canonical.get("href", "")) if canonical else ""  # Absolute


def _parse_headings(ctx: PageContext, soup: BeautifulSoup) -> None:
    """Collect the text of each heading level into ctx.headings."""
    for level in range(1, 7):  # Heading levels h1 through h6
        tag = f"h{level}"  # Build the tag name
        # Store the stripped text of every heading at this level
        ctx.headings[tag] = [h.get_text(strip=True) for h in soup.find_all(tag)]


def _parse_text(ctx: PageContext, soup: BeautifulSoup) -> None:
    """Extract visible text, paragraph list and word count."""
    # Remove non-content elements so they do not pollute the visible text
    for bad in soup(["script", "style", "noscript", "template"]):  # Iterate noise elements
        bad.extract()  # Drop them from the tree

    ctx.paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all("p")]  # Paragraph texts
    ctx.visible_text = soup.get_text(" ", strip=True)  # All remaining visible text
    ctx.word_count = len(ctx.visible_text.split())  # Word count via whitespace split


def _parse_links(ctx: PageContext, soup: BeautifulSoup) -> None:
    """Resolve all anchors to absolute URLs and classify internal vs external."""
    page_host = registrable_host(urlparse(ctx.final_url or ctx.url).netloc)  # www == apex
    for a in soup.find_all("a", href=True):  # Iterate anchors that have an href
        href = a["href"].strip()  # Raw href value
        if not href or href.startswith(("javascript:", "mailto:", "tel:", "#")):  # Skip non-navigational
            continue  # Ignore script/mail/phone/in-page anchors
        absolute = urljoin(ctx.final_url or ctx.url, href)  # Resolve relative to the page URL
        link_host = urlparse(absolute).netloc.lower()  # Host of the target
        rel = " ".join(a.get("rel", [])) if a.get("rel") else ""  # rel attribute as a string
        same_site = link_host == "" or registrable_host(link_host) == page_host
        ctx.links.append(  # Record the structured link
            LinkInfo(
                url=absolute,  # Absolute target URL
                anchor=a.get_text(strip=True),  # Visible anchor text
                rel=rel,  # rel value (e.g. nofollow)
                is_internal=same_site,  # Same registrable host => internal
            )
        )


def _parse_images(ctx: PageContext, soup: BeautifulSoup) -> None:
    """Record each image's src, alt, explicit dimensions and lazy-loading flag."""
    for img in soup.find_all("img"):  # Iterate image elements
        ctx.images.append(  # Record structured image data
            {
                "src": img.get("src", ""),  # Image source URL
                "alt": img.get("alt"),  # alt attribute (None when absent, "" when decorative)
                "has_dims": bool(img.get("width") and img.get("height")),  # Explicit width+height
                "lazy": img.get("loading", "") == "lazy",  # Native lazy loading enabled
            }
        )


def _parse_jsonld(ctx: PageContext, soup: BeautifulSoup) -> None:
    """Parse every <script type=application/ld+json> block into ctx.jsonld."""
    for script in soup.find_all("script", type="application/ld+json"):  # Iterate JSON-LD scripts
        text = script.string or script.get_text()  # Raw JSON text
        if not text:  # Empty script body
            continue  # Nothing to parse
        try:  # JSON-LD is frequently malformed in the wild
            data = json.loads(text)  # Parse the JSON
        except Exception:  # Malformed JSON
            continue  # Skip this block
        # JSON-LD may be a single object, a list, or a @graph wrapper
        if isinstance(data, list):  # A list of entities
            ctx.jsonld.extend(d for d in data if isinstance(d, dict))  # Add each dict
        elif isinstance(data, dict) and "@graph" in data:  # A graph container
            ctx.jsonld.extend(d for d in data["@graph"] if isinstance(d, dict))  # Add graph items
        elif isinstance(data, dict):  # A single entity
            ctx.jsonld.append(data)  # Add it directly


# ============================================================================
# 3. Fetcher (all page I/O)
# ============================================================================


def registrable_host(netloc: str) -> str:
    """Return a host key that treats www and non-www as the same site."""
    return netloc.lower().removeprefix("www.")


def normalise_url(url: str) -> str:
    """Ensure the URL has a scheme so httpx and urljoin behave predictably."""
    url = url.strip()  # Trim incidental whitespace
    if not url.startswith(("http://", "https://")):  # Missing scheme
        url = "https://" + url  # Default to HTTPS
    return url  # Normalised URL


class Fetcher:
    """Builds a PageContext for a single target URL."""

    def __init__(self, http: httpx.AsyncClient, settings: Settings, firecrawl: FirecrawlClient) -> None:
        """Store the HTTP client, settings and render fallback."""
        self._http = http  # Shared async HTTP client
        self._settings = settings  # Crawl tunables
        self._firecrawl = firecrawl  # Firecrawl render fallback

    async def fetch(self, url: str) -> PageContext:
        """Fetch everything and return a populated PageContext."""
        ctx = PageContext(url=normalise_url(url))  # Seed the context with the normalised URL
        await self._fetch_main(ctx)  # Fetch the primary document (fills raw HTML + network info)

        # Launch all independent discovery tasks concurrently for speed
        await asyncio.gather(
            self._render(ctx),  # Render JS (Playwright or Firecrawl) -> rendered_html
            self._fetch_robots(ctx),  # /robots.txt
            self._fetch_llms(ctx),  # /llms.txt and /llms-full.txt existence
            self._fetch_sitemap(ctx),  # sitemap discovery + validation
            return_exceptions=True,  # A failure in one task must not cancel the others
        )

        # Choose the best HTML (rendered if we got it, else raw) and parse it
        ctx.html = ctx.rendered_html or ctx.raw_html  # Prefer rendered DOM
        parse_into_context(ctx)  # Populate text/structure fields

        await self._internal_crawl(ctx)  # Shallow internal crawl (needs parsed links)
        return ctx  # The fully-populated context

    async def _fetch_main(self, ctx: PageContext) -> None:
        """GET the target URL, recording status, redirects, headers, protocol and TTFB."""
        start = time.perf_counter()  # Start TTFB timer
        try:  # The primary fetch can still fail (DNS, TLS, timeout)
            response = await self._http.get(ctx.url)  # Issue the GET (redirects auto-followed)
            ctx.ttfb_ms = (time.perf_counter() - start) * 1000.0  # Elapsed -> milliseconds
            ctx.status_code = response.status_code  # Final status code
            ctx.final_url = str(response.url)  # URL after redirects
            ctx.http_version = response.http_version  # Negotiated protocol (e.g. HTTP/2)
            ctx.raw_html = response.text  # Raw (pre-JS) HTML
            ctx.headers = {k.lower(): v for k, v in response.headers.items()}  # Lower-cased headers
            ctx.tls_ok = ctx.final_url.startswith("https://")  # HTTPS used end-to-end
            # Reconstruct the redirect chain from httpx history
            for hop in response.history:  # Each redirect response
                ctx.redirect_chain.append((str(hop.url), hop.status_code))  # Record url + status
            ctx.redirect_chain.append((ctx.final_url, ctx.status_code))  # Append the final hop
        except Exception as exc:  # Capture but do not raise
            ctx.errors.append(f"main fetch failed: {exc}")  # Record the error for the response
            ctx.final_url = ctx.url  # Fall back to the requested URL

    async def _render(self, ctx: PageContext) -> None:
        """Render the page with Playwright; fall back to Firecrawl; else leave empty."""
        if self._settings.enable_playwright:  # Playwright rendering is enabled
            html = await self._render_playwright(ctx.final_url or ctx.url)  # Try the headless browser
            if html:  # Rendering succeeded
                ctx.rendered_html = html  # Store rendered DOM
                return  # Done
        if self._firecrawl.enabled:  # Otherwise try the hosted Firecrawl fallback
            ctx.rendered_html = await self._firecrawl.rendered_html(ctx.final_url or ctx.url)  # Render

    async def _render_playwright(self, url: str) -> str:
        """Use a headless Chromium to obtain the post-JS HTML ("" on failure)."""
        try:  # Playwright may not be installed / browser may be missing
            from playwright.async_api import async_playwright  # Imported lazily to keep startup cheap

            async with async_playwright() as pw:  # Manage the Playwright lifecycle
                browser = await pw.chromium.launch(headless=True)  # Launch headless Chromium
                try:  # Ensure the browser is always closed
                    page = await browser.new_page(user_agent=self._settings.crawl_user_agent)  # New tab
                    # Wait for network to settle so client-rendered content is present
                    await page.goto(url, wait_until="networkidle", timeout=30000)  # Navigate
                    return await page.content()  # Serialised rendered DOM
                finally:  # Always release browser resources
                    await browser.close()  # Close the browser
        except Exception:  # Playwright missing/crash/timeout
            return ""  # Signal "no rendered HTML"

    async def _fetch_robots(self, ctx: PageContext) -> None:
        """Fetch /robots.txt and record its contents + existence."""
        robots_url = urljoin(ctx.origin + "/", "robots.txt")  # Build the robots URL from the origin
        try:  # Network call may fail
            response = await self._http.get(robots_url)  # Fetch robots.txt
            ctx.robots_exists = response.status_code == 200  # 200 => present
            ctx.robots_txt = response.text if ctx.robots_exists else ""  # Store contents when present
        except Exception:  # Any error
            ctx.robots_exists = False  # Treat as missing

    async def _fetch_llms(self, ctx: PageContext) -> None:
        """Probe for /llms.txt and /llms-full.txt (existence only)."""
        # Build absolute URLs for both LLM discovery files
        llms_url = urljoin(ctx.origin + "/", "llms.txt")  # /llms.txt
        llms_full_url = urljoin(ctx.origin + "/", "llms-full.txt")  # /llms-full.txt
        # Check both concurrently; each call returns a status code (0 on failure)
        llms_status, llms_full_status = await asyncio.gather(
            self._status(llms_url),  # Status of /llms.txt
            self._status(llms_full_url),  # Status of /llms-full.txt
        )
        ctx.llms_txt_exists = llms_status == 200  # Present when 200
        ctx.llms_full_txt_exists = llms_full_status == 200  # Present when 200

    async def _fetch_sitemap(self, ctx: PageContext) -> None:
        """Locate and validate the sitemap (from robots.txt or the default path)."""
        info = SitemapInfo()  # Start with an empty result
        sitemap_url = self._sitemap_url_from_robots(ctx) or urljoin(ctx.origin + "/", "sitemap.xml")  # Pick URL
        try:  # Network/XML parsing may fail
            response = await self._http.get(sitemap_url)  # Fetch the sitemap
            if response.status_code == 200 and response.text.strip():  # Present and non-empty
                info.exists = True  # Mark as found
                info.url = sitemap_url  # Record which URL was used
                self._parse_sitemap_xml(response.text, info)  # Parse counts + index detection
        except Exception:  # Any error
            pass  # Leave info.exists = False
        ctx.sitemap = info  # Attach the result to the context

    def _sitemap_url_from_robots(self, ctx: PageContext) -> str:
        """Return the first Sitemap: directive in robots.txt, if any."""
        for line in ctx.robots_txt.splitlines():  # Scan robots.txt lines
            if line.lower().startswith("sitemap:"):  # Sitemap directive
                return line.split(":", 1)[1].strip()  # Return the URL after the colon
        return ""  # No directive found

    def _parse_sitemap_xml(self, xml_text: str, info: SitemapInfo) -> None:
        """Populate counts and index detection from sitemap XML text."""
        try:  # Sitemaps are sometimes invalid XML
            root = ET.fromstring(xml_text.encode("utf-8"))  # Parse the XML tree
        except Exception:  # Invalid XML
            return  # Leave counts at zero
        # Strip XML namespaces so tag matching is simple
        tag = root.tag.split("}")[-1]  # Local name of the root element
        info.is_index = tag == "sitemapindex"  # <sitemapindex> => index of sub-sitemaps
        for loc in root.iter():  # Walk every element
            local = loc.tag.split("}")[-1]  # Local element name
            if local == "loc" and loc.text:  # A <loc> URL entry
                info.url_count += 1  # Count the URL
                if info.is_index:  # Sub-sitemap URLs inside an index
                    info.sub_sitemaps.append(loc.text.strip())  # Record the child sitemap
            elif local == "lastmod" and loc.text:  # A <lastmod> entry
                info.lastmod_count += 1  # Count populated lastmod values

    async def _internal_crawl(self, ctx: PageContext) -> None:
        """Breadth-first crawl (depth<=3) over internal links to compute reachability.

        Records click-depth per URL and the HTTP status of a bounded sample of
        internal links (used for broken-link and crawl-depth parameters).
        """
        max_pages = self._settings.crawl_max_internal_pages  # Cap on pages visited
        home = ctx.final_url or ctx.url  # Treat the audited page as the crawl root
        ctx.internal_depths[home] = 0  # The root is at depth 0
        # Seed the frontier with the homepage's internal links at depth 1
        frontier: list[tuple[str, int]] = [(link.url, 1) for link in ctx.internal_links]
        seen = {home}  # URLs already queued/visited

        # Check the status of a bounded sample of internal links concurrently
        sample = list({l.url for l in ctx.internal_links})[:max_pages]  # De-duplicate + cap
        statuses = await asyncio.gather(*(self._status(u) for u in sample))  # Parallel HEAD/GET
        ctx.link_status = dict(zip(sample, statuses))  # Map url -> status code

        # Record click-depth for reachable internal URLs without re-fetching their bodies
        while frontier and len(ctx.internal_depths) < max_pages:  # Bounded BFS
            current, depth = frontier.pop(0)  # Dequeue the next URL + its depth
            if current in seen or depth > 3:  # Skip visited or too-deep URLs
                continue  # Move on
            seen.add(current)  # Mark as seen
            ctx.internal_depths[current] = depth  # Record its depth from the homepage

    async def _status(self, url: str) -> int:
        """Return the HTTP status code for a URL (0 on failure), preferring HEAD."""
        try:  # Network call may fail
            response = await self._http.head(url)  # Light HEAD request
            if response.status_code >= 400:  # Some servers disallow HEAD
                response = await self._http.get(url, headers={"Range": "bytes=0-0"})  # Minimal GET
            return response.status_code  # Resolved status
        except Exception:  # Any error
            return 0  # Unknown status
