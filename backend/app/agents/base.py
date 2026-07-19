"""The agent framework and every helper an agent needs.

Combined here so an agent module only ever imports from two places: this file
(framework + helpers) and `app.models` (enums + result type). Contents:
  1. AgentContext + BaseAgent      - the contract every agent implements
  2. Result factories              - scored / manual / not_measured / llm_scored
  3. PSI accessors                 - read values out of a PageSpeed Insights payload
  4. JSON-LD query helpers         - inspect parsed structured data
"""

from __future__ import annotations  # Forward references for typing

import json  # Cheap containment checks over JSON-LD blocks
from abc import ABC, abstractmethod  # Abstract base class machinery
from dataclasses import dataclass  # Lightweight context container

from app.clients import Clients  # External clients passed to agents
from app.crawl import PageContext  # The shared page signals
from app.models import (  # Enums + the per-parameter result type
    Confidence,
    DetectionMethod,
    Priority,
    Rating,
    ParameterResult,
)


# ============================================================================
# 1. AgentContext + BaseAgent
# ============================================================================


@dataclass
class AgentContext:
    """Everything an agent needs to do its job, bundled into one object."""

    page: PageContext  # All crawled/parsed signals for the audited page
    clients: Clients  # External API clients (Gemini, PSI, Serper, ...)
    connection: dict | None  # {gsc_site_url, ga4_property_id} when connected, else None

    @property
    def is_connected(self) -> bool:
        """Whether the audited domain is a connected GA4/GSC property."""
        return self.connection is not None  # Connected when registry info is present


class BaseAgent(ABC):
    """Abstract analysis agent for a single SEO or GEO category."""

    key: str = ""  # Stable machine key (e.g. "crawlability")
    title: str = ""  # Display title (e.g. "Crawlability & Indexability")
    kind: str = ""  # "seo" or "geo"
    weight: float = 1.0  # Category weight in the final score

    @abstractmethod
    async def analyze(self, ctx: AgentContext) -> list[ParameterResult]:
        """Evaluate this category and return its parameter rows.

        Implementations should prefer returning a Not Measured row over raising
        so a single failure cannot blank a category (the orchestrator also wraps
        each agent defensively).
        """
        raise NotImplementedError  # Subclasses provide the real implementation


# ============================================================================
# 2. Result factories
# ============================================================================


def scored(
    name: str,
    what_to_check: str,
    meeting: bool | None,
    method: DetectionMethod,
    *,
    partial: bool = False,
    detail: str = "",
    recommendation: str = "",
    fix_where: str = "",
    priority: Priority = Priority.MEDIUM,
    effort: str = "Low",
    weight: float = 1.0,
    confidence: Confidence = Confidence.HIGH,
    evidence: dict | None = None,
) -> ParameterResult:
    """Build a scored row from a boolean (or tri-state) pass/fail signal.

    `meeting=True` -> Meeting; `partial=True` -> Partial; otherwise Not Meeting.
    A recommendation/priority is attached only when the parameter is not Meeting.
    """
    # Decide the rating from the boolean inputs
    if meeting:  # Clearly satisfied
        rating = Rating.MEETING  # Full credit
    elif partial:  # Partially satisfied
        rating = Rating.PARTIAL  # Half credit
    else:  # Not satisfied
        rating = Rating.NOT_MEETING  # Zero credit

    return ParameterResult(  # Construct the uniform result row
        name=name,  # Parameter name
        what_to_check=what_to_check,  # Ideal-state description
        rating=rating,  # Computed rating
        method=method,  # Detection method
        confidence=confidence,  # Confidence label
        weight=weight,  # Category-relative weight
        detail=detail,  # Evidence string
        # Only attach a fix when there is room to improve
        recommendation=recommendation if rating != Rating.MEETING else "",
        fix_where=fix_where if rating != Rating.MEETING else "",
        priority=priority if rating != Rating.MEETING else None,  # Priority only when actionable
        effort=effort if rating != Rating.MEETING else "",  # Effort only when actionable
        evidence=evidence or {},  # Structured evidence for the UI
    )


