"""All data shapes for the auditor: enums, parameter results, reports and the API envelope.

Kept in one module because these models are small and tightly coupled (a Report
holds Categories, which hold ParameterResults, which use the enums).
"""

from __future__ import annotations  # Forward references for typing

from enum import Enum  # Standard library enumeration support

from pydantic import BaseModel, Field  # Base model + field metadata


# ============================================================================
# Enumerations
# ============================================================================


class Rating(str, Enum):
    """How well a single parameter is satisfied.

    Scored parameters use MEETING/PARTIAL/NOT_MEETING. MANUAL marks a parameter
    that is shown but excluded from the denominator. NOT_MEASURED is used when an
    automated check could not run (e.g. a required API key was missing).
    """

    MEETING = "Meeting"  # Full credit (weight * 1.0)
    PARTIAL = "Partial"  # Half credit (weight * 0.5)
    NOT_MEETING = "Not Meeting"  # Zero credit (weight * 0.0)
    MANUAL = "Manual"  # Excluded from score; requires off-site/owner data
    NOT_MEASURED = "Not Measured"  # Automated check could not be performed; excluded from score


# Maps a scored rating to the fraction of its weight it earns
RATING_CREDIT: dict[Rating, float] = {
    Rating.MEETING: 1.0,  # Meeting => full weight
    Rating.PARTIAL: 0.5,  # Partial => half weight
    Rating.NOT_MEETING: 0.0,  # Not Meeting => no weight
}


class DetectionMethod(str, Enum):
    """How a parameter is detected, mirroring the design's method legend."""

    CRAWL = "Crawl"  # httpx + Playwright + BeautifulSoup parsing
    PSI = "PSI"  # Google PageSpeed Insights API
    LLM = "LLM"  # Gemini judgement
    EXTERNAL = "External"  # Third-party API (Serper, Perplexity, SerpApi, ...)
    FIRST_PARTY = "First-party"  # GA4 / Search Console (connected properties)
    MANUAL = "Manual"  # Data the tool cannot obtain automatically


class Confidence(str, Enum):
    """Confidence label attached to a result for transparency in the UI."""

    MEASURED = "Measured"  # Directly measured (e.g. first-party GA4/GSC data)
    HIGH = "High"  # Deterministic crawl/PSI signal
    MEDIUM = "Medium"  # Heuristic or LLM judgement
    LOW = "Low"  # Weak/ambiguous signal
    NONE = "None"  # Not measured at all


class Priority(str, Enum):
    """Priority of a recommended fix."""

    HIGH = "High"  # Fix first; large impact
    MEDIUM = "Med"  # Worthwhile improvement
    LOW = "Low"  # Nice to have


# ============================================================================
# Per-parameter result
# ============================================================================


class ParameterResult(BaseModel):
    """One row in a category table: a parameter that was (or could not be) checked.

    Agents construct these; the scorer reads `rating`/`weight`; the report renders
    `name`, `what_to_check`, `rating` and `recommendation`.
    """

    name: str  # Human-readable parameter name (e.g. "Title tag")
    what_to_check: str  # Short description of the ideal state, shown in the report
    rating: Rating  # Meeting / Partial / Not Meeting / Manual / Not Measured
    method: DetectionMethod  # How this parameter was detected
    confidence: Confidence = Confidence.MEDIUM  # Confidence label for transparency
    weight: float = 1.0  # Relative weight inside its category (default equal weighting)

    detail: str = ""  # Evidence/explanation of why this rating was assigned
    recommendation: str = ""  # Concrete fix (empty when Meeting)
    priority: Priority | None = None  # Priority of the fix (None when Meeting/Manual)
    effort: str = ""  # Rough effort estimate for the fix (e.g. "Low", "1-2h")

    # Free-form structured evidence (e.g. measured values) for the UI panels
    evidence: dict = Field(default_factory=dict)

    @property
    def is_scored(self) -> bool:
        """True when this parameter counts toward its category score."""
        # Only Meeting/Partial/Not Meeting contribute; Manual & Not Measured are excluded
        return self.rating in (Rating.MEETING, Rating.PARTIAL, Rating.NOT_MEETING)


# ============================================================================
# Category + report aggregation
# ============================================================================


class CategoryResult(BaseModel):
    """A scored category (e.g. "Crawlability & Indexability") with its parameters."""

    key: str  # Stable machine key (e.g. "crawlability")
    title: str  # Display title (e.g. "Crawlability & Indexability")
    weight: float = 1.0  # Category weight in the final SEO/GEO score
    score: float = 0.0  # Category score 0-100 (filled by the scorer)
    parameters: list[ParameterResult] = Field(default_factory=list)  # Rows in this category

    # Convenience counts surfaced to the UI
    scored_count: int = 0  # Parameters that counted toward the score
    manual_count: int = 0  # Manual parameters (shown, excluded)


class Report(BaseModel):
    """A complete SEO or GEO report: final score, grade, categories and narrative."""

    kind: str  # "seo" or "geo"
    score: float = 0.0  # Final 0-100 score across categories
    grade: str = "F"  # Letter grade A-F derived from `score`
    summary: str = ""  # Gemini-generated prioritized narrative summary
    categories: list[CategoryResult] = Field(default_factory=list)  # All categories
    manual_count: int = 0  # Total manual parameters across the report
    panel: dict = Field(default_factory=dict)  # Extra UI panel data (CWV for SEO, citations for GEO)


# ============================================================================
# API request/response envelopes
# ============================================================================


class AuditRequest(BaseModel):
    """Body of POST /api/audit: the URL the user wants audited."""

    url: str = Field(..., description="The page URL to audit, e.g. https://example.com/")


class AuditResponse(BaseModel):
    """Response of POST /api/audit: both reports plus run metadata."""

    url: str  # The normalised URL that was audited
    final_url: str  # URL after following redirects
    connected: bool  # Whether the domain is a connected GA4/GSC property
    seo: Report  # The SEO report (one tab in the UI)
    geo: Report  # The GEO report (the other tab)
    duration_seconds: float  # Wall-clock time the audit took
    errors: list[str] = Field(default_factory=list)  # Non-fatal errors collected during the run


class ReportPdfRequest(BaseModel):
    """Body of POST /api/report/pdf: one report plus run metadata for the PDF header."""

    final_url: str  # Audited URL shown on the cover
    duration_seconds: float = 0.0  # Audit duration in seconds
    connected: bool = False  # Whether GA4/GSC connected mode was active
    report: Report  # The SEO or GEO report to export


class SupplementaryPdfRequest(BaseModel):
    """Body of POST /api/report/supplementary-pdf: reference-style supplementary export."""

    final_url: str  # Audited URL shown on the cover
    duration_seconds: float = 0.0  # Audit duration in seconds
    connected: bool = False  # Whether GA4/GSC connected mode was active
    seo: Report  # Full SEO report (parameter lookup only)
    geo: Report  # Full GEO report (parameter lookup only)
    kind: str = Field(
        ...,
        description="performance_baseline | site_audit_full | ai_search_overview",
    )
