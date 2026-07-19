"""All external service clients, plus shared HTTP helpers and a Clients bundle.

Each client is a thin, single-purpose async wrapper grouped here by the fact
that they are all "ways the auditor talks to the outside world". Clients never
raise on network/credential failure; they return empty/None so a single failing
data source degrades one parameter rather than the whole audit.

Sections:
  1. Shared httpx helpers
  2. LLM clients          (Gemini, OpenAI)
  3. Google clients       (PageSpeed Insights, Knowledge Graph, GA4, GSC)
  4. Web/search clients   (Serper, Perplexity, SerpApi, Wikidata, Firecrawl)
  5. Clients bundle       (constructs and holds all of the above)
"""

from __future__ import annotations  # Forward references for typing

import asyncio  # Run blocking Google SDK calls off the event loop
import json  # Parse the JSON verdict returned by Gemini
from dataclasses import dataclass  # Bundle container

import httpx  # Async HTTP client
from openai import AsyncOpenAI  # Async client for Gemini (OpenAI-compatible) + OpenAI

from app.config import Settings  # All keys/tunables come from settings


# ============================================================================
# 1. Shared httpx helpers
# ============================================================================


def build_async_client(settings: Settings) -> httpx.AsyncClient:
    """Create a configured `httpx.AsyncClient` for a single audit run.

    The caller is responsible for closing the client (use `async with`).
    """
    return httpx.AsyncClient(
        timeout=httpx.Timeout(settings.crawl_timeout_seconds),  # Apply the configured timeout
        follow_redirects=True,  # Let httpx follow redirects so we can inspect the chain
        headers={"User-Agent": settings.crawl_user_agent},  # Identify ourselves politely
        http2=True,  # Enable HTTP/2 negotiation so we can report the protocol version
        limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),  # Bound concurrency
    )


async def get_text(client: httpx.AsyncClient, url: str) -> tuple[int, str]:
    """GET a URL and return (status_code, text); (0, "") on any failure."""
    try:  # Network calls can fail in many ways; never propagate to the caller
        response = await client.get(url)  # Issue the GET request
        return response.status_code, response.text  # Hand back status + body
    except Exception:  # Timeouts, DNS errors, TLS errors, etc.
        return 0, ""  # Signal "could not fetch" without raising


# ============================================================================
# 2. LLM clients
# ============================================================================


# Instruction appended to every Gemini judge() call so it returns parseable JSON.
_JUDGE_SYSTEM = (
    "You are an expert SEO and Generative Engine Optimisation auditor. "
    "Given a webpage signal, respond with STRICT JSON only, no prose, of the form: "
    '{"rating": "Meeting|Partial|Not Meeting", "detail": "<=200 chars evidence", '
    '"recommendation": "<=200 chars concrete fix"}. '
    "Use 'Meeting' only when the signal is clearly satisfied."
)


class GeminiClient:
    """Thin async wrapper around the Gemini chat-completions endpoint (used for all judgement)."""

    def __init__(self, settings: Settings) -> None:
        """Store settings and lazily build the underlying OpenAI-compatible client."""
        self._settings = settings  # Keep settings for key/model/base-url access
        self._enabled = bool(settings.gemini_api_key)  # Disabled when no key is present
        # Build the async client only when a key exists; otherwise judge() short-circuits
        self._client = (
            AsyncOpenAI(api_key=settings.gemini_api_key, base_url=settings.gemini_base_url)
            if self._enabled
            else None
        )

    @property
    def enabled(self) -> bool:
        """Whether Gemini calls can be made (a key was configured)."""
        return self._enabled  # Agents check this before relying on LLM output

    async def complete(self, prompt: str, system: str | None = None) -> str:
        """Return Gemini's free-text completion for a prompt ("" if disabled/failed)."""
        if not self._enabled or self._client is None:  # No key => no completion
            return ""  # Caller treats empty string as "no judgement available"
        try:  # The remote call may fail; never break the audit
            messages = []  # Build the chat message list
            if system:  # Optional system prompt
                messages.append({"role": "system", "content": system})  # Prepend system role
            messages.append({"role": "user", "content": prompt})  # Add the user prompt
            response = await self._client.chat.completions.create(  # Call the model
                model=self._settings.gemini_model,  # Configured Gemini model id
                messages=messages,  # Conversation context
                temperature=0.2,  # Low temperature for consistent judgement
            )
            return (response.choices[0].message.content or "").strip()  # Return trimmed text
        except Exception:  # Any API/network error
            return ""  # Degrade gracefully

    async def judge(self, signal: str) -> dict:
        """Ask Gemini to rate a single signal and return a parsed verdict dict.

        Returns {} when Gemini is unavailable so callers can fall back to
        deterministic heuristics or mark the parameter Not Measured.
        """
        raw = await self.complete(signal, system=_JUDGE_SYSTEM)  # Get the JSON verdict text
        if not raw:  # Empty => unavailable/failed
            return {}  # Signal "no verdict"
        return _safe_parse_json(raw)  # Parse the (possibly fenced) JSON