def manual(
    name: str,
    what_to_check: str,
    reason: str,
    *,
    recommendation: str = "",
) -> ParameterResult:
    """Build a Manual row: shown in the report but excluded from the score."""
    return ParameterResult(
        name=name,  # Parameter name
        what_to_check=what_to_check,  # Ideal-state description
        rating=Rating.MANUAL,  # Excluded from the denominator
        method=DetectionMethod.MANUAL,  # Requires data the tool cannot obtain
        confidence=Confidence.NONE,  # Not measured
        detail=reason,  # Why it cannot be measured automatically
        recommendation=recommendation or reason,  # Specific guidance (shown in the UI)
    )


def first_party_empty(
    name: str,
    what_to_check: str,
    detail: str,
    *,
    recommendation: str = "",
) -> ParameterResult:
    """Connected first-party source responded but has no data for this page (excluded from score)."""
    return ParameterResult(
        name=name,
        what_to_check=what_to_check,
        rating=Rating.NOT_MEASURED,
        method=DetectionMethod.FIRST_PARTY,
        confidence=Confidence.NONE,
        detail=detail,
        recommendation=recommendation or detail,
    )


def not_measured(
    name: str,
    what_to_check: str,
    method: DetectionMethod,
    reason: str,
) -> ParameterResult:
    """Build a Not Measured row: an automated check could not run (excluded)."""
    return ParameterResult(
        name=name,  # Parameter name
        what_to_check=what_to_check,  # Ideal-state description
        rating=Rating.NOT_MEASURED,  # Excluded from the score
        method=method,  # The method that was attempted
        confidence=Confidence.NONE,  # Nothing was measured
        detail=reason,  # Why the check could not run (e.g. missing key)
    )


def rating_from_llm(verdict: dict) -> Rating | None:
    """Map a Gemini judge() verdict's rating string onto our Rating enum.

    Returns None when the verdict is empty/unrecognised so the caller can fall
    back to a heuristic or mark the parameter Not Measured.
    """
    value = (verdict or {}).get("rating", "").strip().lower()  # Normalise the rating string
    if value == "meeting":  # Exact match
        return Rating.MEETING  # Full credit
    if value == "partial":  # Exact match
        return Rating.PARTIAL  # Half credit
    if value in ("not meeting", "not-meeting", "notmeeting"):  # Tolerate punctuation variants
        return Rating.NOT_MEETING  # Zero credit
    return None  # Unrecognised/empty verdict


async def llm_scored(
    name: str,
    what_to_check: str,
    *,
    gemini,  # GeminiClient (untyped to avoid importing the class here)
    signal: str,
    fallback_meeting: bool,
    fallback_detail: str = "",
    recommendation: str = "",
    priority: Priority = Priority.MEDIUM,
    effort: str = "Low",
    weight: float = 1.0,
) -> ParameterResult:
    """Judge a parameter with Gemini, falling back to a heuristic boolean.

    Calls Gemini's judge() with `signal`; if a usable verdict comes back it is
    used (method = LLM). Otherwise the deterministic `fallback_meeting` boolean
    decides the rating (method = Crawl) so the parameter is still scored.
    """
    verdict = await gemini.judge(signal) if getattr(gemini, "enabled", False) else {}  # Ask Gemini
    rating = rating_from_llm(verdict)  # Try to map the verdict to a Rating
    if rating is not None:  # Gemini gave a usable verdict
        return ParameterResult(
            name=name,  # Parameter name
            what_to_check=what_to_check,  # Ideal-state description
            rating=rating,  # LLM-derived rating
            method=DetectionMethod.LLM,  # Detected via Gemini judgement
            confidence=Confidence.MEDIUM,  # LLM judgement is medium confidence
            weight=weight,  # Category-relative weight
            detail=verdict.get("detail", "")[:300],  # Evidence from Gemini (bounded)
            recommendation=(verdict.get("recommendation", "") or recommendation)
            if rating != Rating.MEETING
            else "",  # Use Gemini's fix, else the supplied default
            priority=priority if rating != Rating.MEETING else None,  # Priority when actionable
            effort=effort if rating != Rating.MEETING else "",  # Effort when actionable
        )
    # Gemini unavailable/failed: fall back to the deterministic heuristic
    return scored(
        name,
        what_to_check,
        fallback_meeting,  # Heuristic decides Meeting vs Not Meeting
        DetectionMethod.CRAWL,  # Heuristic relies on crawl signals
        detail=fallback_detail or "Heuristic fallback (Gemini unavailable).",  # Note the fallback
        recommendation=recommendation,  # Supplied default fix
        priority=priority,  # Supplied default priority
        effort=effort,  # Supplied default effort
        weight=weight,  # Category-relative weight
        confidence=Confidence.LOW,  # Heuristic fallback is low confidence
    )


