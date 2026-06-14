#!/usr/bin/env python3
"""Compare reference PDFs vs SEO GEO Auditor generated PDFs; emit a comparison PDF."""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from datetime import date
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from pypdf import PdfReader
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.reference_pdf_catalog import (  # noqa: E402
    AI_SEARCH_OVERVIEW_PARAMS,
    BASELINE_PARAMS,
    CATALOG_BY_PDF,
    PDF_TITLES,
    SITE_AUDIT_FULL_PARAMS,
    RefParameter,
)

REF_DIR = Path("/Users/maneeshmukundan/Documents/Heuristics AI LLC/SEOGEO Audit")
OUT_DIR = REF_DIR / "Comparison"

GEN_GLOBS = {
    "performance_baseline": "performance-baseline-*.pdf",
    "site_audit_full": "heuristics-full-site-audit-*.pdf",
    "ai_search_overview": "heuristics-ai-search-overview-*.pdf",
}


def _latest_generated(kind: str) -> Path:
    """Pick the newest generated PDF for a kind in the Comparison folder."""
    pattern = GEN_GLOBS[kind]
    candidates = [
        p
        for p in OUT_DIR.glob(pattern)
        if p.is_file() and not p.name.startswith("PDF-Parameter-Comparison")
    ]
    if not candidates:
        raise FileNotFoundError(f"No generated PDF matching {pattern} in {OUT_DIR}")
    return max(candidates, key=lambda p: p.stat().st_mtime)


REF_FILES = {
    "performance_baseline": REF_DIR
    / "Performance_Baseline-Traffic__Engagement__SEO___Web_Vitals___Feb_20__20-21st_May_2026.pdf",
    "site_audit_full": REF_DIR / "Semrush-Full_Site_Audit_Report-optiorx_com-6th_Feb_2026.pdf",
    "ai_search_overview": REF_DIR / "Semrush-Site_Audit__Overview-optiorx_com-9th_Jun_2026.pdf",
}


def _gen_files() -> dict[str, Path]:
    return {kind: _latest_generated(kind) for kind in REF_FILES}

MARGIN = 14 * mm
PAGE_SIZE = A4
USABLE = PAGE_SIZE[0] - 2 * MARGIN


@dataclass
class ParamRow:
    parameter: str
    reference: str
    generated: str
    why_not_calculated: str


def _read_pdf_text(path: Path) -> str:
    return "\n".join(page.extract_text() or "" for page in PdfReader(str(path)).pages)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def _parse_manual_appendix(text: str, catalog_names: list[str] | None = None) -> dict[str, str]:
    """Return parameter -> reason from generated PDF manual appendix."""
    out: dict[str, str] = {}
    marker = "Parameters Not Calculated (Manual)"
    if marker not in text:
        return out
    section = text.split(marker, 1)[1]
    names = catalog_names or []
    for name in sorted(names, key=len, reverse=True):
        # PDF may wrap long parameter names across lines
        variants = [
            name,
            name.replace(" (", "\n("),
            name.replace("/", "\n/"),
        ]
        for variant in variants:
            idx = section.find(variant)
            if idx < 0:
                continue
            tail = section[idx + len(variant) :]
            # Next lines: Section label, then reason (until next known parameter)
            lines = [ln.strip() for ln in tail.splitlines() if ln.strip()]
            reason_lines: list[str] = []
            for line in lines:
                if line in (
                    "Performance Baseline",
                    "Errors",
                    "Warnings",
                    "Notices",
                    "AI Search Overview",
                ):
                    continue
                if any(line.startswith(n.split("(")[0][:20]) for n in names if n != name):
                    break
                if any(n.startswith(line) and n != name for n in names):
                    break
                reason_lines.append(line)
            reason = " ".join(reason_lines).strip()
            if reason:
                out[name] = reason
            break
    return out