def _safe_parse_json(text: str) -> dict:
    """Best-effort parse of a JSON object that may be wrapped in markdown fences."""
    cleaned = text.strip()  # Remove surrounding whitespace
    if cleaned.startswith("```"):  # Strip ```json ... ``` fences if present
        cleaned = cleaned.strip("`")  # Remove backticks
        # After stripping backticks a leading language tag may remain (e.g. "json\n{...}")
        newline = cleaned.find("\n")  # Find the first newline
        if newline != -1 and "{" not in cleaned[:newline]:  # Language tag line has no brace
            cleaned = cleaned[newline + 1 :]  # Drop the language tag line
    try:  # The text may still not be valid JSON
        start = cleaned.find("{")  # Locate the first object brace
        end = cleaned.rfind("}")  # Locate the last object brace
        if start == -1 or end == -1:  # No JSON object found
            return {}  # Give up gracefully
        return json.loads(cleaned[start : end + 1])  # Parse the object substring
    except Exception:  # Malformed JSON
        return {}  # Degrade gracefully


class OpenAIClient:
    """Asks an OpenAI model whether it would reference a domain for a query."""

    def __init__(self, settings: Settings) -> None:
        """Store key and lazily build the client."""
        self._enabled = bool(settings.openai_api_key)  # Disabled without a key
        # Build the client only when a key is configured
        self._client = AsyncOpenAI(api_key=settings.openai_api_key) if self._enabled else None

    @property
    def enabled(self) -> bool:
        """Whether OpenAI calls can be made."""
        return self._enabled  # Agents check before relying on results

    async def mentions_domain(self, query: str, domain: str) -> bool | None:
        """Return True/False if an OpenAI answer to `query` references `domain`.

        Returns None when OpenAI is unavailable so the caller can mark the
        parameter Not Measured rather than guessing.
        """
        if not self._enabled or self._client is None:  # No key configured
            return None  # Unknown
        try:  # Remote call may fail
            response = await self._client.chat.completions.create(  # Ask the model
                model="gpt-4o-mini",  # Inexpensive model sufficient for a mention check
                messages=[{"role": "user", "content": query}],  # The query
                temperature=0.0,  # Deterministic output
            )
            answer = (response.choices[0].message.content or "").lower()  # Lower-cased answer
            return domain.lower() in answer  # True when the domain appears in the answer
        except Exception:  # Any error
            return None  # Unknown


# ============================================================================
# 3. Google clients (PageSpeed Insights, Knowledge Graph, GA4, GSC)
# ============================================================================

_PSI_ENDPOINT = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"  # PSI v5 endpoint
_KG_ENDPOINT = "https://kgsearch.googleapis.com/v1/entities:search"  # Knowledge Graph endpoint

from app.google_auth import (  # Shared GSC/GA4 credential loader (OAuth or service account)
    google_credentials_available,
    load_google_credentials,
)


class PsiClient:
    """Fetches Lighthouse + CrUX data for a URL and strategy (mobile/desktop)."""

    def __init__(self, client: httpx.AsyncClient, settings: Settings) -> None:
        """Store the shared HTTP client and API key."""
        self._client = client  # Shared httpx.AsyncClient
        self._key = settings.google_api_key  # PSI uses the GOOGLE_API_KEY
        self._enabled = bool(self._key)  # Disabled without a key

    @property
    def enabled(self) -> bool:
        """Whether PSI calls can be made."""
        return self._enabled  # Agents check this before relying on PSI data

    async def analyze(self, url: str, strategy: str) -> dict:
        """Run PSI for `url` with `strategy` ("mobile"|"desktop"); {} on failure."""
        if not self._enabled:  # No API key configured
            return {}  # Caller marks PSI parameters Not Measured
        params = {  # Query parameters for the PSI request
            "url": url,  # The page to analyse
            "key": self._key,  # API key
            "strategy": strategy,  # Device emulation strategy
        }
        # Request each Lighthouse category so we can report all four scores
        categories = ["performance", "accessibility", "best-practices", "seo"]
        # httpx encodes repeated keys when given a list of tuples
        query = list(params.items()) + [("category", c) for c in categories]
        try:  # PSI can time out for slow pages
            response = await self._client.get(_PSI_ENDPOINT, params=query)  # Issue request
            if response.status_code != 200:  # Non-200 => treat as unavailable
                return {}  # Degrade gracefully
            return response.json()  # Return the parsed PSI payload
        except Exception:  # Network/JSON errors
            return {}  # Degrade gracefully


class KnowledgeGraphClient:
    """Searches the Google Knowledge Graph for a brand/entity."""

    def __init__(self, client: httpx.AsyncClient, settings: Settings) -> None:
        """Store the HTTP client and API key."""
        self._client = client  # Shared httpx.AsyncClient
        self._key = settings.google_api_key  # KG uses the GOOGLE_API_KEY
        self._enabled = bool(self._key)  # Disabled without a key

    @property
    def enabled(self) -> bool:
        """Whether Knowledge Graph calls can be made."""
        return self._enabled  # Agents check before relying on results

    async def lookup(self, name: str) -> dict:
        """Return the top KG entity for `name` ({} when none/disabled)."""
        if not self._enabled or not name:  # No key or empty name
            return {}  # Nothing to return
        params = {  # KG search parameters
            "query": name,  # The entity name
            "key": self._key,  # API key
            "limit": 1,  # Only the best match
            "indent": "true",  # Pretty JSON (harmless)
        }
        try:  # Network call may fail
            response = await self._client.get(_KG_ENDPOINT, params=params)  # Issue request
            if response.status_code != 200:  # Non-200 => unavailable
                return {}  # Degrade gracefully
            items = response.json().get("itemListElement", [])  # Result wrapper list
            return items[0].get("result", {}) if items else {}  # Top entity result or {}
        except Exception:  # Any error
            return {}  # Degrade gracefully


