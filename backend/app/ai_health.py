"""Five-pillar AI Search Health score (technical readiness for AI search).

Pillars (industry-aligned technical AI readiness, not brand visibility):
  35% Access & discovery — AI bots, robots, indexability, llms.txt, sitemap
  25% Structured signals — JSON-LD, entities, FAQ
  20% Extractability — semantic HTML, chunking, plain text
  15% Citation readiness — answer-first content, E-E-A-T, AI quality
   5% Technical baseline — HTTPS, canonical, crawl depth
"""

from __future__ import annotations

from app.models import (
    RATING_CREDIT,
    CategoryResult,
    DetectionMethod,
    ParameterResult,
    Rating,
    Report,
)

ACCESS_PARAMS: dict[str, float] = {
    "GPTBot / ClaudeBot / PerplexityBot": 3.0,
    "Google-Extended bot blocking": 2.0,
    "Crawl rate limits": 1.0,
    "llms.txt": 1.5,
    "Meta robots": 2.0,
    "robots.txt": 1.5,
    "sitemap.xml": 1.0,
}

BASELINE_PARAMS: dict[str, float] = {
    "HTTPS / SSL": 1.5,
    "Canonical tags": 1.0,
    "Crawl depth": 1.0,
}

STRUCTURED_CATEGORIES = ("ai_structured_data", "entity_clarity")
EXTRACT_CATEGORY = "extractability"
CITATION_CATEGORIES = ("answerability", "citability", "ai_quality")
MULTIMODAL_CATEGORY = "multimodal"
MULTIMODAL_WEIGHT = 0.5

PILLAR_WEIGHTS = {
    "access": 0.35,
    "structured": 0.25,
    "extractability": 0.20,
    "citation": 0.15,
    "baseline": 0.05,
}


def compute_ai_search_health(seo: Report, geo: Report) -> tuple[float, dict[str, float]]:
    """Return (score 0-100, pillar breakdown)."""
    index = _index_parameters(seo, geo)

    access = _weighted_param_score(index, ACCESS_PARAMS)
    structured = _category_score(geo, STRUCTURED_CATEGORIES)
    extractability = _category_score(geo, (EXTRACT_CATEGORY,))
    citation = _citation_pillar_score(geo)
    baseline = _weighted_param_score(index, BASELINE_PARAMS)

    score = (
        PILLAR_WEIGHTS["access"] * access
        + PILLAR_WEIGHTS["structured"] * structured
        + PILLAR_WEIGHTS["extractability"] * extractability
        + PILLAR_WEIGHTS["citation"] * citation
        + PILLAR_WEIGHTS["baseline"] * baseline
    )

    if _all_major_ai_bots_blocked(index):
        score = min(score, 25.0)
    if _page_noindex(index):
        score = min(score, 15.0)

    breakdown = {
        "access": access,
        "structured": structured,
        "extractability": extractability,
        "citation": citation,
        "baseline": baseline,
    }
    return round(score, 1), breakdown


def attach_ai_search_health(seo: Report, geo: Report) -> float:
    """Compute AI Search Health, attach to geo panel and a zero-weight GEO category."""
    score, breakdown = compute_ai_search_health(seo, geo)
    geo.panel = dict(geo.panel or {})
    geo.panel["ai_search_health"] = {"score": score, **breakdown}

    if score >= 80:
        rating = Rating.MEETING
    elif score >= 60:
        rating = Rating.PARTIAL
    else:
        rating = Rating.NOT_MEETING

    param = ParameterResult(
        name="AI Search Health score",
        what_to_check="Five-pillar technical AI search readiness for the audited page",
        rating=rating,
        method=DetectionMethod.CRAWL,
        detail=(
            f"score={score:.1f}%; access={breakdown['access']:.1f}%; "
            f"structured={breakdown['structured']:.1f}%; extractability={breakdown['extractability']:.1f}%; "
            f"citation={breakdown['citation']:.1f}%; baseline={breakdown['baseline']:.1f}%"
        ),
        weight=0.0,
        evidence=breakdown,
    )
    geo.categories.append(
        CategoryResult(
            key="ai_search_health",
            title="AI Search Health",
            weight=0.0,
            parameters=[param],
            score=score,
            scored_count=1,
            manual_count=0,
        )
    )
    return score


def _index_parameters(*reports: Report) -> dict[str, ParameterResult]:
    index: dict[str, ParameterResult] = {}
    for report in reports:
        for category in report.categories:
            for param in category.parameters:
                index[param.name] = param
    return index


def _weighted_param_score(index: dict[str, ParameterResult], spec: dict[str, float]) -> float:
    earned = 0.0
    possible = 0.0
    for name, weight in spec.items():
        param = index.get(name)
        if param is None or not param.is_scored:
            continue
        earned += weight * RATING_CREDIT[param.rating]
        possible += weight
    return round((earned / possible) * 100, 1) if possible > 0 else 0.0


def _category_score(report: Report, keys: tuple[str, ...], *, param_weight: float = 1.0) -> float:
    earned = 0.0
    possible = 0.0
    for category in report.categories:
        if category.key not in keys:
            continue
        w = param_weight
        if category.key == MULTIMODAL_CATEGORY:
            w *= MULTIMODAL_WEIGHT
        for param in category.parameters:
            if not param.is_scored:
                continue
            earned += w * param.weight * RATING_CREDIT[param.rating]
            possible += w * param.weight
    return round((earned / possible) * 100, 1) if possible > 0 else 0.0


def _citation_pillar_score(geo: Report) -> float:
    earned = 0.0
    possible = 0.0
    boost = 1.2
    for category in geo.categories:
        if category.key not in CITATION_CATEGORIES:
            continue
        w_mult = boost if category.key in ("answerability", "citability") else 1.0
        for param in category.parameters:
            if not param.is_scored:
                continue
            w = w_mult * param.weight
            earned += w * RATING_CREDIT[param.rating]
            possible += w
    return round((earned / possible) * 100, 1) if possible > 0 else 0.0


def _all_major_ai_bots_blocked(index: dict[str, ParameterResult]) -> bool:
    param = index.get("GPTBot / ClaudeBot / PerplexityBot")
    if param is None or not param.is_scored:
        return False
    if param.rating != Rating.NOT_MEETING:
        return False
    detail = (param.detail or "").lower()
    return "gptbot" in detail and "claudebot" in detail and "perplexitybot" in detail


def _page_noindex(index: dict[str, ParameterResult]) -> bool:
    param = index.get("Meta robots")
    return param is not None and param.is_scored and param.rating == Rating.NOT_MEETING
