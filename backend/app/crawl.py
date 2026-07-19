"""Fetch + render + parse the target page into a single shared `PageContext`.

This module owns all page I/O and all DOM-to-data extraction:
  1. PageContext  - the data object every agent reads from
  2. parser       - pure BeautifulSoup -> structured fields (no I/O)
  3. Fetcher      - httpx fetch with Cloudflare bypass (Playwright session,
                    then Firecrawl for critical bodies) + robots/sitemap/llms + crawl

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
    locs: list[str] = field(default_factory=list)  # Sampled <loc> URLs from the sitemap
    http_loc_count: int = 0  # HTTP locs when the site is served over HTTPS
    loc_status: dict[str, int] = field(default_factory=dict)  # loc url -> HTTP status
    blocked: bool = False  # True when bot protection blocked sitemap fetch
    block_detail: str = ""  # Evidence when blocked (e.g. status=403)


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

    # --- HeuristicsAI site audit supplementary crawl signals ---
    html_byte_size: int = 0  # Raw HTML payload size in bytes
    content_encoding: str = ""  # Content-Encoding response header
    has_doctype: bool = False  # Whether raw HTML declares a DOCTYPE
    has_charset: bool = False  # Charset declared in meta or Content-Type
    has_meta_refresh: bool = False  # Meta http-equiv=refresh present
    script_urls: list[str] = field(default_factory=list)  # Absolute script src URLs
    stylesheet_urls: list[str] = field(default_factory=list)  # Absolute stylesheet href URLs
    asset_status: dict[str, int] = field(default_factory=dict)  # JS/CSS url -> status
    asset_cache: dict[str, str] = field(default_factory=dict)  # JS/CSS url -> Cache-Control
    asset_encoding: dict[str, str] = field(default_factory=dict)  # JS/CSS url -> Content-Encoding
    image_status: dict[str, int] = field(default_factory=dict)  # Image url -> status
    external_link_status: dict[str, int] = field(default_factory=dict)  # External href -> status
    malformed_links: list[str] = field(default_factory=list)  # Hrefs that failed URL validation
    crawl_failures: list[dict[str, str]] = field(default_factory=list)  # {url, reason}
    dns_ok: bool = True  # False when the primary host failed DNS resolution
    www_resolve_ok: bool = True  # www vs apex redirect consistency
    tls_version: str = ""  # Negotiated TLS version (e.g. TLSv1.3)
    tls_cert_hostname_ok: bool = True  # Certificate CN/SAN matches host
    tls_cert_days_remaining: int | None = None  # Days until certificate expiry
    robots_blocked_internal: list[str] = field(default_factory=list)  # Internal assets blocked by robots
    robots_blocked_external: list[str] = field(default_factory=list)  # External assets blocked by robots
    orphaned_sitemap_pages: list[str] = field(default_factory=list)  # Sitemap URLs with no inlinks
    tls_hosts: list[dict] = field(default_factory=list)  # Per-host TLS {host, version, cipher, weak_cipher, sni_ok}
    resource_page_links: list[dict] = field(default_factory=list)  # {url, content_type} anchor-linked resources
    crawl_page_status: dict[str, int] = field(default_factory=dict)  # shallow-crawl url -> HTTP status
    crawled_titles: dict[str, str] = field(default_factory=dict)  # shallow-crawl url -> title text
    crawled_outlinks: dict[str, list[str]] = field(default_factory=dict)  # normalized url -> internal targets
    internal_inlink_counts: dict[str, int] = field(default_factory=dict)  # normalized url -> incoming internal links
    http_homepage_https_ok: bool = True  # HTTP homepage redirects/canonicals to HTTPS
    http_homepage_detail: str = ""  # Evidence from HTTP homepage probe

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
    _parse_assets(ctx, soup)  # Script and stylesheet URLs
    _parse_markup_flags(ctx, soup)  # DOCTYPE, charset, meta refresh
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
        if not _is_valid_http_url(absolute):
            ctx.malformed_links.append(href)
            continue
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
    base = ctx.final_url or ctx.url
    for img in soup.find_all("img"):  # Iterate image elements
        src = img.get("src", "")
        absolute = urljoin(base, src) if src else ""
        ctx.images.append(  # Record structured image data
            {
                "src": src,  # Raw src attribute
                "absolute": absolute,  # Resolved absolute URL
                "alt": img.get("alt"),  # alt attribute (None when absent, "" when decorative)
                "has_dims": bool(img.get("width") and img.get("height")),  # Explicit width+height
                "lazy": img.get("loading", "") == "lazy",  # Native lazy loading enabled
            }
        )


def _parse_assets(ctx: PageContext, soup: BeautifulSoup) -> None:
    """Collect absolute script and stylesheet URLs referenced by the page."""
    base = ctx.final_url or ctx.url
    for script in soup.find_all("script", src=True):
        ctx.script_urls.append(urljoin(base, script["src"].strip()))
    for link in soup.find_all("link", href=True):
        rel = " ".join(link.get("rel", [])) if link.get("rel") else ""
        if "stylesheet" in rel.lower():
            ctx.stylesheet_urls.append(urljoin(base, link["href"].strip()))


def _parse_markup_flags(ctx: PageContext, soup: BeautifulSoup) -> None:
    """Detect DOCTYPE, charset and meta refresh from markup and headers."""
    raw = (ctx.raw_html or ctx.html or "").lstrip()
    ctx.has_doctype = raw.lower().startswith("<!doctype")
    charset_header = ctx.header("content-type")
    ctx.has_charset = bool(
        soup.find("meta", charset=True)
        or soup.find("meta", attrs={"http-equiv": lambda v: v and v.lower() == "content-type"})
        or "charset=" in charset_header.lower()
    )
    refresh = soup.find("meta", attrs={"http-equiv": lambda v: v and v.lower() == "refresh"})
    ctx.has_meta_refresh = refresh is not None and bool(refresh.get("content"))


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


def _is_valid_http_url(url: str) -> bool:
    """Return True when `url` looks like a fetchable http(s) URL."""
    try:
        parsed = urlparse(url)
    except Exception:
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    if not parsed.netloc or " " in url:
        return False
    return True


def normalize_crawl_url(url: str) -> str:
    """Normalize a crawl URL for depth/inlink graph keys (scheme + host + path)."""
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    path = parsed.path or "/"
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")
    return f"{parsed.scheme}://{host}{path}"


def extract_internal_link_urls(html: str, base_url: str) -> list[str]:
    """Parse internal hyperlink targets from an HTML snippet."""
    page_host = registrable_host(urlparse(base_url).netloc)
    soup = BeautifulSoup(html, "lxml")
    out: list[str] = []
    seen: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()
        if not href or href.startswith(("javascript:", "mailto:", "tel:", "#")):
            continue
        absolute = urljoin(base_url, href)
        if not _is_valid_http_url(absolute):
            continue
        link_host = urlparse(absolute).netloc.lower()
        if link_host and registrable_host(link_host) != page_host:
            continue
        norm = normalize_crawl_url(absolute)
        if norm not in seen:
            seen.add(norm)
            out.append(norm)
    return out


_RESOURCE_LINK_EXTENSIONS = (
    ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".bmp", ".ico",
    ".mp4", ".webm", ".mp3", ".wav", ".zip", ".rar", ".7z",
    ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".csv",
)

_WEAK_CIPHER_MARKERS = ("RC4", "DES", "3DES", "NULL", "EXPORT", "ANON", "MD5")


def _discover_site_hosts(ctx: PageContext) -> list[str]:
    """Return unique HTTPS hostnames under the same registrable domain (cap 15)."""
    apex = registrable_host(ctx.host)
    hosts: set[str] = set()
    primary = urlparse(ctx.final_url or ctx.url).netloc.lower()
    if primary:
        hosts.add(primary)
    for url in ctx.sitemap.locs + [link.url for link in ctx.links] + [ctx.canonical]:
        if not url:
            continue
        host = urlparse(url).netloc.lower()
        if host and registrable_host(host) == apex:
            hosts.add(host)
    return sorted(hosts)[:15]


def _cert_hostnames(cert: dict) -> set[str]:
    """Extract lower-cased hostnames from a peer certificate dict."""
    names: set[str] = set()
    for _key, value in cert.get("subjectAltName", []):
        if _key == "DNS" and value:
            names.add(value.lower().removeprefix("www."))
    for rdns in cert.get("subject", ()):
        for key, value in rdns:
            if key == "commonName" and value:
                names.add(value.lower().removeprefix("www."))
    return names


def _cert_matches_host(cert: dict, hostname: str) -> bool:
    """Return True when the certificate covers `hostname`."""
    host = hostname.lower().removeprefix("www.")
    names = _cert_hostnames(cert)
    if host in names:
        return True
    return any(name.startswith("*.") and host.endswith(name[2:]) for name in names)


def _cert_subject_key(cert: dict) -> tuple:
    """Fingerprint certificate identity for comparison."""
    sans = tuple(sorted(_cert_hostnames(cert)))
    cn = ""
    for rdns in cert.get("subject", ()):
        for key, value in rdns:
            if key == "commonName":
                cn = value
    return (cn, sans)


def _is_weak_tls(version: str, cipher_name: str) -> bool:
    """Flag deprecated TLS versions and weak cipher suites."""
    if version in ("TLSv1", "TLSv1.1"):
        return True
    upper = cipher_name.upper()
    return any(marker in upper for marker in _WEAK_CIPHER_MARKERS)


def _tls_inspect_host(hostname: str) -> dict:
    """Blocking TLS probe: version, cipher strength, cert match, SNI behaviour."""
    import datetime
    import socket
    import ssl

    result: dict = {
        "host": hostname,
        "version": "",
        "cipher": "",
        "weak_cipher": False,
        "hostname_ok": False,
        "sni_ok": True,
        "days_remaining": None,
    }
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((hostname, 443), timeout=8) as raw:
            with ctx.wrap_socket(raw, server_hostname=hostname) as ss:
                result["version"] = ss.version() or ""
                cipher = ss.cipher()
                if cipher:
                    result["cipher"] = cipher[0]
                    result["weak_cipher"] = _is_weak_tls(result["version"], cipher[0])
                with_cert = ss.getpeercert() or {}
                result["hostname_ok"] = _cert_matches_host(with_cert, hostname)
                not_after = with_cert.get("notAfter")
                if not_after:
                    expiry = datetime.datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z")
                    result["days_remaining"] = (expiry - datetime.datetime.utcnow()).days

        without_cert: dict = {}
        try:
            ctx_no_verify = ssl.create_default_context()
            ctx_no_verify.check_hostname = False
            ctx_no_verify.verify_mode = ssl.CERT_NONE
            ip = socket.gethostbyname(hostname)
            with socket.create_connection((ip, 443), timeout=8) as raw:
                with ctx_no_verify.wrap_socket(raw) as ss:
                    without_cert = ss.getpeercert() or {}
        except Exception:
            without_cert = {}

        with_match = _cert_matches_host(with_cert, hostname)
        without_match = _cert_matches_host(without_cert, hostname) if without_cert else False
        if with_match:
            result["sni_ok"] = True
        elif without_cert and _cert_subject_key(with_cert) == _cert_subject_key(without_cert):
            result["sni_ok"] = False
        else:
            result["sni_ok"] = without_match
    except Exception as exc:
        result["error"] = str(exc)
        result["sni_ok"] = False
    return result


def registrable_host(netloc: str) -> str:
    """Return a host key that treats www and non-www as the same site."""
    return netloc.lower().removeprefix("www.")


def normalise_url(url: str) -> str:
    """Ensure the URL has a scheme so httpx and urljoin behave predictably."""
    url = url.strip()  # Trim incidental whitespace
    if not url.startswith(("http://", "https://")):  # Missing scheme
        url = "https://" + url  # Default to HTTPS
    return url  # Normalised URL


# Realistic browser UA for Cloudflare bypass (auditor UA is often challenged).
_BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

_CF_BODY_MARKERS = (
    "attention required",
    "just a moment",
    "cf-browser-verification",
    "challenge-platform",
    "cdn-cgi/challenge",
    "cloudflare ray id",
    "checking your browser",
    "enable javascript and cookies to continue",
    "cf-chl",
    "cf-error-details",
    "error code 1020",
    "error code 1015",
    "access denied",
    "sorry, you have been blocked",
    "blocked by security policy",
)

# Soft-block statuses often returned by Cloudflare/WAF instead of a real page error.
# (503 is only treated as a bot block when CF challenge headers/body are present.)
_BOT_SOFT_BLOCK_STATUSES = frozenset({401, 403, 429})

# Sentinel status: URL could not be verified because of bot protection (not a site 4xx/5xx).
STATUS_BOT_BLOCKED = -403


def is_http_error_status(status: int) -> bool:
    """True for real HTTP client/server errors (excludes bot-block sentinel)."""
    return status >= 400


def is_bot_blocked_status(status: int) -> bool:
    """True when status is the bot-protection sentinel."""
    return status == STATUS_BOT_BLOCKED


def is_reportable_http_error(status: int) -> bool:
    """True for real broken-page statuses (excludes bot sentinel and WAF soft-blocks)."""
    return is_http_error_status(status) and status not in _BOT_SOFT_BLOCK_STATUSES


@dataclass
class FetchResult:
    """Normalised response from httpx, Playwright, or Firecrawl."""

    status_code: int = 0
    text: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    final_url: str = ""
    http_version: str = ""
    content: bytes = b""
    history: list[tuple[str, int]] = field(default_factory=list)
    blocked: bool = False
    via: str = "httpx"


def _is_challenge_body(text: str) -> bool:
    """Return True when body looks like a Cloudflare/bot interstitial."""
    if not text:
        return False
    lower = text[:8000].lower()
    return any(marker in lower for marker in _CF_BODY_MARKERS)


def _has_cloudflare_headers(headers: dict[str, str] | None) -> bool:
    headers = headers or {}
    server = headers.get("server", "").lower()
    return (
        "cf-ray" in headers
        or "cf-cache-status" in headers
        or "cloudflare" in server
        or server == "cloudflare"
    )


def _is_challenge_response(status_code: int, text: str, headers: dict[str, str] | None = None) -> bool:
    """Return True when status/body/headers indicate bot protection."""
    headers = headers or {}
    if _is_challenge_body(text):
        return True
    if status_code in (*_BOT_SOFT_BLOCK_STATUSES, 503) and _has_cloudflare_headers(headers):
        return True
    # Empty/short deny bodies are typical of edge blocks without an HTML challenge page.
    if status_code in _BOT_SOFT_BLOCK_STATUSES and len((text or "").strip()) < 64:
        return True
    return False


def _origin_probe_status(
    status_code: int,
    text: str = "",
    headers: dict[str, str] | None = None,
    *,
    blocked: bool = False,
) -> int:
    """Normalize an audited-origin probe status for reporting.

    Bot challenges and soft-block denials (401/403/429) become STATUS_BOT_BLOCKED
    so public-site audits do not treat Cloudflare/WAF blocks as real broken pages.
    Real 404/410 and non-CF 5xx still pass through.
    """
    if blocked or _is_challenge_response(status_code, text, headers):
        return STATUS_BOT_BLOCKED
    if status_code in _BOT_SOFT_BLOCK_STATUSES:
        return STATUS_BOT_BLOCKED
    return status_code or 0


def _looks_like_sitemap(text: str) -> bool:
    """Return True when text appears to be sitemap XML."""
    sample = text.lstrip()[:2000].lower()
    return "<urlset" in sample or "<sitemapindex" in sample


class Fetcher:
    """Builds a PageContext for a single target URL."""

    def __init__(self, http: httpx.AsyncClient, settings: Settings, firecrawl: FirecrawlClient) -> None:
        """Store the HTTP client, settings and render fallback."""
        self._http = http  # Shared async HTTP client
        self._settings = settings  # Crawl tunables
        self._firecrawl = firecrawl  # Firecrawl render fallback
        self._audited_host = ""  # Registrable host for the audit target
        self._pw = None  # Playwright driver (lazy)
        self._browser = None  # Chromium browser (lazy)
        self._context = None  # Browser context with clearance cookies
        self._pw_lock = asyncio.Lock()  # Serialize session creation / navigations
        self._pw_ready = False  # True after session bootstrap finished
        self._pw_cleared = False  # True when CF challenge was cleared once
        self._pw_skip = False  # True when Playwright cannot beat bot protection

    async def fetch(self, url: str) -> PageContext:
        """Fetch everything and return a populated PageContext."""
        normalised = normalise_url(url)
        ctx = PageContext(url=normalised)
        self._audited_host = registrable_host(urlparse(normalised).netloc)
        try:
            await self._fetch_main(ctx)
            # robots before sitemap so Sitemap: directive is available
            await self._fetch_robots(ctx)
            await asyncio.gather(
                self._render(ctx),
                self._fetch_llms(ctx),
                self._fetch_sitemap(ctx),
                return_exceptions=True,
            )
            ctx.html = ctx.rendered_html or ctx.raw_html
            if _is_challenge_body(ctx.html):
                ctx.errors.append("page HTML still looks like a bot-protection challenge")
            parse_into_context(ctx)
            await self._internal_crawl(ctx)
            await self._supplementary_probes(ctx)
            return ctx
        finally:
            await self._close_playwright()

    def _is_audited_url(self, url: str) -> bool:
        """True when URL belongs to the audited registrable host (or host unset)."""
        if not self._audited_host:
            return True
        host = registrable_host(urlparse(url).netloc)
        return not host or host == self._audited_host

    async def _get(
        self,
        url: str,
        *,
        allow_firecrawl: bool = True,
        headers: dict[str, str] | None = None,
    ) -> FetchResult:
        """GET url via httpx, escalating to Playwright then Firecrawl on CF blocks."""
        result = await self._httpx_get(url, headers=headers)
        audited = self._is_audited_url(url)
        # Soft-block statuses on the audited origin always escalate — CF often
        # returns bare 403s that look like "real" errors without challenge HTML.
        soft_block = audited and (
            result.blocked or result.status_code in _BOT_SOFT_BLOCK_STATUSES or not result.status_code
        )
        if result.status_code and not result.blocked and not soft_block:
            return result

        if not audited:
            return result

        if self._settings.enable_playwright and not self._pw_skip:
            pw = await self._playwright_get(url, allow_navigate=True)
            if pw.status_code and not pw.blocked and pw.status_code not in _BOT_SOFT_BLOCK_STATUSES:
                return pw
            if pw.text and not pw.blocked and not _is_challenge_body(pw.text):
                return pw
            if pw.status_code or pw.text:
                result = pw

        if allow_firecrawl and self._firecrawl.enabled:
            fc = await self._firecrawl_get(url)
            if fc.text and not fc.blocked:
                return fc

        result.blocked = True
        return result

    async def _httpx_get(self, url: str, headers: dict[str, str] | None = None) -> FetchResult:
        """Plain httpx GET; marks blocked when Cloudflare challenges the client."""
        try:
            response = await self._http.get(url, headers=headers or {})
            text = response.text
            hdrs = {k.lower(): v for k, v in response.headers.items()}
            blocked = _is_challenge_response(response.status_code, text, hdrs)
            history = [(str(hop.url), hop.status_code) for hop in response.history]
            history.append((str(response.url), response.status_code))
            return FetchResult(
                status_code=response.status_code,
                text="" if blocked else text,
                headers=hdrs,
                final_url=str(response.url),
                http_version=response.http_version,
                content=b"" if blocked else response.content,
                history=history,
                blocked=blocked,
                via="httpx",
            )
        except Exception:
            # Treat transport failure as escalate-worthy for audited hosts.
            return FetchResult(status_code=0, blocked=True, via="httpx")

    async def _firecrawl_get(self, url: str) -> FetchResult:
        """Fetch body via Firecrawl scrape (rawHtml preferred)."""
        text = await self._firecrawl.fetch_body(url)
        if not text or _is_challenge_body(text):
            return FetchResult(blocked=True, via="firecrawl")
        return FetchResult(
            status_code=200,
            text=text,
            final_url=url,
            content=text.encode("utf-8", errors="ignore"),
            via="firecrawl",
        )

    async def _ensure_playwright_session(self, seed_url: str) -> bool:
        """Launch a shared Chromium context and attempt to clear CF challenge once."""
        if self._pw_skip:
            return False
        if self._pw_ready and self._context is not None:
            return True
        if not self._settings.enable_playwright:
            return False
        async with self._pw_lock:
            if self._pw_skip:
                return False
            if self._pw_ready and self._context is not None:
                return True
            try:
                from playwright.async_api import async_playwright

                self._pw = await async_playwright().start()
                self._browser = await self._pw.chromium.launch(headless=True)
                self._context = await self._browser.new_context(
                    user_agent=_BROWSER_UA,
                    viewport={"width": 1280, "height": 720},
                    ignore_https_errors=True,
                )
                page = await self._context.new_page()
                try:
                    await page.goto(seed_url, wait_until="domcontentloaded", timeout=20000)
                    cleared = False
                    for _ in range(8):
                        content = await page.content()
                        if not _is_challenge_body(content):
                            cleared = True
                            break
                        await page.wait_for_timeout(750)
                    self._pw_cleared = cleared
                    if not cleared:
                        # Headless Chromium could not pass the challenge; prefer Firecrawl.
                        self._pw_skip = True
                finally:
                    await page.close()
                if self._pw_skip:
                    await self._close_playwright()
                    return False
                self._pw_ready = self._context is not None
                return self._pw_ready
            except Exception:
                self._pw_skip = True
                await self._close_playwright()
                return False

    async def _close_playwright(self) -> None:
        """Release Playwright resources for this audit."""
        context, browser, pw = self._context, self._browser, self._pw
        self._context = self._browser = self._pw = None
        self._pw_ready = False
        for obj, method in ((context, "close"), (browser, "close"), (pw, "stop")):
            if obj is None:
                continue
            try:
                await getattr(obj, method)()
            except Exception:
                pass

    async def _playwright_request(self, url: str) -> FetchResult:
        """Lightweight GET via Playwright request API (no page navigation)."""
        if self._pw_skip or not await self._ensure_playwright_session(url):
            return FetchResult(blocked=True, via="playwright")
        assert self._context is not None
        try:
            resp = await self._context.request.get(url, timeout=15000)
            text = await resp.text()
            hdrs = {k.lower(): v for k, v in resp.headers.items()}
            blocked = _is_challenge_response(resp.status, text, hdrs)
            return FetchResult(
                status_code=resp.status,
                text="" if blocked else text,
                headers=hdrs,
                final_url=resp.url,
                content=b"" if blocked else text.encode("utf-8", errors="ignore"),
                blocked=blocked,
                via="playwright",
            )
        except Exception:
            return FetchResult(blocked=True, via="playwright")

    async def _playwright_get(self, url: str, *, allow_navigate: bool = True) -> FetchResult:
        """GET via shared Playwright context (request API, optional single navigation)."""
        result = await self._playwright_request(url)
        if not result.blocked and result.status_code:
            return result
        if not allow_navigate or self._pw_skip or self._context is None:
            return result

        async with self._pw_lock:
            if self._pw_skip or self._context is None:
                return FetchResult(blocked=True, via="playwright")
            page = await self._context.new_page()
            try:
                resp = await page.goto(url, wait_until="domcontentloaded", timeout=20000)
                status = resp.status if resp else 0
                text = ""
                if resp is not None:
                    try:
                        text = await resp.text()
                    except Exception:
                        text = await page.content()
                else:
                    text = await page.content()

                for _ in range(6):
                    if not _is_challenge_response(status or 403, text, {}):
                        break
                    await page.wait_for_timeout(750)
                    text = await page.content()
                    status = 200

                if _is_challenge_response(status or 403, text, {}):
                    self._pw_skip = True
                    return FetchResult(
                        status_code=status or 403,
                        text="",
                        final_url=page.url,
                        blocked=True,
                        via="playwright",
                    )
                self._pw_cleared = True
                return FetchResult(
                    status_code=status or 200,
                    text=text,
                    final_url=page.url,
                    content=text.encode("utf-8", errors="ignore"),
                    via="playwright",
                )
            except Exception:
                return FetchResult(blocked=True, via="playwright")
            finally:
                await page.close()

    async def _fetch_main(self, ctx: PageContext) -> None:
        """GET the target URL, recording status, redirects, headers, protocol and TTFB."""
        start = time.perf_counter()
        try:
            result = await self._get(ctx.url, allow_firecrawl=True)
            ctx.ttfb_ms = (time.perf_counter() - start) * 1000.0
            ctx.status_code = result.status_code or (403 if result.blocked else 0)
            ctx.final_url = result.final_url or ctx.url
            ctx.http_version = result.http_version or ctx.http_version
            ctx.raw_html = result.text
            ctx.html_byte_size = len(result.content) if result.content else len(result.text.encode("utf-8", errors="ignore"))
            ctx.content_encoding = result.headers.get("content-encoding", "")
            ctx.headers = result.headers
            ctx.tls_ok = ctx.final_url.startswith("https://")
            ctx.redirect_chain = list(result.history) or [(ctx.final_url, ctx.status_code)]
            if result.blocked:
                ctx.errors.append(f"main fetch blocked by bot protection (via={result.via})")
            elif result.via != "httpx":
                ctx.errors.append(f"main fetch used bypass via={result.via}")
            # Keep audited host in sync after redirects
            self._audited_host = registrable_host(urlparse(ctx.final_url).netloc) or self._audited_host
        except Exception as exc:
            ctx.errors.append(f"main fetch failed: {exc}")
            ctx.final_url = ctx.url
            msg = str(exc).lower()
            if "getaddrinfo" in msg or "name or service not known" in msg or "nodename nor servname" in msg:
                ctx.dns_ok = False

    async def _render(self, ctx: PageContext) -> None:
        """Render the page with Playwright; fall back to Firecrawl; else leave empty."""
        url = ctx.final_url or ctx.url
        if self._settings.enable_playwright:
            html = await self._render_via_session(url)
            if not html:
                html = await self._render_playwright(url)
            if html and not _is_challenge_body(html):
                ctx.rendered_html = html
                return
        if self._firecrawl.enabled:
            html = await self._firecrawl.rendered_html(url)
            if html and not _is_challenge_body(html):
                ctx.rendered_html = html

    async def _render_via_session(self, url: str) -> str:
        """Render using the shared bypass browser context when available."""
        if self._pw_skip or not await self._ensure_playwright_session(url):
            return ""
        assert self._context is not None
        async with self._pw_lock:
            if self._pw_skip or self._context is None:
                return ""
            page = await self._context.new_page()
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=20000)
                html = await page.content()
                if _is_challenge_body(html):
                    self._pw_skip = True
                    return ""
                return html
            except Exception:
                return ""
            finally:
                await page.close()

    async def _render_playwright(self, url: str) -> str:
        """Use a one-off headless Chromium to obtain post-JS HTML ("" on failure)."""
        try:
            from playwright.async_api import async_playwright

            async with async_playwright() as pw:
                browser = await pw.chromium.launch(headless=True)
                try:
                    page = await browser.new_page(user_agent=_BROWSER_UA)
                    await page.goto(url, wait_until="networkidle", timeout=30000)
                    html = await page.content()
                    return "" if _is_challenge_body(html) else html
                finally:
                    await browser.close()
        except Exception:
            return ""

    async def _fetch_robots(self, ctx: PageContext) -> None:
        """Fetch /robots.txt and record its contents + existence."""
        robots_url = urljoin(ctx.origin + "/", "robots.txt")
        try:
            result = await self._get(robots_url, allow_firecrawl=True)
            if result.blocked or _is_challenge_body(result.text):
                ctx.robots_exists = False
                ctx.robots_txt = ""
                ctx.errors.append(f"robots.txt blocked by bot protection (via={result.via})")
                return
            ctx.robots_exists = result.status_code == 200 and bool(result.text.strip())
            ctx.robots_txt = result.text if ctx.robots_exists else ""
        except Exception:
            ctx.robots_exists = False

    async def _fetch_llms(self, ctx: PageContext) -> None:
        """Probe for /llms.txt and /llms-full.txt (existence only)."""
        llms_url = urljoin(ctx.origin + "/", "llms.txt")
        llms_full_url = urljoin(ctx.origin + "/", "llms-full.txt")
        llms_status, llms_full_status = await asyncio.gather(
            self._status(llms_url),
            self._status(llms_full_url),
        )
        ctx.llms_txt_exists = llms_status == 200
        ctx.llms_full_txt_exists = llms_full_status == 200

    async def _fetch_sitemap(self, ctx: PageContext) -> None:
        """Locate and validate the sitemap (from robots.txt or the default path)."""
        info = SitemapInfo()
        sitemap_url = self._sitemap_url_from_robots(ctx) or urljoin(ctx.origin + "/", "sitemap.xml")
        info.url = sitemap_url
        try:
            result = await self._get(sitemap_url, allow_firecrawl=True)
            if result.blocked or _is_challenge_body(result.text):
                info.blocked = True
                info.block_detail = f"bot_protection status={result.status_code or 403} via={result.via}"
                ctx.errors.append(f"sitemap blocked: {info.block_detail}")
            elif result.status_code == 200 and result.text.strip():
                if _looks_like_sitemap(result.text) or not _is_challenge_body(result.text):
                    info.exists = True
                    self._parse_sitemap_xml(result.text, info)
                    if info.url_count == 0 and not _looks_like_sitemap(result.text):
                        info.exists = False
        except Exception:
            pass
        ctx.sitemap = info

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
                loc_url = loc.text.strip()
                info.url_count += 1  # Count the URL
                if len(info.locs) < 200:  # Cap stored locs for memory
                    info.locs.append(loc_url)
                if info.is_index:  # Sub-sitemap URLs inside an index
                    info.sub_sitemaps.append(loc_url)  # Record the child sitemap
            elif local == "lastmod" and loc.text:  # A <lastmod> entry
                info.lastmod_count += 1  # Count populated lastmod values

    async def _internal_crawl(self, ctx: PageContext) -> None:
        """Breadth-first crawl (depth<=3) over internal links.

        Fetches each visited page, records click-depth, outgoing links, titles,
        and aggregates incoming internal link counts for the site audit PDF.
        """
        max_pages = self._settings.crawl_max_internal_pages
        home = normalize_crawl_url(ctx.final_url or ctx.url)
        page_host = registrable_host(urlparse(home).netloc)

        ctx.internal_depths[home] = 0
        ctx.crawl_page_status[home] = ctx.status_code or 0
        if ctx.title:
            ctx.crawled_titles[home] = ctx.title

        home_outlinks = list(
            dict.fromkeys(normalize_crawl_url(link.url) for link in ctx.internal_links)
        )
        ctx.crawled_outlinks[home] = home_outlinks

        sample = home_outlinks[:max_pages]
        statuses = await asyncio.gather(*(self._status(u) for u in sample))
        ctx.link_status = dict(zip(sample, statuses))
        for url, status in ctx.link_status.items():
            if status == STATUS_BOT_BLOCKED or status in _BOT_SOFT_BLOCK_STATUSES:
                # Bot protection blocked verification — not a real site 4xx/5xx.
                continue
            if status == 0:
                ctx.crawl_failures.append({"url": url, "reason": "unreachable"})
            elif is_reportable_http_error(status):
                ctx.crawl_failures.append({"url": url, "reason": f"http_{status}"})

        frontier: list[tuple[str, int]] = [(url, 1) for url in home_outlinks]
        seen = {home}

        while frontier and len(ctx.internal_depths) < max_pages:
            current, depth = frontier.pop(0)
            current = normalize_crawl_url(current)
            if current in seen or depth > 3:
                continue
            if registrable_host(urlparse(current).netloc) != page_host:
                continue
            seen.add(current)
            ctx.internal_depths[current] = depth

            if current == home:
                outlinks = ctx.crawled_outlinks.get(home, [])
            else:
                status, html = await self._fetch_crawl_snippet(current)
                ctx.crawl_page_status[current] = status
                if (
                    status == STATUS_BOT_BLOCKED
                    or status == 0
                    or status >= 400
                    or not html
                ):
                    ctx.crawled_outlinks[current] = []
                    continue
                soup = BeautifulSoup(html, "lxml")
                title_tag = soup.find("title")
                title = (title_tag.string or "").strip() if title_tag and title_tag.string else ""
                if title:
                    ctx.crawled_titles[current] = title
                outlinks = extract_internal_link_urls(html, current)
                ctx.crawled_outlinks[current] = outlinks

            for link in outlinks:
                norm = normalize_crawl_url(link)
                if registrable_host(urlparse(norm).netloc) != page_host:
                    continue
                if norm not in seen and depth < 3:
                    frontier.append((norm, depth + 1))

        inlinks: dict[str, int] = {}
        for targets in ctx.crawled_outlinks.values():
            for target in targets:
                norm = normalize_crawl_url(target)
                if registrable_host(urlparse(norm).netloc) == page_host:
                    inlinks[norm] = inlinks.get(norm, 0) + 1
        ctx.internal_inlink_counts = inlinks

    async def _fetch_crawl_snippet(self, url: str) -> tuple[int, str]:
        """Fetch HTML for shallow-crawl link/title parsing (with CF bypass on origin).

        Firecrawl is not used here — it would spray paid scrapes across the BFS.
        Critical resources (main/robots/sitemap) already escalate to Firecrawl in `_get`.
        """
        try:
            if self._is_audited_url(url):
                result = await self._get(url, allow_firecrawl=False)
                status = _origin_probe_status(
                    result.status_code,
                    result.text,
                    result.headers,
                    blocked=result.blocked,
                )
                if status == STATUS_BOT_BLOCKED or status == 0:
                    return status, ""
                if status >= 400 or not result.text:
                    return status, ""
                return status or 200, result.text[:16384]
            response = await self._http.get(url, headers={"Range": "bytes=0-16384"})
            return response.status_code, response.text if response.status_code < 400 else ""
        except Exception:
            return 0, ""

    async def _httpx_status_with_headers(self, url: str) -> tuple[int, dict[str, str], str]:
        """HEAD/GET via httpx; returns status, headers, and a short body sample."""
        try:
            response = await self._http.head(url)
            text = ""
            if response.status_code >= 400 or _is_challenge_response(
                response.status_code, "", {k.lower(): v for k, v in response.headers.items()}
            ):
                response = await self._http.get(url, headers={"Range": "bytes=0-2048"})
                text = response.text
            headers = {k.lower(): v for k, v in response.headers.items()}
            return response.status_code, headers, text
        except Exception:
            return 0, {}, ""

    async def _status(self, url: str) -> int:
        """Return the HTTP status code for a URL (0 on failure), preferring HEAD."""
        status, _headers = await self._status_with_headers(url)
        return status

    async def _status_with_headers(self, url: str) -> tuple[int, dict[str, str]]:
        """Return status code and lower-cased headers for a URL (CF bypass on origin).

        When the audited origin is behind a bot challenge we cannot clear, return
        STATUS_BOT_BLOCKED instead of a raw 403/503 so reports do not treat
        Cloudflare blocks as real broken pages.
        """
        status, headers, text = await self._httpx_status_with_headers(url)
        if not self._is_audited_url(url):
            return status, headers

        # Real page errors (404/410/5xx that are not soft-blocks) pass through.
        if (
            status
            and status not in _BOT_SOFT_BLOCK_STATUSES
            and not _is_challenge_response(status, text, headers)
        ):
            return status, headers

        # Soft-block / challenge — escalate via Playwright request API.
        if self._settings.enable_playwright and not self._pw_skip:
            result = await self._playwright_request(url)
            normalized = _origin_probe_status(
                result.status_code,
                result.text,
                result.headers or headers,
                blocked=result.blocked,
            )
            if normalized == STATUS_BOT_BLOCKED:
                return STATUS_BOT_BLOCKED, result.headers or headers
            if normalized and normalized not in _BOT_SOFT_BLOCK_STATUSES:
                return normalized, result.headers or headers

        return (
            _origin_probe_status(status, text, headers, blocked=True),
            headers,
        )

    async def _supplementary_probes(self, ctx: PageContext) -> None:
        """Run asset, TLS, WWW, sitemap and robots cross-checks for site audit params."""
        await asyncio.gather(
            self._probe_assets(ctx),
            self._probe_external_links(ctx),
            self._probe_www(ctx),
            self._probe_http_homepage(ctx),
            self._probe_crawl_titles(ctx),
            self._probe_tls(ctx),
            self._validate_sitemap_urls(ctx),
            self._check_robots_resources(ctx),
            self._detect_orphaned_sitemap_pages(ctx),
            self._probe_resource_page_links(ctx),
            return_exceptions=True,
        )
        if ctx.final_url.startswith("https://") and ctx.sitemap.locs:
            ctx.sitemap.http_loc_count = sum(1 for loc in ctx.sitemap.locs if loc.startswith("http://"))

    async def _probe_assets(self, ctx: PageContext) -> None:
        """HEAD-check images and JS/CSS assets referenced by the audited page."""
        page_host = registrable_host(urlparse(ctx.final_url or ctx.url).netloc)
        asset_urls = list(dict.fromkeys(ctx.script_urls + ctx.stylesheet_urls))[:40]
        image_urls = [
            img.get("absolute", "")
            for img in ctx.images
            if img.get("absolute") and _is_valid_http_url(img.get("absolute", ""))
        ][:40]

        async def check_asset(url: str) -> None:
            status, headers = await self._status_with_headers(url)
            ctx.asset_status[url] = status
            ctx.asset_cache[url] = headers.get("cache-control", "")
            ctx.asset_encoding[url] = headers.get("content-encoding", "")

        async def check_image(url: str) -> None:
            ctx.image_status[url] = await self._status(url)

        await asyncio.gather(*(check_asset(u) for u in asset_urls), return_exceptions=True)
        await asyncio.gather(*(check_image(u) for u in image_urls), return_exceptions=True)

        for url, status in ctx.asset_status.items():
            host = registrable_host(urlparse(url).netloc)
            if host == page_host and is_reportable_http_error(status):
                ctx.crawl_failures.append({"url": url, "reason": f"asset_http_{status}"})

    async def _probe_external_links(self, ctx: PageContext) -> None:
        """Sample external href targets for broken links and 403 responses."""
        sample = list(dict.fromkeys(l.url for l in ctx.outbound_links))[:25]
        statuses = await asyncio.gather(*(self._status(u) for u in sample))
        ctx.external_link_status = dict(zip(sample, statuses))

    async def _probe_http_homepage(self, ctx: PageContext) -> None:
        """Verify the HTTP homepage redirects or canonicals to HTTPS."""
        parsed = urlparse(ctx.final_url or ctx.url)
        host = parsed.hostname or ""
        if not host or parsed.scheme != "https":
            return
        http_url = f"http://{host}/"
        try:
            result = await self._get(http_url, allow_firecrawl=True)
            final = result.final_url or http_url
            if final.startswith("https://"):
                ctx.http_homepage_https_ok = True
                ctx.http_homepage_detail = f"redirects to {final}"
                return
            html = result.text[:8000] if (result.status_code or 0) < 400 else ""
            canonical = ""
            if html and not _is_challenge_body(html):
                soup = BeautifulSoup(html, "lxml")
                tag = soup.find("link", rel=lambda v: v and "canonical" in v.lower())
                if tag and tag.get("href"):
                    canonical = urljoin(final, tag["href"])
            if canonical.startswith("https://"):
                ctx.http_homepage_https_ok = True
                ctx.http_homepage_detail = f"canonical={canonical}"
            else:
                ctx.http_homepage_https_ok = False
                detail = f"final={final}, canonical={canonical or 'missing'}"
                if result.blocked:
                    detail += "; bot_protection"
                ctx.http_homepage_detail = detail
        except Exception as exc:
            ctx.http_homepage_https_ok = False
            ctx.http_homepage_detail = f"fetch failed: {exc}"

    async def _probe_crawl_titles(self, ctx: PageContext) -> None:
        """Backfill titles for crawled URLs missed during BFS."""
        missing = [u for u in ctx.internal_depths if u not in ctx.crawled_titles][:50]

        async def fetch_title(url: str) -> None:
            status, html = await self._fetch_crawl_snippet(url)
            if status == STATUS_BOT_BLOCKED or status == 0 or status >= 400 or not html:
                return
            soup = BeautifulSoup(html, "lxml")
            title_tag = soup.find("title")
            title = (title_tag.string or "").strip() if title_tag and title_tag.string else ""
            if title:
                ctx.crawled_titles[url] = title

        await asyncio.gather(*(fetch_title(u) for u in missing), return_exceptions=True)

    async def _probe_www(self, ctx: PageContext) -> None:
        """Compare www vs non-www homepage resolution."""
        parsed = urlparse(ctx.final_url or ctx.url)
        host = parsed.netloc.lower()
        if not host:
            return
        if host.startswith("www."):
            alt_host = host.removeprefix("www.")
        else:
            alt_host = f"www.{host}"
        alt_url = f"{parsed.scheme}://{alt_host}/"
        try:
            result = await self._get(alt_url, allow_firecrawl=True)
            final_host = urlparse(result.final_url or alt_url).netloc.lower()
            ctx.www_resolve_ok = registrable_host(final_host) == registrable_host(host)
        except Exception:
            ctx.www_resolve_ok = False

    async def _probe_tls(self, ctx: PageContext) -> None:
        """Inspect TLS version, cipher, cert and SNI for discovered site hosts."""
        parsed = urlparse(ctx.final_url or ctx.url)
        if not ctx.tls_ok and parsed.scheme != "https":
            return
        hosts = _discover_site_hosts(ctx)
        if not hosts:
            return
        loop = asyncio.get_running_loop()
        probes = await asyncio.gather(
            *[loop.run_in_executor(None, _tls_inspect_host, host) for host in hosts],
            return_exceptions=True,
        )
        for probe in probes:
            if isinstance(probe, dict):
                ctx.tls_hosts.append(probe)

        primary = (parsed.hostname or "").lower()
        primary_row = next((row for row in ctx.tls_hosts if row.get("host", "").lower() == primary), None)
        if primary_row is None and ctx.tls_hosts:
            primary_row = ctx.tls_hosts[0]
        if primary_row:
            ctx.tls_version = primary_row.get("version", "")
            ctx.tls_cert_hostname_ok = primary_row.get("hostname_ok", True)
            ctx.tls_cert_days_remaining = primary_row.get("days_remaining")

    async def _probe_resource_page_links(self, ctx: PageContext) -> None:
        """Flag non-HTML resources linked via anchor tags instead of media elements."""
        if not ctx.soup:
            return
        base = ctx.final_url or ctx.url
        candidates: list[str] = []
        for anchor in ctx.soup.find_all("a", href=True):
            if anchor.get("download") is not None:
                continue
            href = anchor["href"].strip()
            absolute = urljoin(base, href)
            if not _is_valid_http_url(absolute):
                continue
            path = urlparse(absolute).path.lower()
            if any(path.endswith(ext) for ext in _RESOURCE_LINK_EXTENSIONS):
                candidates.append(absolute)

        for url in list(dict.fromkeys(candidates))[:20]:
            status, headers = await self._status_with_headers(url)
            if status >= 400:
                continue
            content_type = headers.get("content-type", "").split(";")[0].strip().lower()
            if not content_type or content_type in ("text/html", "application/xhtml+xml"):
                continue
            if content_type.startswith(
                ("image/", "video/", "audio/", "application/pdf", "application/zip", "application/octet-stream")
            ) or content_type in (
                "application/msword",
                "application/vnd.ms-excel",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ):
                ctx.resource_page_links.append({"url": url, "content_type": content_type})

    async def _validate_sitemap_urls(self, ctx: PageContext) -> None:
        """HEAD-check a sample of sitemap loc URLs."""
        sample = ctx.sitemap.locs[:30]
        if not sample:
            return
        statuses = await asyncio.gather(*(self._status(u) for u in sample))
        ctx.sitemap.loc_status = dict(zip(sample, statuses))

    def _robots_disallow_prefixes(self, robots_txt: str) -> list[str]:
        """Return Disallow path prefixes from robots.txt (User-agent: * block)."""
        prefixes: list[str] = []
        in_star = False
        for line in robots_txt.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            lower = line.lower()
            if lower.startswith("user-agent:"):
                agent = line.split(":", 1)[1].strip()
                in_star = agent == "*"
            elif in_star and lower.startswith("disallow:"):
                path = line.split(":", 1)[1].strip()
                if path:
                    prefixes.append(path)
        return prefixes

    async def _check_robots_resources(self, ctx: PageContext) -> None:
        """Flag JS/CSS/image URLs that robots.txt Disallow rules would block."""
        if not ctx.robots_txt:
            return
        prefixes = self._robots_disallow_prefixes(ctx.robots_txt)
        if not prefixes:
            return
        page_host = registrable_host(urlparse(ctx.final_url or ctx.url).netloc)
        resources = list(dict.fromkeys(ctx.script_urls + ctx.stylesheet_urls))[:40]
        resources += [
            img.get("absolute", "")
            for img in ctx.images
            if img.get("absolute")
        ][:40]
        for url in resources:
            if not _is_valid_http_url(url):
                continue
            path = urlparse(url).path or "/"
            if not any(path.startswith(prefix) for prefix in prefixes):
                continue
            host = registrable_host(urlparse(url).netloc)
            if host == page_host:
                ctx.robots_blocked_internal.append(url)
            else:
                ctx.robots_blocked_external.append(url)

    async def _detect_orphaned_sitemap_pages(self, ctx: PageContext) -> None:
        """Mark sitemap URLs that lack internal inlinks in the shallow crawl graph."""
        if not ctx.sitemap.locs:
            return
        reachable = set(ctx.internal_depths.keys())
        home_variants = {ctx.url, ctx.final_url, ctx.url.rstrip("/"), (ctx.final_url or "").rstrip("/")}
        for loc in ctx.sitemap.locs[:100]:
            normalised = loc.rstrip("/")
            if loc in reachable or normalised in reachable or loc in home_variants:
                continue
            if registrable_host(urlparse(loc).netloc) != registrable_host(ctx.host):
                continue
            ctx.orphaned_sitemap_pages.append(loc)
