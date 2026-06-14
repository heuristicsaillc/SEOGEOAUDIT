"""Build a downloadable PDF for a single SEO or GEO report."""

from __future__ import annotations

from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.models import Report, Rating

BRAND = colors.HexColor("#2563EB")
TITLE_COLOR = colors.HexColor("#1a1a2e")
MUTED = colors.HexColor("#64748B")
GRID = colors.HexColor("#E2E8F0")
HEADER_BG = colors.HexColor("#EEF2FF")


def build_report_pdf(
    report: Report,
    *,
    final_url: str,
    duration_seconds: float = 0.0,
    connected: bool = False,
) -> bytes:
    """Render `report` as a PDF and return the raw bytes."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=0.65 * inch,
        rightMargin=0.65 * inch,
        topMargin=0.65 * inch,
        bottomMargin=0.65 * inch,
        title=f"{report.kind.upper()} Audit Report",
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "AuditTitle",
        parent=styles["Heading1"],
        fontSize=20,
        spaceAfter=4,
        textColor=TITLE_COLOR,
    )
    meta_style = ParagraphStyle(
        "AuditMeta",
        parent=styles["Normal"],
        fontSize=9,
        textColor=MUTED,
        spaceAfter=4,
    )
    heading_style = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        fontSize=13,
        spaceBefore=12,
        spaceAfter=6,
        textColor=BRAND,
    )
    body_style = ParagraphStyle(
        "Body",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        spaceAfter=8,
        textColor=TITLE_COLOR,
    )
    cell_style = ParagraphStyle(
        "Cell",
        parent=styles["Normal"],
        fontSize=8,
        leading=10,
        alignment=TA_LEFT,
        textColor=TITLE_COLOR,
    )

    kind_label = "SEO" if report.kind == "seo" else "GEO"
    story: list = []

    story.append(Paragraph(f"{kind_label} Audit Report", title_style))
    story.append(Paragraph(f"Prepared for {_para(final_url)}", meta_style))
    story.append(
        Paragraph(
            f"Score: {report.score}/100 · Grade: {report.grade} · "
            f"Duration: {duration_seconds}s · "
            f"{'Connected (GA4/GSC)' if connected else 'Public crawl'}",
            meta_style,
        )
    )
    story.append(Paragraph("Heuristics AI Solutions LLC · WWW.HEURISTICSAISOLUTIONS.COM", meta_style))
    story.append(Spacer(1, 0.12 * inch))

    action_items = _action_items(report)
    story.append(Paragraph("Executive Summary", heading_style))
    if report.summary:
        story.append(Paragraph(_para(report.summary), body_style))
    if action_items:
        story.append(Spacer(1, 0.06 * inch))
        story.append(Paragraph("Priority issues &amp; recommended fixes", heading_style))
        table_data = [
            [
                Paragraph("<b>Issue</b>", cell_style),
                Paragraph("<b>Severity</b>", cell_style),
                Paragraph("<b>How to fix on your website</b>", cell_style),
            ]
        ]
        for issue, severity, fix in action_items:
            table_data.append(
                [
                    Paragraph(_para(issue), cell_style),
                    Paragraph(_para(severity), cell_style),
                    Paragraph(_para(fix), cell_style),
                ]
            )
        table = Table(table_data, colWidths=[1.55 * inch, 0.85 * inch, 3.6 * inch], repeatRows=1)
        table.setStyle(_table_style())
        story.append(table)
    elif not report.summary:
        story.append(
            Paragraph(
                _para("No critical issues were identified. See the detailed parameter tables below."),
                body_style,
            )
        )
    story.append(Spacer(1, 0.1 * inch))

    panel_lines = _panel_lines(report)
    if panel_lines:
        panel_title = (
            "Core Web Vitals (PageSpeed Insights · mobile)"
            if report.kind == "seo"
            else "AI Citation Appearance"
        )
        story.append(Paragraph(panel_title, heading_style))
        for line in panel_lines:
            story.append(Paragraph(f"• {_para(line)}", body_style))

    for category in report.categories:
        story.append(Paragraph(f"{category.title} — {category.score}/100", heading_style))
        table_data = [
            [
                Paragraph("<b>Parameter</b>", cell_style),
                Paragraph("<b>What to check</b>", cell_style),
                Paragraph("<b>Rating</b>", cell_style),
                Paragraph("<b>Recommendation / Detail</b>", cell_style),
            ]
        ]
        for param in category.parameters:
            name_cell = Paragraph(_para(param.name), cell_style)
            if param.method:
                name_cell = Paragraph(
                    f"{_para(param.name)}<br/><font size='6' color='#64748B'>"
                    f"{_para(param.method.value)}{(' · ' + _para(param.confidence.value)) if param.confidence else ''}"
                    f"</font>",
                    cell_style,
                )
            rec = param.recommendation or param.detail or ""
            if param.priority and param.rating.value not in ("Meeting", "Manual", "Not Measured"):
                rec = f"[{param.priority.value}] {rec}"
            table_data.append(
                [
                    name_cell,
                    Paragraph(_para(param.what_to_check), cell_style),
                    Paragraph(_para(param.rating.value), cell_style),
                    Paragraph(_para(rec), cell_style),
                ]
            )

        table = Table(
            table_data,
            colWidths=[1.35 * inch, 1.55 * inch, 0.85 * inch, 2.75 * inch],
            repeatRows=1,
        )
        table.setStyle(_table_style())
        story.append(table)
        story.append(Spacer(1, 0.1 * inch))

    doc.build(story)
    return buffer.getvalue()


def _table_style() -> TableStyle:
    return TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
            ("TEXTCOLOR", (0, 0), (-1, 0), TITLE_COLOR),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 8),
            ("GRID", (0, 0), (-1, -1), 0.25, GRID),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]
    )


def _action_items(report: Report, *, limit: int = 10) -> list[tuple[str, str, str]]:
    order = {Rating.NOT_MEETING: 0, Rating.PARTIAL: 1}
    candidates: list[tuple[int, str, str, str]] = []
    for category in report.categories:
        for param in category.parameters:
            if param.rating not in order:
                continue
            fix = param.recommendation or param.detail or param.what_to_check
            candidates.append((order[param.rating], param.name, param.rating.value, fix))
    candidates.sort(key=lambda item: item[0])
    return [(name, rating, fix) for _, name, rating, fix in candidates[:limit]]


def _para(text: str) -> str:
    return escape(text or "").replace("\n", "<br/>")


def _panel_lines(report: Report) -> list[str]:
    panel = report.panel or {}
    if not panel:
        return []

    lines: list[str] = []
    if report.kind == "seo":
        for label, key, unit in (
            ("LCP", "lcp_ms", "ms"),
            ("CLS", "cls", ""),
            ("INP", "inp_ms", "ms"),
            ("TTFB", "ttfb_ms", "ms"),
        ):
            value = panel.get(key)
            if value is not None:
                lines.append(f"{label}: {value}{unit}")
        lighthouse = panel.get("lighthouse") or {}
        if lighthouse:
            lh = ", ".join(f"{cat}: {score}" for cat, score in lighthouse.items())
            lines.append(f"Lighthouse — {lh}")
    else:
        if panel.get("query"):
            lines.append(f"Query tested: {panel['query']}")
        cited = panel.get("cited_by") or []
        lines.append(
            "Cited by: " + (", ".join(cited) if cited else "Not currently cited by tested engines")
        )
        for label, key in (
            ("Perplexity sources", "perplexity_sources"),
            ("Google AI Overview sources", "ai_overview_sources"),
        ):
            sources = panel.get(key) or []
            if sources:
                lines.append(f"{label}: " + "; ".join(sources[:8]))
    return lines