def _parse_site_audit_issues(text: str) -> dict[str, str]:
    """Map catalog-style issue labels to counts from audit PDF text."""
    out: dict[str, str] = {}
    patterns = [
        (r"(\d+)\s+pages returned 5XX status code(?:\s+\d+\s+\d+)?", "Pages returned 5XX status code"),
        (r"(\d+)\s+pages returned 4XX status code(?:\s+\d+\s+\d+)?", "Pages returned 4XX status code"),
        (r"(\d+)\s+pages don't have title tags(?:\s+\d+\s+\d+)?", "Pages don't have title tags"),
        (r"(\d+)\s+issues with duplicate title tags(?:\s+\d+\s+\d+)?", "Issues with duplicate title tags"),
        (r"(\d+)\s+pages have duplicate content issues(?:\s+\d+\s+\d+)?", "Pages have duplicate content issues"),
        (r"(\d+)\s+internal links are broken(?:\s+\d+\s+\d+)?", "Internal links are broken"),
        (r"(\d+)\s+pages couldn't be crawled(?:\s+\d+\s+\d+)?(?! \()", "Pages couldn't be crawled"),
        (
            r"(\d+)\s+pages couldn't be crawled \(DNS resolution issues\)(?:\s+\d+\s+\d+)?",
            "Pages couldn't be crawled (DNS resolution issues)",
        ),
        (
            r"(\d+)\s+pages couldn't be crawled \(incorrect URL formats\)(?:\s+\d+\s+\d+)?",
            "Pages couldn't be crawled (incorrect URL formats)",
        ),
        (r"(\d+)\s+internal images are broken(?:\s+\d+\s+\d+)?", "Internal images are broken"),
        (
            r"(\d+)\s+pages have duplicate meta descriptions(?:\s+\d+\s+\d+)?",
            "Pages have duplicate meta descriptions",
        ),
        (r"Robots\.txt file has format errors(?:\s+\d+\s+\d+)?", "Robots.txt file has format errors"),
        (r"(\d+)\s+sitemap\.xml files have format errors(?:\s+\d+\s+\d+)?", "sitemap.xml files have format errors"),
        (
            r"(\d+)\s+incorrect pages found in sitemap\.xml(?:\s+\d+\s+\d+)?",
            "Incorrect pages found in sitemap.xml",
        ),
        (r"(\d+)\s+pages have a WWW resolve issue(?:\s+\d+\s+\d+)?", "Pages have a WWW resolve issue"),
        (r"This page has no viewport tag(?:\s+\d+\s+\d+)?", "This page has no viewport tag"),
        (r"(\d+)\s+pages have too large HTML size(?:\s+\d+\s+\d+)?", "Pages have too large HTML size"),
        (r"AMP pages have no canonical tag(?:\s+\d+\s+\d+)?", "AMP pages have no canonical tag"),
        (r"(\d+)\s+AMP pages have no canonical tag(?:\s+\d+\s+\d+)?", "AMP pages have no canonical tag"),
        (r"(\d+)\s+issues with hreflang values(?:\s+\d+\s+\d+)?", "Issues with hreflang values"),
        (
            r"(\d+)\s+hreflang conflicts within page source code(?:\s+\d+\s+\d+)?",
            "hreflang conflicts within page source code",
        ),
        (
            r"(\d+)\s+issues with incorrect hreflang links(?:\s+\d+\s+\d+)?",
            "Issues with incorrect hreflang links",
        ),
        (r"(\d+)\s+non-secure pages(?:\s+\d+\s+\d+)?", "Non-secure pages"),
        (
            r"(\d+)\s+issues with expiring or expired certificate(?:\s+\d+\s+\d+)?",
            "Issues with expiring or expired certificate",
        ),
        (
            r"(\d+)\s+issues with old security protocol(?:\s+\d+\s+\d+)?",
            "Issues with old security protocol",
        ),
        (
            r"(\d+)\s+issues with incorrect certificate name(?:\s+\d+\s+\d+)?",
            "Issues with incorrect certificate name",
        ),
        (r"(\d+)\s+issues with mixed content(?:\s+\d+\s+\d+)?", "Issues with mixed content"),
        (
            r"No redirect or canonical to HTTPS homepage from HTTP(?: version)?(?:\s+\d+\s+\d+)?",
            "No redirect or canonical to HTTPS homepage from HTTP",
        ),
        (r"(\d+)\s+pages with a broken canonical link(?:\s+\d+\s+\d+)?", "Pages with a broken canonical link"),
        (r"(\d+)\s+pages have multiple canonical URLs(?:\s+\d+\s+\d+)?", "Pages have multiple canonical URLs"),
        (r"(\d+)\s+pages have a meta refresh tag(?:\s+\d+\s+\d+)?", "Pages have a meta refresh tag"),
        (
            r"(\d+)\s+issues with broken internal JavaScript and CSS files(?:\s+\d+\s+\d+)?",
            "Issues with broken internal JavaScript and CSS files",
        ),
        (
            r"(\d+)\s+subdomains don't support secure encryption algorithms(?:\s+\d+\s+\d+)?",
            "Subdomains don't support secure encryption algorithms",
        ),
        (r"(\d+)\s+sitemap\.xml files are too large(?:\s+\d+\s+\d+)?", "sitemap.xml files are too large"),
        (
            r"(\d+)\s+links couldn't be crawled \(incorrect URL formats\)(?:\s+\d+\s+\d+)?",
            "Links couldn't be crawled (incorrect URL formats)",
        ),
        (r"(\d+)\s+structured data items are invalid(?:\s+\d+\s+\d+)?", "Structured data items are invalid"),
        (
            r"(\d+)\s+pages are missing the viewport width value(?:\s+\d+\s+\d+)?",
            "Pages are missing the viewport width value",
        ),
        (r"(\d+)\s+pages have slow load speed(?:\s+\d+\s+\d+)?", "Pages have slow load speed"),
        (r"(\d+)\s+external links are broken(?:\s+\d+\s+\d+)?", "External links are broken"),
        (r"(\d+)\s+external images are broken(?:\s+\d+\s+\d+)?", "External images are broken"),
        (
            r"(\d+)\s+links on HTTPS pages lead to HTTP page(?:\s+\d+\s+\d+)?",
            "Links on HTTPS pages lead to HTTP page",
        ),
        (
            r"(\d+)\s+pages don't have enough text within (?:the )?title tags(?:\s+\d+\s+\d+)?",
            "Pages don't have enough text within title tags",
        ),
        (
            r"(\d+)\s+pages have too much text within (?:the )?title tags(?:\s+\d+\s+\d+)?",
            "Pages have too much text within title tags",
        ),
        (r"(\d+)\s+pages don't have an h1 heading(?:\s+\d+\s+\d+)?", "Pages don't have an h1 heading"),
        (
            r"(\d+)\s+pages have duplicate H1 and title tags(?:\s+\d+\s+\d+)?",
            "Pages have duplicate H1 and title tags",
        ),
        (r"(\d+)\s+pages don't have meta descriptions(?:\s+\d+\s+\d+)?", "Pages don't have meta descriptions"),
        (r"(\d+)\s+pages have too many on-page links(?:\s+\d+\s+\d+)?", "Pages have too many on-page links"),
        (r"(\d+)\s+URLs with a temporary redirect(?:\s+\d+\s+\d+)?", "URLs with a temporary redirect"),
        (r"(\d+)\s+images don't have alt attributes(?:\s+\d+\s+\d+)?", "Images don't have alt attributes"),
        (r"(\d+)\s+pages have low text-HTML ratio(?:\s+\d+\s+\d+)?", "Pages have low text-HTML ratio"),
        (
            r"(\d+)\s+pages have too many parameters in their URLs(?:\s+\d+\s+\d+)?",
            "Pages have too many parameters in their URLs",
        ),
        (
            r"(\d+)\s+pages have no hreflang and lang attributes(?:\s+\d+\s+\d+)?",
            "Pages have no hreflang and lang attributes",
        ),
        (
            r"(\d+)\s+pages don't have character encoding declared(?:\s+\d+\s+\d+)?",
            "Pages don't have character encoding declared",
        ),
        (r"(\d+)\s+pages don't have doctype declared(?:\s+\d+\s+\d+)?", "Pages don't have doctype declared"),
        (r"(\d+)\s+pages have a low word count(?:\s+\d+\s+\d+)?", "Pages have a low word count"),
        (
            r"(\d+)\s+pages have incompatible plugin content(?:\s+\d+\s+\d+)?",
            "Pages have incompatible plugin content",
        ),
        (r"(\d+)\s+pages contain frames(?:\s+\d+\s+\d+)?", "Pages contain frames"),
        (r"(\d+)\s+pages have underscores in the URL(?:\s+\d+\s+\d+)?", "Pages have underscores in the URL"),
        (
            r"(\d+)\s+outgoing internal links contain nofollow attribute(?:\s+\d+\s+\d+)?",
            "Outgoing internal links contain nofollow attribute",
        ),
        (r"Sitemap\.xml not indicated in robots\.txt(?:\s+\d+\s+\d+)?", "Sitemap.xml not indicated in robots.txt"),
        (r"Sitemap\.xml not found(?:\s+\d+\s+\d+)?", "Sitemap.xml not found"),
        (
            r"Homepage does not use HTTPS encryption(?:\s+\d+\s+\d+)?",
            "Homepage does not use HTTPS encryption",
        ),
        (r"(\d+)\s+subdomains don't support SNI(?:\s+\d+\s+\d+)?", "Subdomains don't support SNI"),
        (
            r"(\d+)\s+HTTP URLs in sitemap\.xml for HTTPS site(?:\s+\d+\s+\d+)?",
            "HTTP URLs in sitemap.xml for HTTPS site",
        ),
        (r"(\d+)\s+Uncompressed pages(?:\s+\d+\s+\d+)?", "Uncompressed pages"),
        (
            r"(\d+)\s+Issues with blocked internal resources in robots\.txt(?:\s+\d+\s+\d+)?",
            "Issues with blocked internal resources in robots.txt",
        ),
        (
            r"(\d+)\s+Issues with uncompressed JavaScript and CSS files(?:\s+\d+\s+\d+)?",
            "Issues with uncompressed JavaScript and CSS files",
        ),
        (
            r"(\d+)\s+Issues with uncached JavaScript and CSS files(?:\s+\d+\s+\d+)?",
            "Issues with uncached JavaScript and CSS files",
        ),
        (
            r"(\d+)\s+Pages have JS/CSS total size too large(?:\s+\d+\s+\d+)?",
            "Pages have JS/CSS total size too large",
        ),
        (
            r"(\d+)\s+Pages use too many JavaScript and CSS files(?:\s+\d+\s+\d+)?",
            "Pages use too many JavaScript and CSS files",
        ),
        (
            r"(\d+)\s+Issues with unminified JavaScript and CSS files(?:\s+\d+\s+\d+)?",
            "Issues with unminified JavaScript and CSS files",
        ),
        (r"(\d+)\s+Link URLs are too long(?:\s+\d+\s+\d+)?", "Link URLs are too long"),
        (r"(\d+)\s+pages have more than one H1 tag(?:\s+\d+\s+\d+)?", "Pages have more than one H1 tag"),
        (r"Llms\.txt not found(?:\s+\d+\s+\d+)?", "Llms.txt not found"),
        (r"(\d+)\s+pages are blocked from crawling(?:\s+\d+\s+\d+)?", "Pages are blocked from crawling"),
        (
            r"(\d+)\s+Page URLs are longer than 200 characters(?:\s+\d+\s+\d+)?",
            "Page URLs are longer than 200 characters",
        ),
        (
            r"(\d+)\s+outgoing external links contain nofollow attributes(?:\s+\d+\s+\d+)?",
            "Outgoing external links contain nofollow attributes",
        ),
        (r"Robots\.txt not found(?:\s+\d+\s+\d+)?", "Robots.txt not found"),
        (
            r"(\d+)\s+pages have hreflang language mismatch issues(?:\s+\d+\s+\d+)?",
            "Pages have hreflang language mismatch issues",
        ),
        (r"(\d+)\s+subdomains don't support HSTS(?:\s+\d+\s+\d+)?", "Subdomains don't support HSTS"),
        (r"(\d+)\s+Orphaned pages in Google Analytics(?:\s+\d+\s+\d+)?", "Orphaned pages in Google Analytics"),
        (r"(\d+)\s+Orphaned pages in sitemaps(?:\s+\d+\s+\d+)?", "Orphaned pages in sitemaps"),
        (
            r"(\d+)\s+Pages blocked by X-Robots-Tag: noindex HTTP header(?:\s+\d+\s+\d+)?",
            "Pages blocked by X-Robots-Tag: noindex HTTP header",
        ),
        (
            r"(\d+)\s+Issues with blocked external resources in robots\.txt(?:\s+\d+\s+\d+)?",
            "Issues with blocked external resources in robots.txt",
        ),
        (
            r"(\d+)\s+Issues with broken external JavaScript and CSS files(?:\s+\d+\s+\d+)?",
            "Issues with broken external JavaScript and CSS files",
        ),
        (
            r"(\d+)\s+Pages need more than 3 clicks to be reached(?:\s+\d+\s+\d+)?",
            "Pages need more than 3 clicks to be reached",
        ),
        (
            r"(\d+)\s+Pages have only one incoming internal link(?:\s+\d+\s+\d+)?",
            "Pages have only one incoming internal link",
        ),
        (r"(\d+)\s+URLs with a permanent redirect(?:\s+\d+\s+\d+)?", "URLs with a permanent redirect"),
        (r"(\d+)\s+Resources are formatted as page link(?:\s+\d+\s+\d+)?", "Resources are formatted as page link"),
        (r"(\d+)\s+Links on this page have no anchor text(?:\s+\d+\s+\d+)?", "Links on this page have no anchor text"),
        (
            r"(\d+)\s+Links have non-descriptive anchor text(?:\s+\d+\s+\d+)?",
            "Links have non-descriptive anchor text",
        ),
        (
            r"(\d+)\s+Links to external pages returned 403 HTTP status(?:\s+\d+\s+\d+)?",
            "Links to external pages returned 403 HTTP status",
        ),
        (r"Llms\.txt has formatting issues(?:\s+\d+\s+\d+)?", "Llms.txt has formatting issues"),
        (r"(\d+)\s+Pages contain too much content(?:\s+\d+\s+\d+)?", "Pages contain too much content"),
        (r"(\d+)\s+Pages have outdated content(?:\s+\d+\s+\d+)?", "Pages have outdated content"),
        (r"(\d+)\s+Pages have low semantic HTML usage(?:\s+\d+\s+\d+)?", "Pages have low semantic HTML usage"),
        (r"(\d+)\s+Pages require content optimization(?:\s+\d+\s+\d+)?", "Pages require content optimization"),
    ]
    for pat, name in patterns:
        m = re.search(pat, text, flags=re.I)
        if m:
            val = m.group(1) if m.lastindex else "0"
            out[name] = f"{val} issue(s)" if val != "0" else "0 (passing)"
    # Site health summary (Semrush % line or executive-summary badge)
    badge = _parse_score_badge(text, "Site Health")
    if badge:
        out["__site_health__"] = f"{badge}%"
    else:
        m = re.search(r"Site Health\s*\n?\s*(\d+)%", text)
        if m:
            out["__site_health__"] = f"{m.group(1)}%"
    m = re.search(r"Crawled Pages:\s*(\d+)", text)
    if m:
        out["__crawled_pages__"] = m.group(1)
    if "internal link distribution" in text.lower():
        out["Internal Link Distribution"] = "Present in generated PDF"
    return out