@dataclass
class GscApiResult:
    """Outcome of a Search Console API call."""

    ok: bool  # True when the API call completed without error
    data: dict | list | None = None  # Payload (row dict, sitemap list, inspection dict, …)
    error: str = ""  # Error message when ok is False

    @property
    def has_data(self) -> bool:
        """True when the call succeeded and returned a non-empty payload."""
        if not self.ok or self.data is None:
            return False
        if isinstance(self.data, (dict, list)):
            return len(self.data) > 0
        return bool(self.data)


_GSC_MAX_ATTEMPTS = 3
_GSC_RETRY_BACKOFF_SEC = (0.5, 1.0, 2.0)


class GscClient:
    """Read-only Search Console access for connected properties (blocking SDK off-thread)."""

    def __init__(self, settings: Settings) -> None:
        """Record whether Google credentials are available; build the service lazily."""
        self._settings = settings  # Application settings
        self._enabled = google_credentials_available(settings)  # OAuth token or service account
        self._service = None  # The Google API service is built on first use
        self._lock = asyncio.Lock()  # Google API client is not safe for concurrent execute()

    @property
    def enabled(self) -> bool:
        """Whether GSC calls can be made (credentials present)."""
        return self._enabled  # Agents check before relying on GSC data

    def _build_service(self):
        """Construct the GSC service object (blocking; called inside a thread)."""
        from googleapiclient.discovery import build  # Builds the API client

        creds = load_google_credentials(self._settings)  # OAuth or service account
        if creds is None:  # Should not happen when enabled=True
            raise RuntimeError("Google credentials not configured")
        return build("searchconsole", "v1", credentials=creds, cache_discovery=False)  # API client

    def _service_or_build(self):
        """Return the cached service, building it on first access."""
        if self._service is None:  # Not yet built
            self._service = self._build_service()  # Build and cache
        return self._service  # Reuse across calls

    def _reset_service(self) -> None:
        """Drop the cached API client so the next call builds a fresh connection."""
        self._service = None

    async def _run_with_retry(self, fn) -> GscApiResult:
        """Run a blocking GSC call with retries on transient SSL/connection failures."""
        async with self._lock:
            last_error = ""
            for attempt in range(_GSC_MAX_ATTEMPTS):
                try:
                    return await asyncio.to_thread(fn)
                except Exception as exc:
                    last_error = str(exc)
                    self._reset_service()
                    if attempt + 1 < _GSC_MAX_ATTEMPTS:
                        await asyncio.sleep(_GSC_RETRY_BACKOFF_SEC[attempt])
            return GscApiResult(ok=False, error=last_error)

    async def query_search_analytics(self, site_url: str, page_url: str) -> GscApiResult:
        """Return CTR/position metrics for `page_url`, trying common URL variants."""
        if not self._enabled:
            return GscApiResult(ok=False, error="Google credentials not configured")
        return await self._run_with_retry(lambda: self._query_sync(site_url, page_url))

    @staticmethod
    def _page_url_variants(page_url: str) -> list[str]:
        """Build URL forms GSC may use when storing page dimensions."""
        from urllib.parse import urlparse, urlunparse

        parsed = urlparse(page_url)
        if not parsed.scheme or not parsed.netloc:
            return [page_url]
        path = parsed.path or "/"
        base = urlunparse((parsed.scheme, parsed.netloc, path, "", parsed.query, ""))
        variants: list[str] = []
        for candidate in (page_url, base):
            if candidate and candidate not in variants:
                variants.append(candidate)
            alt = candidate.rstrip("/") if candidate.endswith("/") else candidate + "/"
            if alt not in variants:
                variants.append(alt)
        host = parsed.netloc.lower()
        alt_host = host[4:] if host.startswith("www.") else f"www.{host}"
        for v in list(variants):
            p = urlparse(v)
            swapped = urlunparse((p.scheme, alt_host, p.path or "/", "", p.query, ""))
            if swapped not in variants:
                variants.append(swapped)
            alt = swapped.rstrip("/") if swapped.endswith("/") else swapped + "/"
            if alt not in variants:
                variants.append(alt)
        return variants

    def _query_sync(self, site_url: str, page_url: str) -> GscApiResult:
        """Blocking searchanalytics.query for a single page (final data)."""
        service = self._service_or_build()
        for variant in self._page_url_variants(page_url):
            body = {
                "startDate": "2020-01-01",
                "endDate": "2030-01-01",
                "dimensions": ["page"],
                "dimensionFilterGroups": [
                    {"filters": [{"dimension": "page", "expression": variant}]}
                ],
                "dataState": "final",
                "rowLimit": 1,
            }
            resp = service.searchanalytics().query(siteUrl=site_url, body=body).execute()
            rows = resp.get("rows", [])
            if rows:
                row = rows[0]
                row["_matchedPageUrl"] = variant
                return GscApiResult(ok=True, data=row)
        return GscApiResult(ok=True, data={})

    async def sitemaps(self, site_url: str) -> GscApiResult:
        """Return submitted sitemaps for the property."""
        if not self._enabled:
            return GscApiResult(ok=False, error="Google credentials not configured")
        return await self._run_with_retry(lambda: self._sitemaps_sync(site_url))

    def _sitemaps_sync(self, site_url: str) -> GscApiResult:
        """Blocking sitemaps.list for the property."""
        service = self._service_or_build()
        resp = service.sitemaps().list(siteUrl=site_url).execute()
        return GscApiResult(ok=True, data=resp.get("sitemap", []))

    async def inspect_url(self, site_url: str, inspection_url: str) -> GscApiResult:
        """Return URL Inspection index status for one page."""
        if not self._enabled:
            return GscApiResult(ok=False, error="Google credentials not configured")
        return await self._run_with_retry(
            lambda: self._inspect_sync(site_url, inspection_url)
        )

    def _inspect_sync(self, site_url: str, inspection_url: str) -> GscApiResult:
        """Blocking urlInspection.index.inspect for one URL."""
        service = self._service_or_build()
        for variant in self._page_url_variants(inspection_url):
            resp = (
                service.urlInspection()
                .index()
                .inspect(body={"inspectionUrl": variant, "siteUrl": site_url})
                .execute()
            )
            result = resp.get("inspectionResult") or {}
            if result:
                result["_matchedInspectionUrl"] = variant
                return GscApiResult(ok=True, data=result)
        return GscApiResult(ok=True, data={})

    async def search_analytics_report(
        self,
        site_url: str,
        *,
        dimensions: list[str],
        row_limit: int = 25,
        days: int = 90,
    ) -> GscApiResult:
        """Return Search Analytics rows grouped by the given dimensions."""
        if not self._enabled:
            return GscApiResult(ok=False, error="Google credentials not configured")
        return await self._run_with_retry(
            lambda: self._search_analytics_report_sync(site_url, dimensions, row_limit, days)
        )

    def _search_analytics_report_sync(
        self,
        site_url: str,
        dimensions: list[str],
        row_limit: int,
        days: int,
    ) -> GscApiResult:
        from datetime import date, timedelta

        service = self._service_or_build()
        end = date.today() - timedelta(days=1)
        start = end - timedelta(days=max(1, days) - 1)
        body = {
            "startDate": start.isoformat(),
            "endDate": end.isoformat(),
            "dimensions": dimensions,
            "rowLimit": row_limit,
            "dataState": "final",
        }
        resp = service.searchanalytics().query(siteUrl=site_url, body=body).execute()
        rows = resp.get("rows", [])
        parsed = []
        for row in rows:
            keys = row.get("keys", [])
            parsed.append(
                {
                    "keys": keys,
                    "clicks": row.get("clicks", 0),
                    "impressions": row.get("impressions", 0),
                    "ctr": row.get("ctr", 0.0),
                    "position": row.get("position", 0.0),
                }
            )
        return GscApiResult(ok=True, data=parsed)