# ============================================================================
# 3. PSI accessors (read values from a PageSpeed Insights payload)
# ============================================================================


def lighthouse(psi: dict) -> dict:
    """Return the lighthouseResult object ({} when absent)."""
    return (psi or {}).get("lighthouseResult", {})  # Top-level Lighthouse container


def category_score(psi: dict, category: str) -> float | None:
    """Return a Lighthouse category score 0-100 (None when missing).

    `category` is one of performance|accessibility|best-practices|seo.
    """
    cats = lighthouse(psi).get("categories", {})  # All category scores
    raw = cats.get(category, {}).get("score")  # Score is 0..1 or None
    return round(raw * 100, 1) if isinstance(raw, (int, float)) else None  # Scale to 0-100


def audit_numeric(psi: dict, audit_id: str) -> float | None:
    """Return an audit's numericValue (e.g. LCP ms) or None when missing."""
    audits = lighthouse(psi).get("audits", {})  # All Lighthouse audits
    value = audits.get(audit_id, {}).get("numericValue")  # Numeric result of the audit
    return value if isinstance(value, (int, float)) else None  # Guard against missing values


def audit_score(psi: dict, audit_id: str) -> float | None:
    """Return an audit's 0..1 score or None when missing."""
    audits = lighthouse(psi).get("audits", {})  # All Lighthouse audits
    value = audits.get(audit_id, {}).get("score")  # 0..1 score for the audit
    return value if isinstance(value, (int, float)) else None  # Guard against missing values


def crux_metric(psi: dict, metric: str) -> dict:
    """Return a CrUX field-data metric block ({} when absent).

    `metric` examples: LARGEST_CONTENTFUL_PAINT_MS, CUMULATIVE_LAYOUT_SHIFT_SCORE,
    INTERACTION_TO_NEXT_PAINT, EXPERIMENTAL_TIME_TO_FIRST_BYTE.
    """
    loading = (psi or {}).get("loadingExperience", {})  # Field (CrUX) experience block
    return loading.get("metrics", {}).get(metric, {})  # The requested metric block or {}


# ============================================================================
# 4. JSON-LD query helpers (inspect parsed structured data on a PageContext)
# ============================================================================


def jsonld_types(page: PageContext) -> set[str]:
    """Return the set of @type values present across all JSON-LD blocks."""
    types: set[str] = set()  # Accumulate type names
    for block in page.jsonld:  # Iterate parsed JSON-LD entities
        value = block.get("@type")  # The @type may be a string or list
        if isinstance(value, str):  # Single type
            types.add(value)  # Add it
        elif isinstance(value, list):  # Multiple types
            types.update(str(v) for v in value)  # Add each
    return types  # Set of all schema types found


def type_present(page: PageContext, type_name: str) -> bool:
    """Return True if any JSON-LD block declares @type == `type_name`."""
    for block in page.jsonld:  # Iterate parsed JSON-LD entities
        t = block.get("@type")  # The block's @type (string or list)
        if t == type_name or (isinstance(t, list) and type_name in t):  # Match either form
            return True  # Found
    return False  # Not present


def block_mentions(page: PageContext, needle: str) -> bool:
    """Return True if any JSON-LD block contains `needle` anywhere in its values."""
    needle_l = needle.lower()  # Case-insensitive comparison
    for block in page.jsonld:  # Iterate JSON-LD blocks
        try:  # Serialisation can rarely fail on exotic content
            if needle_l in json.dumps(block).lower():  # Substring match over the serialised block
                return True  # Found
        except Exception:  # Non-serialisable block
            continue  # Skip it
    return False  # Not present