def _parse_session_duration(text: str) -> str | None:
    """Extract session duration KPI; PDF text may wrap the label across lines."""
    duration = r"(\d+m\s*\d+s)"
    patterns = [
        rf"Average Session Duration\s*\n?\s*{duration}",
        rf"Average Session\s*\n?\s*Duration\s*\n?\s*{duration}",
        rf"Avg\.?\s*Session\s*\n?\s*Duration\s*\n?\s*{duration}",
    ]
    for pat in patterns:
        m = re.search(pat, text, flags=re.I)
        if m:
            return m.group(1).strip()
    return None


def _has_bounce_engagement_chart_section(text: str) -> bool:
    normalized = re.sub(r"\s+", " ", text.lower())
    return "bounce rate & average engagement time" in normalized


def _parse_baseline_values(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    seo_score = _parse_score_badge(text, "SEO score")
    if seo_score:
        out["SEO score (summary)"] = f"{seo_score}/100"
    kpis = {
        # PDF extract often wraps labels: "Engagement\nRate\n28.6%"
        "Engagement Rate": r"Engagement\s*\n?\s*Rate\s*\n?\s*([\d.]+%)",
        "Total Users": r"Total Users\s*\n?\s*([\d.]+K?)",
        "New Users": r"New Users\s*\n?\s*([\d.]+K?)",
        "Bounce Rate": r"Bounce Rate\s*\n?\s*([\d.]+%)",
    }
    for name, pat in kpis.items():
        m = re.search(pat, text)
        if m:
            out[name] = m.group(1).strip()
    # Prefer Overview KPI block over channel-table headers that reuse the same labels.
    overview_block = re.search(
        r"Overview\s*\nEngagement\s*\n?\s*Rate\s*\n?\s*([\d.]+%)\s*\nTotal Users",
        text,
        flags=re.I,
    )
    if overview_block:
        out["Engagement Rate"] = overview_block.group(1).strip()
    duration = _parse_session_duration(text)
    if duration:
        out["Average Session Duration"] = duration
    flags = {
        "Clicks by Device (Mobile/Desktop/Tablet)": "Clicks: Device",
        "Clicks by Country": "Clicks: Country",
        "Organic traffic trend (top pages traffic %)": "Organic traffic trend",
        "Traffic by source (organic/direct/referral)": "Monthly total traffic",
        "Session source breakdown (google/bing/yahoo/etc.)": "Session Source",
        "Organic Social traffic": "Organic Social",
        "Session primary channel group": "Session primary channel group",
        "Top ranking keywords (CTR, position, clicks, impressions)": "Top Keywords",
        "Pages per session": "Pages per session",
        "Mobile vs Desktop traffic split": "Mobile vs Desktop",
        "LCP (Core Web Vitals)": "LCP",
        "CLS (Core Web Vitals)": "CLS",
        "INP (Core Web Vitals)": "INP",
        "Page load speed - Desktop": "Page load speed - Desktop",
        "Page load speed - Mobile": "Page load speed - Mobile",
        "Form submissions by type": "Form submissions",
        "Top exit pages": "Top exit pages",
    }
    for name, needle in flags.items():
        if needle.lower() in text.lower():
            out[name] = "Present in reference PDF"
    if _has_bounce_engagement_chart_section(text):
        out["Bounce rate & Average engagement time (charts)"] = "Present (chart section)"
    return out


def _parse_score_badge(text: str, label: str) -> str | None:
    """Parse executive-summary badge scores like 'Site Health\\nC\\n73/100'."""
    m = re.search(
        rf"{re.escape(label)}\s*\n?\s*[A-F]\s*\n?\s*(\d+)/100",
        text,
        flags=re.I,
    )
    return m.group(1) if m else None


def _parse_ai_overview(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    site = _parse_score_badge(text, "Site Health")
    if site:
        out["Site Health score (percentage)"] = site
    ai = _parse_score_badge(text, "AI Search Health")
    if ai:
        out["AI Search Health score (percentage)"] = ai
    for label, pat in [
        ("Site Health score (percentage)", r"Site Health\s*\n?\s*(\d+)%"),
        ("AI Search Health score (percentage)", r"AI Search Health\s*\n?\s*(\d+)%"),
        ("Crawled pages stats (Blocked/Redirect/Broken/Healthy)", r"Total\s+100%\s+(\d+)"),
        (
            "Crawled pages stats (Blocked/Redirect/Broken/Healthy)",
            r"crawled=(\d+)",
        ),
        ("Pages blocked from AI search (aggregate %)", r"Blocked\s*\n?\s*([\d.]+%)"),
    ]:
        m = re.search(pat, text)
        if m:
            out[label] = m.group(1)
    bots = [
        ("ChatGPT-User bot blocking", r"ChatGPT.?User"),
        ("OAI-SearchBot bot blocking", r"OAI.?SearchBot"),
        ("Googlebot blocking", r"Googlebot"),
        ("Google-Extended bot blocking", r"Google-Extended"),
        ("PerplexityBot bot blocking", r"PerplexityBot"),
        ("Perplexity-User bot blocking", r"Perplexity-User"),
        ("Claude-User bot blocking", r"Claude-User"),
        ("Claude-SearchBot bot blocking", r"Claude-SearchBot"),
    ]
    for name, pat in bots:
        if re.search(pat, text):
            out[name] = "Listed in PDF"
    if "Top Issues" in text:
        if "All good" in text:
            out["Top Issues list (Errors/Warnings dashboard)"] = "No issues"
        else:
            out["Top Issues list (Errors/Warnings dashboard)"] = "Issues listed"
    return out


def _baseline_generated(text: str, manual: dict[str, str]) -> dict[str, str]:
    out = _parse_baseline_values(text)
    for name in BASELINE_PARAM_NAMES:
        if name in manual:
            continue
        if name not in out:
            if name.startswith("LCP") or name.startswith("CLS") or name.startswith("INP"):
                if "LCP" in text or "CLS" in text or "INP" in text:
                    out[name] = "Present in generated PDF"
            elif name in ("Page load speed - Desktop", "Page load speed - Mobile"):
                if "load speed" in text.lower() or "Lighthouse" in text:
                    out[name] = "Derived from PSI metrics"
            elif name == "Bounce rate & Average engagement time (charts)":
                if _has_bounce_engagement_chart_section(text):
                    out[name] = "Present (chart section)"
    # Re-label reference-only phrasing for generated column
    for key, val in list(out.items()):
        if val == "Present in reference PDF":
            out[key] = "Present in generated PDF"
    return out


BASELINE_PARAM_NAMES = [p.name for p in BASELINE_PARAMS]
SITE_AUDIT_PARAM_NAMES = [p.name for p in SITE_AUDIT_FULL_PARAMS]
AI_PARAM_NAMES = [p.name for p in AI_SEARCH_OVERVIEW_PARAMS]


def _catalog_lookup(kind: str) -> list[RefParameter]:
    return CATALOG_BY_PDF[kind]


def _is_gen_calculated(gen: str) -> bool:
    """True when the generated PDF includes a calculated value for this parameter."""
    return gen not in (
        "Manual (not calculated)",
        "Not shown in generated PDF",
        "Not listed in generated PDF body",
    )


def _why_not_calculated(
    entry: RefParameter,
    ref: str,
    gen: str,
    manual: dict[str, str],
) -> str:
    """Explain why SEO GEO Auditor did not calculate a parameter Semrush reports."""
    if _is_gen_calculated(gen):
        return "—"
    if entry.name in manual:
        return manual[entry.name]
    return entry.manual_reason


def _compare_kind(kind: str, ref_text: str, gen_text: str) -> list[ParamRow]:
    catalog = _catalog_lookup(kind)
    catalog_names = [e.name for e in catalog]
    manual = _parse_manual_appendix(gen_text, catalog_names)
    rows: list[ParamRow] = []

    if kind == "performance_baseline":
        ref_vals = _parse_baseline_values(ref_text)
        gen_vals = _baseline_generated(gen_text, manual)
        for entry in _catalog_lookup(kind):
            ref = ref_vals.get(entry.name, "Not found in reference PDF text")
            if entry.name in manual:
                gen = "Manual (not calculated)"
            elif entry.name in gen_vals:
                gen = gen_vals[entry.name]
            else:
                gen = "Not shown in generated PDF"
            why = _why_not_calculated(entry, ref, gen, manual)
            rows.append(ParamRow(entry.name, ref, gen, why))

    elif kind == "site_audit_full":
        ref_issues = _parse_site_audit_issues(ref_text)
        gen_issues = _parse_site_audit_issues(gen_text)
        ref_health = ref_issues.get("__site_health__", "—")
        gen_health = gen_issues.get("__site_health__", "—")
        ref_crawled = ref_issues.get("__crawled_pages__", "—")
        gen_crawled = gen_issues.get("__crawled_pages__", "—")

        for entry in _catalog_lookup(kind):
            ref = ref_issues.get(entry.name, "0 (passing) in reference")
            if entry.name in manual:
                gen = "Manual (not calculated)"
            elif entry.name in gen_issues:
                gen = gen_issues[entry.name]
            else:
                gen = "Not listed in generated PDF body"
            why = _why_not_calculated(entry, ref, gen, manual)
            rows.append(ParamRow(entry.name, ref, gen, why))

        rows.insert(
            0,
            ParamRow(
                "Site Health (summary)",
                ref_health,
                gen_health,
                "—" if gen_health != "—" else "Derived from SEO report score",
            ),
        )
        rows.insert(
            1,
            ParamRow(
                "Crawled pages (summary)",
                ref_crawled,
                gen_crawled,
                "—" if gen_crawled != "—" else "Shallow crawl count from SEO GEO Auditor",
            ),
        )

    else:  # ai_search_overview
        ref_vals = _parse_ai_overview(ref_text)
        gen_vals = _parse_ai_overview(gen_text)
        for entry in _catalog_lookup(kind):
            ref = ref_vals.get(entry.name, "Not extracted from reference")
            gen_val = gen_vals.get(entry.name)
            if gen_val:
                gen = gen_val
            elif entry.name in manual:
                gen = "Manual (not calculated)"
            else:
                gen = "Not shown in generated PDF"
            why = _why_not_calculated(entry, ref, gen, manual)
            rows.append(ParamRow(entry.name, ref, gen, why))

    return rows


def _para(text: str) -> str:
    return escape(text or "").replace("\n", "<br/>")


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "title",
            parent=base["Heading1"],
            fontSize=16,
            leading=20,
            textColor=colors.HexColor("#1a1a2e"),
            spaceAfter=8,
        ),
        "h2": ParagraphStyle(
            "h2",
            parent=base["Heading2"],
            fontSize=12,
            leading=15,
            textColor=colors.HexColor("#2563EB"),
            spaceBefore=10,
            spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "body",
            parent=base["Normal"],
            fontSize=9,
            leading=11,
            textColor=colors.HexColor("#333333"),
        ),
        "cell": ParagraphStyle(
            "cell",
            parent=base["Normal"],
            fontSize=7,
            leading=9,
            alignment=TA_LEFT,
        ),
        "meta": ParagraphStyle(
            "meta",
            parent=base["Normal"],
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#666666"),
            spaceAfter=6,
        ),
    }