class Ga4Client:
    """Read-only GA4 engagement metrics for a connected property (blocking SDK off-thread)."""

    def __init__(self, settings: Settings) -> None:
        """Record whether Google credentials are available."""
        self._settings = settings  # Application settings
        self._enabled = google_credentials_available(settings)  # OAuth token or service account

    @property
    def enabled(self) -> bool:
        """Whether GA4 calls can be made (credentials present)."""
        return self._enabled  # Agents check before relying on GA4 data

    async def engagement(self, property_id: str, page_path: str) -> dict:
        """Return engagement metrics for `page_path` ({} on failure)."""
        if not self._enabled or not property_id:  # No credentials or property id
            return {}  # Degrade gracefully
        try:  # SDK call may fail (no access, quota, etc.)
            return await asyncio.to_thread(self._engagement_sync, property_id, page_path)  # Off-thread
        except Exception:  # Any error
            return {}  # Degrade gracefully

    @staticmethod
    def _page_path_variants(page_path: str) -> list[str]:
        """Path forms GA4 may use (/ vs trailing slash)."""
        path = page_path or "/"
        variants: list[str] = []
        for candidate in (path, path.rstrip("/") or "/", path.rstrip("/") + "/"):
            if candidate and candidate not in variants:
                variants.append(candidate)
        return variants

    def _engagement_sync(self, property_id: str, page_path: str) -> dict:
        """Blocking runReport for engagement metrics on a single page path."""
        from google.analytics.data_v1beta import BetaAnalyticsDataClient  # GA4 client
        from google.analytics.data_v1beta.types import (  # Request building blocks
            DateRange,
            Dimension,
            Filter,
            FilterExpression,
            Metric,
            RunReportRequest,
        )
        creds = load_google_credentials(self._settings)  # OAuth or service account
        if creds is None:  # Should not happen when enabled=True
            raise RuntimeError("Google credentials not configured")
        client = BetaAnalyticsDataClient(credentials=creds)  # Authenticated GA4 client
        def _page_path_filter(path: str) -> FilterExpression:
            return FilterExpression(
                filter=Filter(
                    field_name="pagePath",
                    string_filter=Filter.StringFilter(value=path),
                )
            )

        def _row_metrics(request: RunReportRequest) -> dict:
            try:
                response = client.run_report(request)
            except Exception:
                return {}
            if not response.rows:
                return {}
            names = [m.name for m in response.metric_headers]
            values = [v.value for v in response.rows[0].metric_values]
            return dict(zip(names, values))

        for path in self._page_path_variants(page_path):
            base = _row_metrics(
                RunReportRequest(
                    property=f"properties/{property_id}",
                    date_ranges=[DateRange(start_date="28daysAgo", end_date="yesterday")],
                    dimensions=[Dimension(name="pagePath")],
                    metrics=[
                        Metric(name="averageSessionDuration"),
                        Metric(name="bounceRate"),
                    ],
                    dimension_filter=_page_path_filter(path),
                    limit=1,
                )
            )
            engagement = _row_metrics(
                RunReportRequest(
                    property=f"properties/{property_id}",
                    date_ranges=[DateRange(start_date="28daysAgo", end_date="yesterday")],
                    dimensions=[Dimension(name="pagePath")],
                    metrics=[Metric(name="engagementRate")],
                    dimension_filter=_page_path_filter(path),
                    limit=1,
                )
            )
            merged = {**base, **engagement}
            if merged:
                return merged
        return {}

    async def fetch_baseline(self, property_id: str, page_path: str, *, days: int = 90) -> dict:
        """Return all GA4 datasets needed for the Performance Baseline PDF."""
        if not self._enabled or not property_id:
            return {}
        try:
            return await asyncio.to_thread(self._fetch_baseline_sync, property_id, page_path, days)
        except Exception:
            return {}

    def _fetch_baseline_sync(self, property_id: str, page_path: str, days: int) -> dict:
        """Blocking GA4 runReport bundle for baseline charts."""
        from google.analytics.data_v1beta import BetaAnalyticsDataClient
        from google.analytics.data_v1beta.types import (
            DateRange,
            Dimension,
            Filter,
            FilterExpression,
            FilterExpressionList,
            Metric,
            OrderBy,
            RunReportRequest,
        )

        creds = load_google_credentials(self._settings)
        if creds is None:
            return {}
        client = BetaAnalyticsDataClient(credentials=creds)
        date_range = [DateRange(start_date=f"{days}daysAgo", end_date="yesterday")]
        prop = f"properties/{property_id}"
        out: dict = {}

        def _run(request: RunReportRequest) -> list[dict]:
            try:
                response = client.run_report(request)
            except Exception:
                return []
            rows = []
            dims = [d.name for d in response.dimension_headers]
            metrics = [m.name for m in response.metric_headers]
            for row in response.rows:
                item = {}
                for idx, dim in enumerate(dims):
                    item[dim] = row.dimension_values[idx].value
                for idx, metric in enumerate(metrics):
                    item[metric] = row.metric_values[idx].value
                rows.append(item)
            return rows

        # engagementRate is incompatible with bounceRate in one GA4 request — fetch separately.
        overview_rows = _run(
            RunReportRequest(
                property=prop,
                date_ranges=date_range,
                metrics=[
                    Metric(name="totalUsers"),
                    Metric(name="newUsers"),
                    Metric(name="bounceRate"),
                    Metric(name="averageSessionDuration"),
                    Metric(name="screenPageViewsPerSession"),
                ],
            )
        )
        engagement_overview_rows = _run(
            RunReportRequest(
                property=prop,
                date_ranges=date_range,
                metrics=[Metric(name="engagementRate")],
            )
        )
        if overview_rows:
            out["overview"] = overview_rows[0]
            if engagement_overview_rows:
                out["overview"]["engagementRate"] = engagement_overview_rows[0].get("engagementRate")
        elif engagement_overview_rows:
            out["overview"] = engagement_overview_rows[0]

        for path in self._page_path_variants(page_path):
            page_rows = _run(
                RunReportRequest(
                    property=prop,
                    date_ranges=date_range,
                    dimensions=[Dimension(name="pagePath")],
                    metrics=[
                        Metric(name="averageSessionDuration"),
                        Metric(name="bounceRate"),
                    ],
                    dimension_filter=FilterExpression(
                        filter=Filter(
                            field_name="pagePath",
                            string_filter=Filter.StringFilter(value=path),
                        )
                    ),
                    limit=1,
                )
            )
            engagement_page_rows = _run(
                RunReportRequest(
                    property=prop,
                    date_ranges=date_range,
                    dimensions=[Dimension(name="pagePath")],
                    metrics=[Metric(name="engagementRate")],
                    dimension_filter=FilterExpression(
                        filter=Filter(
                            field_name="pagePath",
                            string_filter=Filter.StringFilter(value=path),
                        )
                    ),
                    limit=1,
                )
            )
            if page_rows or engagement_page_rows:
                out["page_engagement"] = {
                    **(page_rows[0] if page_rows else {}),
                    **(engagement_page_rows[0] if engagement_page_rows else {}),
                }
                break

        out["channels"] = _run(
            RunReportRequest(
                property=prop,
                date_ranges=date_range,
                dimensions=[Dimension(name="sessionDefaultChannelGroup")],
                metrics=[
                    Metric(name="totalUsers"),
                    Metric(name="sessions"),
                    Metric(name="screenPageViews"),
                    Metric(name="averageSessionDuration"),
                    Metric(name="engagementRate"),
                ],
                limit=15,
            )
        )
        out["sources"] = _run(
            RunReportRequest(
                property=prop,
                date_ranges=date_range,
                dimensions=[Dimension(name="sessionSource")],
                metrics=[
                    Metric(name="totalUsers"),
                    Metric(name="sessions"),
                    Metric(name="screenPageViews"),
                    Metric(name="averageSessionDuration"),
                    Metric(name="engagementRate"),
                ],
                limit=25,
            )
        )
        out["devices"] = _run(
            RunReportRequest(
                property=prop,
                date_ranges=date_range,
                dimensions=[Dimension(name="deviceCategory")],
                metrics=[
                    Metric(name="totalUsers"),
                    Metric(name="averageSessionDuration"),
                    Metric(name="engagementRate"),
                    Metric(name="screenPageViewsPerSession"),
                ],
                limit=5,
            )
        )
        out["bounce_trend"] = _run(
            RunReportRequest(
                property=prop,
                date_ranges=date_range,
                dimensions=[Dimension(name="date")],
                metrics=[Metric(name="bounceRate")],
                limit=500,
            )
        )
        out["engagement_trend"] = _run(
            RunReportRequest(
                property=prop,
                date_ranges=date_range,
                dimensions=[Dimension(name="date")],
                metrics=[Metric(name="averageSessionDuration")],
                limit=500,
            )
        )
        out["forms"] = _run(
            RunReportRequest(
                property=prop,
                date_ranges=date_range,
                dimensions=[Dimension(name="eventName")],
                metrics=[Metric(name="eventCount")],
                dimension_filter=FilterExpression(
                    or_group=FilterExpressionList(
                        expressions=[
                            FilterExpression(
                                filter=Filter(
                                    field_name="eventName",
                                    in_list_filter=Filter.InListFilter(
                                        values=["form_start", "form_submit"],
                                    ),
                                )
                            ),
                            FilterExpression(
                                filter=Filter(
                                    field_name="eventName",
                                    string_filter=Filter.StringFilter(
                                        match_type=Filter.StringFilter.MatchType.PARTIAL_REGEXP,
                                        value="form|submit|generate_lead|contact",
                                    ),
                                )
                            ),
                        ]
                    )
                ),
                order_bys=[
                    OrderBy(
                        metric=OrderBy.MetricOrderBy(metric_name="eventCount"),
                        desc=True,
                    ),
                ],
                limit=15,
            )
        )
        out["top_pages"] = _run(
            RunReportRequest(
                property=prop,
                date_ranges=date_range,
                dimensions=[Dimension(name="pagePath")],
                metrics=[
                    Metric(name="sessions"),
                    Metric(name="bounceRate"),
                    Metric(name="screenPageViews"),
                ],
                limit=20,
            )
        )
        social_rows = [
            row
            for row in out.get("channels", [])
            if str(row.get("sessionDefaultChannelGroup", "")).lower() == "organic social"
        ]
        out["organic_social"] = social_rows
        return out

    async def fetch_page_inventory(
        self,
        property_id: str,
        *,
        days: int = 90,
        limit: int = 500,
    ) -> list[dict]:
        """Return GA4 pagePath rows with sessions for orphan detection."""
        if not self._enabled or not property_id:
            return []
        try:
            return await asyncio.to_thread(self._fetch_page_inventory_sync, property_id, days, limit)
        except Exception:
            return []

    def _fetch_page_inventory_sync(self, property_id: str, days: int, limit: int) -> list[dict]:
        from google.analytics.data_v1beta import BetaAnalyticsDataClient
        from google.analytics.data_v1beta.types import (
            DateRange,
            Dimension,
            Metric,
            OrderBy,
            RunReportRequest,
        )

        creds = load_google_credentials(self._settings)
        if creds is None:
            return []
        client = BetaAnalyticsDataClient(credentials=creds)
        request = RunReportRequest(
            property=f"properties/{property_id}",
            date_ranges=[DateRange(start_date=f"{days}daysAgo", end_date="yesterday")],
            dimensions=[Dimension(name="pagePath")],
            metrics=[Metric(name="sessions"), Metric(name="screenPageViews")],
            order_bys=[
                OrderBy(metric=OrderBy.MetricOrderBy(metric_name="sessions"), desc=True),
            ],
            limit=limit,
        )
        try:
            response = client.run_report(request)
        except Exception:
            return []
        rows = []
        for row in response.rows:
            path = row.dimension_values[0].value if row.dimension_values else ""
            sessions = row.metric_values[0].value if row.metric_values else "0"
            views = row.metric_values[1].value if len(row.metric_values) > 1 else "0"
            rows.append({"pagePath": path, "sessions": sessions, "screenPageViews": views})
        return rows


