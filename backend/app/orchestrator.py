"""The async orchestrator that runs a full SEO + GEO audit.

Also holds the connected-property registry and the canonical agent list, since
both exist only to serve a run. Flow: crawl the page and fetch PSI concurrently,
run every agent concurrently, assemble + score two reports, then generate both
narrative summaries in parallel. Each agent is wrapped defensively so one
failure cannot break the whole audit.
"""

from __future__ import annotations  # Forward references for typing

import asyncio  # Concurrency primitives
import json  # Read the connected-property registry file
import time  # Wall-clock timing of the audit
from pathlib import Path  # Registry file path handling

from app.agents.base import AgentContext, BaseAgent  # Agent contract + context
from app.agents.geo_agents import (  # The 8 GEO agents
    AiBotCrawlabilityAgent,
    AiQualityAgent,
    AiStructuredDataAgent,
    AnswerabilityAgent,
    CitabilityAgent,
    EntityClarityAgent,
    ExtractabilityAgent,
    MultimodalAgent,
)
from app.agents.seo_agents import (  # The 7 SEO agents
    CoreWebVitalsAgent,
    CrawlabilityAgent,
    OffPageAgent,
    OnPageAgent,
    StructuredDataAgent,
    TechnicalAgent,
    UxAgent,
)
from app.clients import Clients, build_async_client  # External clients + HTTP factory
from app.config import Settings, get_settings  # Application configuration
from app.crawl import Fetcher, normalise_url, registrable_host  # Page fetching + host key
from app.models import AuditResponse, CategoryResult, ParameterResult, Report  # Models
from app.scoring import generate_summary, score_report  # Scoring + narrative


# ============================================================================
# Connected-property registry
# ============================================================================


class ConnectedRegistry:
    """Loads and queries the connected_properties.json mapping (domain -> GSC/GA4 ids)."""

    def __init__(self, settings: Settings) -> None:
        """Load the registry file once at construction."""
        self._mapping: dict[str, dict] = {}  # domain -> {gsc_site_url, ga4_property_id}
        path = Path(settings.connected_properties_path)  # Configured registry path
        if path.exists():  # Only read when the file is present
            try:  # The file may be malformed
                data = json.loads(path.read_text(encoding="utf-8"))  # Parse the JSON
                # Keep only real entries (skip helper keys that start with "_")
                self._mapping = {k: v for k, v in data.items() if not k.startswith("_")}
            except Exception:  # Malformed JSON
                self._mapping = {}  # Treat as an empty registry

    def lookup(self, host: str) -> dict | None:
        """Return the connection info for `host` (or None when not connected)."""
        return self._mapping.get(registrable_host(host))  # www and apex share one registry entry


# ============================================================================
# Agent list
# ============================================================================


def build_agents() -> list[BaseAgent]:
    """Instantiate every agent in report/category order (orchestrator runs them concurrently)."""
    return [
        # SEO (7 categories)
        CrawlabilityAgent(),  # 01 Crawlability & Indexability
        OnPageAgent(),  # 02 On-Page Signals
        TechnicalAgent(),  # 03 Technical SEO
        CoreWebVitalsAgent(),  # 04 Core Web Vitals & Performance
        StructuredDataAgent(),  # 05 Structured Data & Social
        OffPageAgent(),  # 06 Off-Page & Authority
        UxAgent(),  # 07 UX & Engagement Signals
        # GEO (8 categories)
        AnswerabilityAgent(),  # 01 Answerability
        ExtractabilityAgent(),  # 02 Extractability
        CitabilityAgent(),  # 03 Citability & E-E-A-T
        AiStructuredDataAgent(),  # 04 AI Structured Data
        EntityClarityAgent(),  # 05 Entity Clarity
        AiBotCrawlabilityAgent(),  # 06 AI-Bot Crawlability
        AiQualityAgent(),  # 07 AI Quality Scores
        MultimodalAgent(),  # 08 Multimodal & Voice GEO
    ]


# ============================================================================
# Orchestrator
# ============================================================================