def _summary_stats(rows: list[ParamRow]) -> tuple[int, int, int]:
    calc = sum(1 for r in rows if _is_gen_calculated(r.generated))
    manual = sum(1 for r in rows if not _is_gen_calculated(r.generated))
    return len(rows), calc, manual


def build_comparison_pdf(
    all_rows: dict[str, list[ParamRow]],
    gen_files: dict[str, Path],
) -> bytes:
    st = _styles()
    story: list = []
    story.append(Paragraph("SEO GEO Auditor — PDF Parameter Comparison", st["title"]))
    story.append(
        Paragraph(
            _para(
                f"Generated on {date.today():%B %d, %Y}. "
                "Compares reference PDFs (optiorx.com baseline / site audit exports) "
                "with SEO GEO Auditor outputs (heuristicsaisolutions.com) saved in the Comparison folder."
            ),
            st["meta"],
        )
    )

    for kind in ("performance_baseline", "site_audit_full", "ai_search_overview"):
        rows = all_rows[kind]
        total, calculated, manual = _summary_stats(rows)
        story.append(Paragraph(PDF_TITLES[kind], st["h2"]))
        story.append(
            Paragraph(
                _para(
                    f"Reference: {REF_FILES[kind].name} · "
                    f"Generated: {gen_files[kind].name} · "
                    f"{total} parameters · {calculated} calculated · {manual} not calculated"
                ),
                st["meta"],
            )
        )
        col_w = [USABLE * 0.22, USABLE * 0.18, USABLE * 0.18, USABLE * 0.42]
        data = [
            [
                Paragraph("<b>Parameter</b>", st["cell"]),
                Paragraph("<b>Reference PDF</b>", st["cell"]),
                Paragraph("<b>Generated PDF</b>", st["cell"]),
                Paragraph("<b>Why Not Calculated</b>", st["cell"]),
            ]
        ]
        for row in rows:
            data.append(
                [
                    Paragraph(_para(row.parameter), st["cell"]),
                    Paragraph(_para(row.reference), st["cell"]),
                    Paragraph(_para(row.generated), st["cell"]),
                    Paragraph(_para(row.why_not_calculated), st["cell"]),
                ]
            )
        table = Table(data, colWidths=col_w, repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EEF2FF")),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CBD5E1")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        story.append(table)
        story.append(PageBreak())

    buffer = BytesIO()
    doc = BaseDocTemplate(
        buffer,
        pagesize=PAGE_SIZE,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN,
        bottomMargin=MARGIN,
        title="PDF Parameter Comparison",
    )
    frame = Frame(MARGIN, MARGIN, USABLE, PAGE_SIZE[1] - 2 * MARGIN, id="main")
    doc.addPageTemplates([PageTemplate(id="main", frames=[frame])])
    doc.build(story)
    return buffer.getvalue()