# ============================================================================
# 4. Web/search clients (Serper, Perplexity, SerpApi, Wikidata, Firecrawl)
# ============================================================================

_SERPER_ENDPOINT = "https://google.serper.dev/search"  # Serper search endpoint
_PPLX_ENDPOINT = "https://api.perplexity.ai/chat/completions"  # Perplexity (OpenAI-compatible)
_SERPAPI_ENDPOINT = "https://serpapi.com/search"  # SerpApi search endpoint
_WIKIDATA_SEARCH = "https://www.wikidata.org/w/api.php"  # Wikidata entity search
_WIKIPEDIA_SUMMARY = "https://en.wikipedia.org/api/rest_v1/page/summary/"  # Wikipedia summary
_FIRECRAWL_SCRAPE = "https://api.firecrawl.dev/v1/scrape"  # Firecrawl scrape endpoint


class SerperClient:
    """Runs Google web searches and returns organic results (press mentions, awards)."""

    def __init__(self, client: httpx.AsyncClient, settings: Settings) -> None:
        """Store the HTTP client and API key."""
        self._client = client  # Shared httpx.AsyncClient
        self._key = settings.serper_api_key  # Serper API key
        self._enabled = bool(self._key)  # Disabled without a key

    @property
    def enabled(self) -> bool:
        """Whether Serper calls can be made."""
        return self._enabled  # Agents check before relying on results

    async def search(self, query: str, num: int = 10) -> list[dict]:
        """Return organic results for `query` ([] on failure)."""
        if not self._enabled:  # No key configured
            return []  # Degrade gracefully
        try:  # Network call may fail
            response = await self._client.post(  # Serper expects a POST with JSON body
                _SERPER_ENDPOINT,
                headers={"X-API-KEY": self._key, "Content-Type": "application/json"},  # Auth header
                json={"q": query, "num": num},  # Query payload
            )
            if response.status_code != 200:  # Non-200 => unavailable
                return []  # Degrade gracefully
            return response.json().get("organic", [])  # Extract organic results list
        except Exception:  # Any error
            return []  # Degrade gracefully


