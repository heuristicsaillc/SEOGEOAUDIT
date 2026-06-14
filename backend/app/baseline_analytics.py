"""Fetch GA4 + GSC datasets for the Performance Baseline PDF."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from urllib.parse import urlparse

from app.clients import Ga4Client, GscApiResult, GscClient


@dataclass
class BaselineAnalytics:
    """Live analytics bundle used when building the baseline PDF."""

    overview: dict = field(default_factory=dict)
    page_engagement: dict = field(default_factory=dict)
    gsc_device: list[dict] = field(default_factory=list)
    gsc_country: list[dict] = field(default_factory=list)
    gsc_top_pages: list[dict] = field(default_factory=list)
    gsc_keywords: list[dict] = field(default_factory=list)
    ga4_channels: list[dict] = field(default_factory=list)
    ga4_sources: list[dict] = field(default_factory=list)
    ga4_social: list[dict] = field(default_factory=list)
    ga4_devices: list[dict] = field(default_factory=list)
    ga4_bounce_trend: list[dict] = field(default_factory=list)
    ga4_engagement_trend: list[dict] = field(default_factory=list)
    ga4_forms: list[dict] = field(default_factory=list)
    ga4_top_pages: list[dict] = field(default_factory=list)
    gsc_keywords_ok: bool = True
    gsc_keywords_error: str = ""

    def has_ga4_overview(self) -> bool:
        return bool(self.overview.get("totalUsers"))

    def has_gsc_clicks(self) -> bool:
        return bool(self.gsc_device or self.gsc_country)


def _parse_gsc_rows(result: GscApiResult) -> list[dict]:
    if not result.ok or not result.data:
        return []
    rows = []
    for row in result.data:
        keys = row.get("keys") or []
        label = keys[0] if keys else ""
        rows.append(
            {
                "label": label,
                "clicks": int(row.get("clicks", 0)),
                "impressions": int(row.get("impressions", 0)),
                "ctr": float(row.get("ctr", 0.0)),
                "position": float(row.get("position", 0.0)),
            }
        )
    return rows


def _with_share(rows: list[dict], key: str = "clicks") -> list[dict]:
    total = sum(r.get(key, 0) for r in rows) or 1
    for row in rows:
        row["share"] = row.get(key, 0) / total
    return rows


async def fetch_baseline_analytics(
    ga4: Ga4Client,
    gsc: GscClient,
    connection: dict,
    final_url: str,
) -> BaselineAnalytics:
    """Pull GA4/GSC reports in parallel for the baseline PDF."""
    prop = connection.get("ga4_property_id", "")
    site = connection.get("gsc_site_url", "")
    path = urlparse(final_url).path or "/"

    ga4_task = ga4.fetch_baseline(prop, path)
    gsc_device_task = gsc.search_analytics_report(site, dimensions=["device"], row_limit=10)
    gsc_country_task = gsc.search_analytics_report(site, dimensions=["country"], row_limit=15)
    gsc_pages_task = gsc.search_analytics_report(site, dimensions=["page"], row_limit=25)
    gsc_queries_task = gsc.search_analytics_report(site, dimensions=["query"], row_limit=25)

    ga4_raw, gsc_device, gsc_country, gsc_pages, gsc_queries = await asyncio.gather(
        ga4_task,
        gsc_device_task,
        gsc_country_task,
        gsc_pages_task,
        gsc_queries_task,
    )

    bundle = BaselineAnalytics()
    if ga4_raw:
        bundle.overview = ga4_raw.get("overview", {})
        bundle.page_engagement = ga4_raw.get("page_engagement", {})
        bundle.ga4_channels = ga4_raw.get("channels", [])
        bundle.ga4_sources = ga4_raw.get("sources", [])
        bundle.ga4_social = ga4_raw.get("organic_social", [])
        bundle.ga4_devices = ga4_raw.get("devices", [])
        bundle.ga4_bounce_trend = ga4_raw.get("bounce_trend", [])
        bundle.ga4_engagement_trend = ga4_raw.get("engagement_trend", [])
        bundle.ga4_forms = ga4_raw.get("forms", [])
        bundle.ga4_top_pages = ga4_raw.get("top_pages", [])

    bundle.gsc_device = _with_share(_parse_gsc_rows(gsc_device))
    bundle.gsc_country = _with_share(_parse_gsc_rows(gsc_country))
    bundle.gsc_top_pages = _with_share(_parse_gsc_rows(gsc_pages))
    bundle.gsc_keywords = _parse_gsc_rows(gsc_queries)
    bundle.gsc_keywords_ok = gsc_queries.ok
    bundle.gsc_keywords_error = gsc_queries.error or ""
    return bundle