def main() -> None:
    gen_files = _gen_files()
    missing = [p for p in list(REF_FILES.values()) + list(gen_files.values()) if not p.exists()]
    if missing:
        raise SystemExit("Missing PDF(s):\n" + "\n".join(str(p) for p in missing))

    all_rows: dict[str, list[ParamRow]] = {}
    for kind in REF_FILES:
        ref_text = _read_pdf_text(REF_FILES[kind])
        gen_text = _read_pdf_text(gen_files[kind])
        all_rows[kind] = _compare_kind(kind, ref_text, gen_text)

    out_path = OUT_DIR / f"PDF-Parameter-Comparison-{date.today():%Y-%m-%d}.pdf"
    out_path.write_bytes(build_comparison_pdf(all_rows, gen_files))
    print(f"Wrote {out_path}")

    for kind, rows in all_rows.items():
        total, calculated, manual = _summary_stats(rows)
        print(f"\n{PDF_TITLES[kind]}")
        print(f"  Total: {total} | Calculated: {calculated} | Not calculated: {manual}")
        not_calc = [r for r in rows if not _is_gen_calculated(r.generated)]
        for r in not_calc[:8]:
            print(f"  - {r.parameter}: {r.why_not_calculated[:80]}...")
        if len(not_calc) > 8:
            print(f"  ... and {len(not_calc) - 8} more")


if __name__ == "__main__":
    main()