class PerplexityClient:
    """Asks Perplexity a query and returns the cited source URLs."""

    def __init__(self, client: httpx.AsyncClient, settings: Settings) -> None:
        """Store the HTTP client and API key."""
        self._client = client  # Shared httpx.AsyncClient
        self._key = settings.perplexity_api_key  # Perplexity API key
        self._enabled = bool(self._key)  # Disabled without a key

    @property
    def enabled(self) -> bool:
        """Whether Perplexity calls can be made."""
        return self._enabled  # Agents check before relying on results

    async def citations(self, query: str) -> list[str]:
        """Return the list of source URLs Perplexity cites for `query` ([] on failure)."""
        if not self._enabled:  # No key configured
            return []  # Degrade gracefully
        try:  # Network call may fail
            response = await self._client.post(  # Chat completions request
                _PPLX_ENDPOINT,
                headers={"Authorization": f"Bearer {self._key}"},  # Bearer auth
                json={  # Minimal Sonar request
                    "model": "sonar",  # Online model that returns citations
                    "messages": [{"role": "user", "content": query}],  # The query
                },
            )
            if response.status_code != 200:  # Non-200 => unavailable
                return []  # Degrade gracefully
            data = response.json()  # Parse the payload
            return data.get("citations", []) or []  # Top-level citations array of URLs
        except Exception:  # Any error
            return []  # Degrade gracefully


