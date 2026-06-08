"""Build a downloadable PDF for a single SEO or GEO report."""

from __future__ import annotations  # Forward references for typing

from io import BytesIO  # In-memory PDF buffer
from xml.sax.saxutils import escape  # Escape text for ReportLab Paragraph markup

from reportlab.lib import colors  # Table styling colours
from reportlab.lib.enums import TA_LEFT  # Paragraph alignment
from reportlab.lib.pagesizes import letter  # US Letter page size
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet  # Text styles
from reportlab.lib.units import inch  # Inch helper
from reportlab.platypus import (  # PDF building blocks
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.models import Report  # The report payload to render


def build_report_pdf(
    report: Report,
    *,
    final_url: str,
    duration_seconds: float = 0.0,
    connected: bool = False,
) -> bytes:
    """Render `report` as a PDF and return the raw bytes."""
    buffer = BytesIO()  # Write the PDF into memory
    doc = SimpleDocTemplate(  # Document with standard margins
        buffer,
        pagesize=letter,
        leftMargin=0.6 * inch,
        rightMargin=0.6 * inch,
        topMargin=0.6 * inch,
        bottomMargin=0.6 * inch,
        title=f"{report.kind.upper()} Audit Report",
    )

    styles = getSampleStyleSheet()  # Base styles from ReportLab
    title_style = ParagraphStyle(  # Main document title
        "AuditTitle",
        parent=styles["Heading1"],
        fontSize=18,
        spaceAfter=6,
        textColor=colors.HexColor("#1a1a2e"),
    )
    meta_style = ParagraphStyle(  # URL / run metadata
        "AuditMeta",
        parent=styles["Normal"],
        fontSize=9,
        textColor=colors.HexColor("#555555"),
        spaceAfter=4,
    )
    heading_style = ParagraphStyle(  # Section headings
        "SectionHeading",
        parent=styles["Heading2"],
        fontSize=13,
        spaceBefore=10,
        spaceAfter=6,
        textColor=colors.HexColor("#1a1a2e"),
    )
    body_style = ParagraphStyle(  # Narrative body text
        "Body",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        spaceAfter=8,
    )
    cell_style = ParagraphStyle(  # Table cell text (wraps long strings)
        "Cell",
        parent=styles["Normal"],
        fontSize=8,
        leading=10,
        alignment=TA_LEFT,
    )

    kind_label = "SEO" if report.kind == "seo" else "GEO"  # Human-readable report type
    story: list = []  # Flowables appended to the document

    # --- Cover header ---
    story.append(Paragraph(f"{kind_label} Audit Report", title_style))
    story.append(Paragraph(f"URL: {_para(final_url)}", meta_style))
    story.append(
        Paragraph(
            f"Score: {report.score}/100 · Grade: {report.grade} · "
            f"Duration: {duration_seconds}s · "
            f"{'Connected (GA4/GSC)' if connected else 'Public crawl'}",
            meta_style,
        )
    )
    if report.manual_count:
        story.append(
            Paragraph(
                f"{report.manual_count} parameter(s) marked Manual/Not Measured and excluded from the score.",
                meta_style,
            )
        )
    story.append(Spacer(1, 0.15 * inch))

    # --- Narrative summary ---
    if report.summary:
        story.append(Paragraph("Summary &amp; Top Fixes", heading_style))
        story.append(Paragraph(_para(report.summary), body_style))

    # --- Report-specific panel ---
    panel_lines = _panel_lines(report)  # CWV or citation bullets
    if panel_lines:
        panel_title = (
            "Core Web Vitals (PageSpeed Insights · mobile)"
            if report.kind == "seo"
            else "AI Citation Appearance"
        )
        story.append(Paragraph(panel_title, heading_style))
        for line in panel_lines:
            story.append(Paragraph(f"• {_para(line)}", body_style))

    # --- Category tables ---
    for category in report.categories:
        story.append(
            Paragraph(
                f"{category.title} — {category.score}/100",
                heading_style,
            )
        )
        table_data = [  # Header row
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
                    f"{_para(param.name)}<br/><font size='6' color='#666666'>"
                    f"{_para(param.method)}{(' · ' + _para(param.confidence.value)) if param.confidence else ''}"
                    f"</font>",
                    cell_style,
                )
            rec = param.recommendation or param.detail or ""  # Prefer recommendation
            if param.priority and param.rating.value not in ("Meeting", "Manual", "Not Measured"):
                rec = f"[{param.priority.value}] {rec}"  # Prefix priority when actionable
            table_data.append(
                [
                    name_cell,
                    Paragraph(_para(param.what_to_check), cell_style),
                    Paragraph(_para(param.rating.value), cell_style),
                    Paragraph(_para(rec), cell_style),
                ]
            )

        table = Table(  # Full-width parameter table
            table_data,
            colWidths=[1.35 * inch, 1.55 * inch, 0.85 * inch, 2.75 * inch],
            repeatRows=1,  # Repeat header on page breaks
        )
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef1f8")),  # Header row
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#1a1a2e")),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 8),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cccccc")),  # Cell borders
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        story.append(table)
        story.append(Spacer(1, 0.1 * inch))

    doc.build(story)  # Render all flowables into the buffer
    return buffer.getvalue()  # Return PDF bytes


def _para(text: str) -> str:
    """Escape plain text for ReportLab Paragraph markup and preserve newlines."""
    return escape(text or "").replace("\n", "<br/>")


def _panel_lines(report: Report) -> list[str]:
    """Turn the report panel dict into human-readable bullet strings."""
    panel = report.panel or {}  # CWV or citation data
    if not panel:
        return []  # Nothing to show

    lines: list[str] = []
    if report.kind == "seo":  # Core Web Vitals panel
        for label, key, unit in (
            ("LCP", "lcp_ms", "ms"),
            ("CLS", "cls", ""),
            ("INP", "inp_ms", "ms"),
            ("TTFB", "ttfb_ms", "ms"),
        ):
            value = panel.get(key)
            if value is not None:
                lines.append(f"{label}: {value}{unit}")
        lighthouse = panel.get("lighthouse") or {}  # Lighthouse category scores
        if lighthouse:
            lh = ", ".join(f"{cat}: {score}" for cat, score in lighthouse.items())
            lines.append(f"Lighthouse — {lh}")
    else:  # GEO citation panel
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
                lines.append(f"{label}: " + "; ".join(sources[:8]))  # Cap list length in PDF
    return lines
