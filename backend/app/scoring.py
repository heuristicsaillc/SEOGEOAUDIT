"""Scoring + the narrative summary generator.

Turns parameter ratings into category and final scores/grades, then produces
the prioritized narrative shown at the top of each report.

Scoring rules (from the technical design):
- Each scored parameter earns weight * credit (1.0 Meeting / 0.5 Partial / 0.0 Not Meeting).
- Manual and Not Measured parameters are excluded from the denominator.
- Category score = weighted credit / weighted max; final = weighted average of categories.
"""

from __future__ import annotations  # Forward references for typing

from app.clients import GeminiClient  # Gemini writes the narrative
from app.models import RATING_CREDIT, CategoryResult, Priority, Rating, Report  # Models + credit table


# ============================================================================
# Scoring
# ============================================================================


def score_category(category: CategoryResult) -> CategoryResult:
    """Compute and set `category.score` (0-100) and the scored/manual counts."""
    earned = 0.0  # Sum of weight * credit over scored parameters
    possible = 0.0  # Sum of weight over scored parameters (the denominator)
    scored_count = 0  # Number of scored parameters
    manual_count = 0  # Number of Manual/Not Measured parameters (excluded)

    for param in category.parameters:  # Iterate every parameter row
        if param.is_scored:  # Only Meeting/Partial/Not Meeting count
            earned += param.weight * RATING_CREDIT[param.rating]  # Add earned credit
            possible += param.weight  # Add to the denominator
            scored_count += 1  # Tally a scored parameter
        else:  # Manual / Not Measured
            manual_count += 1  # Tally an excluded parameter

    # Category score is 0-100; a category with no scored parameters scores 0 but is weightless later
    category.score = round((earned / possible) * 100, 1) if possible > 0 else 0.0
    category.scored_count = scored_count  # Expose the scored count to the UI
    category.manual_count = manual_count  # Expose the excluded count to the UI
    return category  # Return the same (mutated) object for convenience


def score_report(report: Report) -> Report:
    """Score every category, then compute the report's final score + grade."""
    total_weighted = 0.0  # Sum of (category weight * category score)
    total_weight = 0.0  # Sum of weights for categories that had scored parameters
    manual_total = 0  # Total Manual/Not Measured across the report

    for category in report.categories:  # Score each category in turn
        score_category(category)  # Fill score + counts
        manual_total += category.manual_count  # Accumulate excluded count
        if category.scored_count > 0:  # Only categories with scored params affect the final score
            total_weighted += category.weight * category.score  # Weighted contribution
            total_weight += category.weight  # Accumulate weight

    report.score = round(total_weighted / total_weight, 1) if total_weight > 0 else 0.0  # Final 0-100
    report.grade = grade_for_score(report.score)  # Map to a letter grade
    report.manual_count = manual_total  # Total excluded parameters
    return report  # Return the mutated report


def grade_for_score(score: float) -> str:
    """Map a 0-100 score onto an A-F letter grade."""
    if score >= 90:  # 90-100
        return "A"  # Excellent
    if score >= 80:  # 80-89
        return "B"  # Good
    if score >= 70:  # 70-79
        return "C"  # Fair
    if score >= 60:  # 60-69
        return "D"  # Poor
    return "F"  # Below 60: failing


# ============================================================================
# Narrative summary
# ============================================================================

# Priority ordering used when ranking fixes (High first)
_PRIORITY_ORDER = {Priority.HIGH: 0, Priority.MEDIUM: 1, Priority.LOW: 2, None: 3}


async def generate_summary(report: Report, gemini: GeminiClient) -> str:
    """Return a prioritized narrative summary for `report` (Gemini, else deterministic)."""
    top_fixes = _top_fixes(report)  # The most impactful failing parameters

    if gemini.enabled:  # Prefer a Gemini-generated narrative
        narrative = await _gemini_narrative(report, top_fixes, gemini)  # Ask Gemini
        if narrative:  # Use it when available
            return narrative  # Gemini narrative

    return _fallback_narrative(report, top_fixes)  # Deterministic fallback


def _top_fixes(report: Report, limit: int = 6) -> list[tuple[str, str, str]]:
    """Return up to `limit` (category, parameter, recommendation) tuples, ranked.

    Ranking puts Not Meeting before Partial and High priority before Low.
    """
    candidates: list[tuple[int, int, str, str, str]] = []  # (rating_rank, prio_rank, cat, name, rec)
    for category in report.categories:  # Iterate every category
        for param in category.parameters:  # Iterate every parameter
            if param.rating not in (Rating.NOT_MEETING, Rating.PARTIAL):  # Only failing/partial rows
                continue  # Skip Meeting/Manual/Not Measured
            rating_rank = 0 if param.rating == Rating.NOT_MEETING else 1  # Not Meeting outranks Partial
            prio_rank = _PRIORITY_ORDER.get(param.priority, 3)  # High outranks Low
            candidates.append((rating_rank, prio_rank, category.title, param.name, param.recommendation))

    candidates.sort(key=lambda c: (c[0], c[1]))  # Sort by rating then priority
    # Return only the presentation fields for the top N candidates
    return [(c[2], c[3], c[4]) for c in candidates[:limit]]


async def _gemini_narrative(report: Report, top_fixes: list[tuple[str, str, str]], gemini: GeminiClient) -> str:
    """Ask Gemini to write a concise, prioritized narrative for the report."""
    kind = report.kind.upper()  # "SEO" or "GEO" for the prompt
    # Render the ranked fixes as bullet lines for the prompt
    fixes_text = "\n".join(f"- [{cat}] {name}: {rec}" for cat, name, rec in top_fixes) or "- (no major issues)"
    prompt = (  # The instruction sent to Gemini
        f"You are writing the executive summary of a {kind} audit. "
        f"Final score: {report.score}/100 (grade {report.grade}). "
        f"The highest-priority issues are:\n{fixes_text}\n\n"
        "Write a concise narrative (max 120 words) that: states the overall standing, "
        "lists the top fixes in priority order, and ends with the single biggest opportunity. "
        "Plain prose, no markdown headers."
    )
    return await gemini.complete(prompt)  # Gemini's narrative ("" if it failed)


def _fallback_narrative(report: Report, top_fixes: list[tuple[str, str, str]]) -> str:
    """Build a deterministic narrative when Gemini is unavailable."""
    kind = report.kind.upper()  # "SEO" or "GEO"
    lines = [  # Assemble the summary lines
        f"{kind} score: {report.score}/100 (grade {report.grade}). "
        f"{report.manual_count} parameter(s) require manual/owner data and are excluded from the score."
    ]
    if top_fixes:  # Add a prioritized fix list when issues exist
        lines.append("Top priority fixes:")  # Section lead-in
        for cat, name, rec in top_fixes:  # Each ranked fix
            lines.append(f"- [{cat}] {name}: {rec}")  # One bullet per fix
    else:  # No failing parameters
        lines.append("No major issues detected across scored parameters.")  # Positive note
    return "\n".join(lines)  # Joined narrative