class SerpApiClient:
    """Runs a Google search via SerpApi and extracts AI Overview source links."""

    def __init__(self, client: httpx.AsyncClient, settings: Settings) -> None:
        """Store the HTTP client and API key."""
        self._client = client  # Shared httpx.AsyncClient
        self._key = settings.serpapi_api_key  # SerpApi API key
        self._enabled = bool(self._key)  # Disabled without a key

    @property
    def enabled(self) -> bool:
        """Whether SerpApi calls can be made."""
        return self._enabled  # Agents check before relying on results

    async def ai_overview_sources(self, query: str) -> list[str]:
        """Return source URLs cited in Google's AI Overview for `query` ([] on failure)."""
        if not self._enabled:  # No key configured
            return []  # Degrade gracefully
        params = {  # SerpApi query parameters
            "engine": "google",  # Google search engine
            "q": query,  # The query
            "api_key": self._key,  # API key
        }
        try:  # Network call may fail
            response = await self._client.get(_SERPAPI_ENDPOINT, params=params)  # Issue request
            if response.status_code != 200:  # Non-200 => unavailable
                return []  # Degrade gracefully
            data = response.json()  # Parse payload
            overview = data.get("ai_overview", {})  # AI Overview block (if present)
            sources = overview.get("references", []) or overview.get("sources", [])  # Source list
            return [s.get("link", "") for s in sources if s.get("link")]  # Extract links
        except Exception:  # Any error
            return []  # Degrade gracefully