class AuditOrchestrator:
    """Coordinates crawl, agents, scoring and narrative for one audit."""

    def __init__(self, settings: Settings | None = None) -> None:
        """Load settings and the connected-property registry once."""
        self._settings = settings or get_settings()  # Use provided settings or the cached singleton
        self._registry = ConnectedRegistry(self._settings)  # Registry is cheap to keep around

    async def run(self, url: str) -> AuditResponse:
        """Run the full audit for `url` and return both reports."""
        start = time.perf_counter()  # Begin timing
        normalised = normalise_url(url)  # Ensure the URL has a scheme

        # One HTTP client is shared by the crawl and all REST-based API clients
        async with build_async_client(self._settings) as http:  # Auto-closes when done
            clients = Clients.create(self._settings, http)  # Wire all external clients
            fetcher = Fetcher(http, self._settings, clients.firecrawl)  # Page fetcher

            # Crawl the page and fetch PSI (mobile + desktop) concurrently
            page, psi_mobile, psi_desktop = await asyncio.gather(
                fetcher.fetch(normalised),  # Build the PageContext
                clients.psi.analyze(normalised, "mobile"),  # PSI mobile run
                clients.psi.analyze(normalised, "desktop"),  # PSI desktop run
            )
            page.psi_mobile = psi_mobile  # Attach PSI payloads for the CWV/technical agents
            page.psi_desktop = psi_desktop  # Desktop PSI payload

            # Resolve connected-property info for this domain (None when not connected)
            connection = self._registry.lookup(page.host)  # Registry lookup by host
            ctx = AgentContext(  # Build the context every agent receives
                page=page, clients=clients, connection=connection
            )

            # Run every agent concurrently; collect their result lists
            agents = build_agents()  # Instantiate all agents
            outcomes = await asyncio.gather(
                *(self._run_agent(agent, ctx) for agent in agents),  # One task per agent
            )

            # Build the two reports from the agent outcomes
            seo_report, geo_report, panels = self._assemble_reports(agents, outcomes)

            # Score both reports (categories -> final score + grade)
            score_report(seo_report)  # SEO scoring
            score_report(geo_report)  # GEO scoring

            # Attach the UI panels (CWV for SEO, citations for GEO)
            seo_report.panel = panels.get("cwv", {})  # Core Web Vitals panel
            geo_report.panel = panels.get("citations", {})  # AI-citation panel

            # Generate both narrative summaries concurrently
            seo_summary, geo_summary = await asyncio.gather(
                generate_summary(seo_report, clients.gemini),  # SEO narrative
                generate_summary(geo_report, clients.gemini),  # GEO narrative
            )
            seo_report.summary = seo_summary  # Attach SEO narrative
            geo_report.summary = geo_summary  # Attach GEO narrative

            duration = round(time.perf_counter() - start, 2)  # Total wall-clock time
            return AuditResponse(  # Assemble the API response
                url=normalised,  # The normalised URL
                final_url=page.final_url or normalised,  # URL after redirects
                connected=connection is not None,  # Connected-mode flag
                seo=seo_report,  # SEO report
                geo=geo_report,  # GEO report
                duration_seconds=duration,  # Timing
                errors=page.errors,  # Non-fatal crawl errors
            )

    @staticmethod
    async def _run_agent(agent: BaseAgent, ctx: AgentContext) -> list[ParameterResult]:
        """Run one agent, converting any exception into an empty result list."""
        try:  # Agents should not raise, but guard anyway
            return await agent.analyze(ctx)  # Run the agent's analysis
        except Exception as exc:  # Capture the failure
            ctx.page.errors.append(f"agent {agent.key} failed: {exc}")  # Record it for the response
            return []  # An empty category rather than a crashed audit

    @staticmethod
    def _assemble_reports(
        agents: list[BaseAgent],
        outcomes: list[list[ParameterResult]],
    ) -> tuple[Report, Report, dict]:
        """Group agent outputs into SEO/GEO reports and collect UI panels."""
        seo = Report(kind="seo")  # Empty SEO report
        geo = Report(kind="geo")  # Empty GEO report
        panels: dict = {}  # Collected panel data (cwv, citations)

        for agent, results in zip(agents, outcomes):  # Pair each agent with its rows
            category = CategoryResult(  # Build the category container
                key=agent.key, title=agent.title, weight=agent.weight, parameters=results
            )
            # Route the category into the correct report
            (seo if agent.kind == "seo" else geo).categories.append(category)
            # Collect any panel an agent exposed (CWV agent / AI-quality agent)
            panel = getattr(agent, "_panel", None)  # Agents set _panel during analyze()
            if panel and agent.key == "cwv":  # Core Web Vitals panel for the SEO report
                panels["cwv"] = panel  # Store CWV summary
            elif panel and agent.key == "ai_quality":  # Citation panel for the GEO report
                panels["citations"] = panel  # Store citation summary

        return seo, geo, panels  # Both reports + panels