class WikidataClient:
    """Looks up an organisation/person entity in Wikidata and Wikipedia (no API key)."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        """Store the shared HTTP client (no key required)."""
        self._client = client  # Shared httpx.AsyncClient

    @property
    def enabled(self) -> bool:
        """Always enabled; these endpoints need no key."""
        return True  # No authentication required

    async def entity_exists(self, name: str) -> bool:
        """Return True if a Wikidata entity matches `name`."""
        if not name:  # Guard against empty brand names
            return False  # Nothing to look up
        params = {  # Wikidata search parameters
            "action": "wbsearchentities",  # Entity search action
            "search": name,  # The brand/entity name
            "language": "en",  # Search English labels
            "format": "json",  # JSON response
            "limit": 1,  # We only need to know if at least one match exists
        }
        try:  # Network call may fail
            response = await self._client.get(_WIKIDATA_SEARCH, params=params)  # Issue request
            if response.status_code != 200:  # Non-200 => unavailable
                return False  # Treat as "no entity"
            return bool(response.json().get("search"))  # True when results were returned
        except Exception:  # Any error
            return False  # Treat as "no entity"

    async def wikipedia_exists(self, name: str) -> bool:
        """Return True if an English Wikipedia article exists for `name`."""
        if not name:  # Guard against empty names
            return False  # Nothing to look up
        try:  # Network call may fail
            response = await self._client.get(_WIKIPEDIA_SUMMARY + name.replace(" ", "_"))  # Title slug
            return response.status_code == 200  # 200 => an article exists
        except Exception:  # Any error
            return False  # Treat as "no article"


class FirecrawlClient:
    """Renders a JS-heavy page via Firecrawl and returns its HTML (render fallback)."""

    def __init__(self, client: httpx.AsyncClient, settings: Settings) -> None:
        """Store the HTTP client and API key."""
        self._client = client  # Shared httpx.AsyncClient
        self._key = settings.firecrawl_api_key  # Firecrawl API key
        self._enabled = bool(self._key)  # Disabled without a key

    @property
    def enabled(self) -> bool:
        """Whether Firecrawl calls can be made."""
        return self._enabled  # Fetcher checks before using as a fallback

    async def rendered_html(self, url: str) -> str:
        """Return rendered HTML for `url` ("" on failure)."""
        return await self.fetch_body(url)

    async def fetch_body(self, url: str) -> str:
        """Return page/body text for `url`, preferring rawHtml over html ("" on failure)."""
        if not self._enabled:  # No key configured
            return ""  # No fallback available
        try:  # Network call may fail
            response = await self._client.post(  # Firecrawl scrape request
                _FIRECRAWL_SCRAPE,
                headers={"Authorization": f"Bearer {self._key}"},  # Bearer auth
                json={"url": url, "formats": ["rawHtml", "html"]},  # Prefer unmodified body
                timeout=45.0,  # Rendering can be slow; allow extra time
            )
            if response.status_code != 200:  # Non-200 => unavailable
                return ""  # Degrade gracefully
            data = response.json().get("data", {})  # Scrape payload
            return data.get("rawHtml") or data.get("html") or ""  # Prefer raw body
        except Exception:  # Any error
            return ""  # Degrade gracefully


# ============================================================================
# 5. Clients bundle
# ============================================================================


@dataclass
class Clients:
    """All external clients plus settings and the shared HTTP client.

    Bundling keeps agent constructors uniform and means the orchestrator wires
    every dependency in exactly one place (`Clients.create`).
    """

    settings: Settings  # Application configuration
    http: httpx.AsyncClient  # Shared async HTTP client
    gemini: GeminiClient  # Gemini AI judgement
    psi: PsiClient  # PageSpeed Insights
    serper: SerperClient  # Serper web search
    perplexity: PerplexityClient  # Perplexity citations
    serpapi: SerpApiClient  # SerpApi AI Overview citations
    openai: OpenAIClient  # OpenAI citation checks
    wikidata: WikidataClient  # Wikidata/Wikipedia entity lookups
    knowledge_graph: KnowledgeGraphClient  # Google Knowledge Graph
    firecrawl: FirecrawlClient  # Render fallback
    gsc: GscClient  # Search Console (connected)
    ga4: Ga4Client  # GA4 (connected)

    @classmethod
    def create(cls, settings: Settings, http: httpx.AsyncClient) -> "Clients":
        """Construct every client from settings + a shared HTTP client."""
        return cls(  # Wire all dependencies in one place
            settings=settings,  # Pass settings through
            http=http,  # Reuse one HTTP client across REST-based clients
            gemini=GeminiClient(settings),  # Gemini uses its own OpenAI-compatible client
            psi=PsiClient(http, settings),  # PSI reuses the shared client
            serper=SerperClient(http, settings),  # Serper reuses the shared client
            perplexity=PerplexityClient(http, settings),  # Perplexity reuses the shared client
            serpapi=SerpApiClient(http, settings),  # SerpApi reuses the shared client
            openai=OpenAIClient(settings),  # OpenAI uses its own SDK client
            wikidata=WikidataClient(http),  # Wikidata reuses the shared client
            knowledge_graph=KnowledgeGraphClient(http, settings),  # KG reuses the shared client
            firecrawl=FirecrawlClient(http, settings),  # Firecrawl reuses the shared client
            gsc=GscClient(settings),  # GSC builds its own Google service
            ga4=Ga4Client(settings),  # GA4 builds its own Google client
        )
