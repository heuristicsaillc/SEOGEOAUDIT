"""Shared ReportLab layout primitives matching the three reference PDF styles."""

from __future__ import annotations

from datetime import date, timedelta
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch, mm
from io import BytesIO

from reportlab.platypus import Flowable, Image, Paragraph, Spacer, Table, TableStyle

from app.scoring import grade_for_score

PAGE_SIZE = A4
MARGIN = 18 * mm

HEURISTICS_ORANGE = colors.HexColor("#2563EB")
HEURISTICS_TEXT = colors.HexColor("#1A1A1A")
HEURISTICS_MUTED = colors.HexColor("#767676")
HEURISTICS_LINE = colors.HexColor("#E0E0E0")
BASELINE_TITLE = colors.HexColor("#1A1A1A")
BASELINE_MUTED = colors.HexColor("#5C5C5C")

HEURISTICS_BRAND = "HEURISTICS AI SOLUTIONS LLC"
HEURISTICS_WEB = "WWW.HEURISTICSAISOLUTIONS.COM"

SEVERITY_ERROR = colors.HexColor("#DC2626")
SEVERITY_WARNING = colors.HexColor("#EA580C")
SEVERITY_NOTICE = colors.HexColor("#CA8A04")

SCORE_GOOD = colors.HexColor("#2ECC71")
SCORE_WARN = colors.HexColor("#F1C40F")
SCORE_BAD = colors.HexColor("#E74C3C")
SCORE_WARN_TEXT = colors.HexColor("#222222")

HEADER_TEXT_TOP = 10 * mm
HEADER_TEXT_SECOND = 14 * mm
HEADER_RULE_Y = 19 * mm
CONTENT_TOP_MARGIN = 24 * mm
CONTENT_BOTTOM_MARGIN = 16 * mm


def para(text: str) -> str:
    return escape(text or "").replace("\n", "<br/>")


def styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "baseline_cover_title": ParagraphStyle(
            "baseline_cover_title",
            parent=base["Normal"],
            fontSize=28,
            leading=34,
            alignment=TA_CENTER,
            textColor=BASELINE_TITLE,
            spaceAfter=10,
        ),
        "baseline_cover_sub": ParagraphStyle(
            "baseline_cover_sub",
            parent=base["Normal"],
            fontSize=14,
            leading=18,
            alignment=TA_CENTER,
            textColor=BASELINE_MUTED,
            spaceAfter=8,
        ),
        "section_title": ParagraphStyle(
            "section_title",
            parent=base["Heading2"],
            fontSize=16,
            leading=20,
            textColor=BASELINE_TITLE,
            spaceBefore=6,
            spaceAfter=10,
        ),
        "subsection": ParagraphStyle(
            "subsection",
            parent=base["Heading3"],
            fontSize=12,
            leading=15,
            textColor=BASELINE_TITLE,
            spaceBefore=4,
            spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "body",
            parent=base["Normal"],
            fontSize=10,
            leading=13,
            textColor=BASELINE_TITLE,
            spaceAfter=6,
        ),
        "muted": ParagraphStyle(
            "muted",
            parent=base["Normal"],
            fontSize=9,
            leading=12,
            textColor=BASELINE_MUTED,
            spaceAfter=4,
        ),
        "cell": ParagraphStyle(
            "cell",
            parent=base["Normal"],
            fontSize=8,
            leading=10,
            alignment=TA_LEFT,
            textColor=BASELINE_TITLE,
        ),
        "cell_center": ParagraphStyle(
            "cell_center",
            parent=base["Normal"],
            fontSize=8,
            leading=10,
            alignment=TA_CENTER,
            textColor=BASELINE_TITLE,
        ),
        "kpi_label": ParagraphStyle(
            "kpi_label",
            parent=base["Normal"],
            fontSize=9,
            leading=11,
            alignment=TA_LEFT,
            textColor=BASELINE_MUTED,
        ),
        "kpi_value": ParagraphStyle(
            "kpi_value",
            parent=base["Normal"],
            fontSize=20,
            leading=24,
            alignment=TA_LEFT,
            textColor=BASELINE_TITLE,
        ),
        "audit_cover_title": ParagraphStyle(
            "audit_cover_title",
            parent=base["Normal"],
            fontSize=24,
            leading=30,
            alignment=TA_CENTER,
            textColor=HEURISTICS_TEXT,
            spaceAfter=12,
        ),
        "audit_cover_domain": ParagraphStyle(
            "audit_cover_domain",
            parent=base["Normal"],
            fontSize=14,
            leading=18,
            alignment=TA_CENTER,
            textColor=HEURISTICS_MUTED,
            spaceAfter=8,
        ),
        "audit_cover_sub": ParagraphStyle(
            "audit_cover_sub",
            parent=base["Normal"],
            fontSize=11,
            leading=14,
            alignment=TA_CENTER,
            textColor=HEURISTICS_MUTED,
            spaceAfter=6,
        ),
        "audit_h1": ParagraphStyle(
            "audit_h1",
            parent=base["Heading1"],
            fontSize=18,
            leading=22,
            textColor=HEURISTICS_TEXT,
            spaceAfter=8,
        ),
        "audit_h2": ParagraphStyle(
            "audit_h2",
            parent=base["Heading2"],
            fontSize=14,
            leading=18,
            textColor=HEURISTICS_ORANGE,
            spaceBefore=4,
            spaceAfter=6,
        ),
        "audit_h2_error": ParagraphStyle(
            "audit_h2_error",
            parent=base["Heading2"],
            fontSize=14,
            leading=18,
            textColor=SEVERITY_ERROR,
            spaceBefore=4,
            spaceAfter=6,
        ),
        "audit_h2_warning": ParagraphStyle(
            "audit_h2_warning",
            parent=base["Heading2"],
            fontSize=14,
            leading=18,
            textColor=SEVERITY_WARNING,
            spaceBefore=4,
            spaceAfter=6,
        ),
        "audit_h2_notice": ParagraphStyle(
            "audit_h2_notice",
            parent=base["Heading2"],
            fontSize=14,
            leading=18,
            textColor=SEVERITY_NOTICE,
            spaceBefore=4,
            spaceAfter=6,
        ),
        "audit_body": ParagraphStyle(
            "audit_body",
            parent=base["Normal"],
            fontSize=10,
            leading=13,
            textColor=HEURISTICS_TEXT,
            spaceAfter=4,
        ),
        "audit_issue": ParagraphStyle(
            "audit_issue",
            parent=base["Normal"],
            fontSize=9,
            leading=12,
            textColor=HEURISTICS_TEXT,
            spaceAfter=2,
        ),
        "audit_issue_error": ParagraphStyle(
            "audit_issue_error",
            parent=base["Normal"],
            fontSize=9,
            leading=12,
            textColor=SEVERITY_ERROR,
            spaceAfter=2,
        ),
        "audit_issue_warning": ParagraphStyle(
            "audit_issue_warning",
            parent=base["Normal"],
            fontSize=9,
            leading=12,
            textColor=SEVERITY_WARNING,
            spaceAfter=2,
        ),
        "cell_error": ParagraphStyle(
            "cell_error",
            parent=base["Normal"],
            fontSize=8,
            leading=10,
            alignment=TA_LEFT,
            textColor=SEVERITY_ERROR,
        ),
        "cell_warning": ParagraphStyle(
            "cell_warning",
            parent=base["Normal"],
            fontSize=8,
            leading=10,
            alignment=TA_LEFT,
            textColor=SEVERITY_WARNING,
        ),
        "cell_notice": ParagraphStyle(
            "cell_notice",
            parent=base["Normal"],
            fontSize=8,
            leading=10,
            alignment=TA_LEFT,
            textColor=SEVERITY_NOTICE,
        ),
        "cell_center_error": ParagraphStyle(
            "cell_center_error",
            parent=base["Normal"],
            fontSize=8,
            leading=10,
            alignment=TA_CENTER,
            textColor=SEVERITY_ERROR,
        ),
        "cell_center_warning": ParagraphStyle(
            "cell_center_warning",
            parent=base["Normal"],
            fontSize=8,
            leading=10,
            alignment=TA_CENTER,
            textColor=SEVERITY_WARNING,
        ),
        "bullet_item": ParagraphStyle(
            "bullet_item",
            parent=base["Normal"],
            fontSize=10,
            leading=14,
            textColor=BASELINE_TITLE,
            spaceAfter=8,
            leftIndent=14,
            bulletIndent=0,
        ),
        "baseline_cover_brand": ParagraphStyle(
            "baseline_cover_brand",
            parent=base["Normal"],
            fontSize=9,
            leading=12,
            alignment=TA_CENTER,
            textColor=BASELINE_MUTED,
            spaceAfter=4,
        ),
        "appendix_title": ParagraphStyle(
            "appendix_title",
            parent=base["Heading2"],
            fontSize=13,
            leading=16,
            textColor=BASELINE_TITLE,
            spaceBefore=14,
            spaceAfter=8,
        ),
        "summary_title": ParagraphStyle(
            "summary_title",
            parent=base["Heading1"],
            fontSize=18,
            leading=22,
            textColor=BASELINE_TITLE,
            spaceAfter=6,
        ),
        "summary_scores": ParagraphStyle(
            "summary_scores",
            parent=base["Normal"],
            fontSize=10,
            leading=13,
            textColor=HEURISTICS_ORANGE,
            spaceAfter=8,
        ),
    }


def section_spacer() -> Spacer:
    """Gap between major report sections (avoids forced page breaks)."""
    return Spacer(1, 0.22 * inch)


def subsection_spacer() -> Spacer:
    """Gap between subsections within a report page."""
    return Spacer(1, 0.18 * inch)


DEFAULT_BADGE_DIAMETER = 0.68 * inch
LARGE_BADGE_DIAMETER = 0.92 * inch


def _grade_fill_and_text(grade: str) -> tuple[colors.Color, colors.Color]:
    if grade in ("A", "B"):
        return SCORE_GOOD, colors.white
    if grade in ("C", "D"):
        return SCORE_WARN, SCORE_WARN_TEXT
    return SCORE_BAD, colors.white


class ScoreBadge(Flowable):
    """Circular grade + score badge matching the web UI score header."""

    def __init__(self, score: float, grade: str | None = None, *, diameter: float = DEFAULT_BADGE_DIAMETER):
        super().__init__()
        self.score = score
        self.grade = grade or grade_for_score(score)
        self.diameter = diameter
        self.width = diameter
        self.height = diameter
        scale = diameter / DEFAULT_BADGE_DIAMETER
        self.letter_pt = 22 * scale
        self.score_pt = 8 * scale

    def wrap(self, availWidth, availHeight):
        return self.width, self.height

    def draw(self):
        canvas = self.canv
        radius = self.diameter / 2
        fill, text_color = _grade_fill_and_text(self.grade)
        canvas.setFillColor(fill)
        canvas.circle(radius, radius, radius, fill=1, stroke=0)
        canvas.setFillColor(text_color)
        canvas.setFont("Helvetica-Bold", self.letter_pt)
        letter_w = canvas.stringWidth(self.grade, "Helvetica-Bold", self.letter_pt)
        canvas.drawString(radius - letter_w / 2, radius + 1, self.grade)
        canvas.setFont("Helvetica", self.score_pt)
        score_text = f"{int(round(self.score))}/100"
        score_w = canvas.stringWidth(score_text, "Helvetica", self.score_pt)
        canvas.drawString(radius - score_w / 2, radius - self.letter_pt * 0.55, score_text)


def score_badge_inline(
    label: str,
    score: float,
    st: dict,
    *,
    grade: str | None = None,
    diameter: float = LARGE_BADGE_DIAMETER,
) -> Table:
    """Label left-aligned beside a score badge (matches the web score header layout)."""
    badge = ScoreBadge(score, grade, diameter=diameter)
    label_para = Paragraph(f"<b>{para(label)}</b>", st["summary_scores"])
    table = Table(
        [[label_para, badge]],
        colWidths=[2.4 * inch, diameter],
        hAlign="LEFT",
    )
    table.setStyle(
        TableStyle(
            [
                ("ALIGN", (0, 0), (0, 0), "LEFT"),
                ("ALIGN", (1, 0), (1, 0), "LEFT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    return table


def score_badges_block(
    badges: list[tuple[str, float, str | None]],
    st: dict,
    *,
    diameter: float = LARGE_BADGE_DIAMETER,
) -> list:
    """One or more label-left score badges, stacked when multiple."""
    flow: list = []
    for index, (label, score, grade) in enumerate(badges):
        if index:
            flow.append(Spacer(1, 0.1 * inch))
        flow.append(score_badge_inline(label, score, st, grade=grade, diameter=diameter))
    return flow


def count_paragraph(value: str, severity: str | None, st: dict, *, center: bool = True) -> Paragraph:
    """Count cell — severity color only when the numeric value is greater than zero."""
    try:
        count = int(str(value).strip() or "0")
    except ValueError:
        count = 0
    if count <= 0 or not severity:
        style_key = "cell_center" if center else "cell"
        return Paragraph(para(str(value)), st[style_key])
    style_key = _severity_style_key(severity, center=center)
    return Paragraph(para(str(value)), st[style_key])


def _severity_style_key(severity: str, *, center: bool = False) -> str:
    normalized = (severity or "").strip().lower()
    if normalized in ("not meeting", "error", "errors"):
        return "cell_center_error" if center else "cell_error"
    if normalized in ("partial", "warning", "warnings"):
        return "cell_center_warning" if center else "cell_warning"
    if normalized in ("notice", "notices"):
        return "cell_notice"
    return "cell_center" if center else "cell"


def rating_paragraph(text: str, rating: str, st: dict, *, center: bool = False) -> Paragraph:
    style_key = _severity_style_key(rating, center=center)
    return Paragraph(para(text), st[style_key])


def issue_resolution_bullets(
    action_items: list[tuple[str, str, str]],
    st: dict,
) -> list:
    """Bulleted issue + resolution list for executive overview."""
    flow: list = []
    for issue, severity, fix in action_items:
        color = "#DC2626"
        if severity.lower() in ("partial", "warning", "warnings"):
            color = "#EA580C"
        elif severity.lower() in ("notice", "notices"):
            color = "#CA8A04"
        flow.append(
            Paragraph(
                f"<bullet>&bull;</bullet> "
                f'<font color="{color}"><b>{para(issue)}</b> ({para(severity)})</font><br/>'
                f"&nbsp;&nbsp;&nbsp;&nbsp;<b>Resolution:</b> {para(fix)}",
                st["bullet_item"],
            )
        )
    return flow


def date_range_label(days: int = 90) -> tuple[str, str]:
    """Return (range label, generated label) like the reference baseline PDF."""
    end = date.today()
    start = end - timedelta(days=days)
    return (
        f"{start.strftime('%b %d, %Y')} to {end.strftime('%b %d, %Y')}",
        end.strftime("Generated on %B %d, %Y"),
    )


def audit_generated_label(when: date | None = None) -> str:
    when = when or date.today()
    return when.strftime("Generated on %B %d, %Y")


class AuditPageMarker(Flowable):
    """Invisible flowable that marks a page as using the HeuristicsAI audit header/footer."""

    def __init__(self, domain: str):
        super().__init__()
        self.domain = domain
        self.width = 0
        self.height = 0

    def draw(self):
        self.canv._doctemplateAttr("audit_page", True)  # type: ignore[attr-defined]


def baseline_cover(st: dict, range_label: str, generated_label: str, *, domain: str = "") -> list:
    subtitle = f"Prepared for {domain}" if domain else "Client Performance Report"
    return [
        Spacer(1, 1.8 * inch),
        Paragraph("Performance Baseline", st["baseline_cover_title"]),
        Paragraph("Traffic, Engagement, SEO &amp; Web Vitals", st["baseline_cover_sub"]),
        Paragraph(para(subtitle), st["baseline_cover_sub"]),
        Paragraph(para(range_label), st["baseline_cover_sub"]),
        Paragraph(para(generated_label), st["baseline_cover_sub"]),
        Spacer(1, 0.3 * inch),
        Paragraph(para(f"{HEURISTICS_BRAND} · {HEURISTICS_WEB}"), st["baseline_cover_brand"]),
    ]


def audit_cover(st: dict, title: str, domain: str, generated_label: str) -> list:
    return [
        Spacer(1, 2.0 * inch),
        Paragraph(para(title), st["audit_cover_title"]),
        Paragraph(para(domain), st["audit_cover_domain"]),
        Paragraph(para("Prepared for client review"), st["audit_cover_sub"]),
        Paragraph(para(generated_label), st["audit_cover_sub"]),
        Spacer(1, 0.25 * inch),
        Paragraph(para(f"{HEURISTICS_BRAND} · {HEURISTICS_WEB}"), st["baseline_cover_brand"]),
    ]


def kpi_grid(items: list[tuple[str, str]], st: dict, cols: int = 3) -> Table:
    """Render KPI label/value pairs in a grid like the baseline Overview page."""
    cells: list = []
    row: list = []
    for label, value in items:
        row.append(
            [
                Paragraph(para(label), st["kpi_label"]),
                Paragraph(para(value), st["kpi_value"]),
            ]
        )
        if len(row) == cols:
            flat: list = []
            for pair in row:
                flat.extend(pair)
            cells.append(flat)
            row = []
    if row:
        while len(row) < cols:
            row.append([Paragraph("", st["kpi_label"]), Paragraph("", st["kpi_value"])])
        flat = []
        for pair in row:
            flat.extend(pair)
        cells.append(flat)

    col_w = (PAGE_SIZE[0] - 2 * MARGIN) / (cols * 2)
    table = Table(cells, colWidths=[col_w] * (cols * 2), hAlign="LEFT")
    border = colors.HexColor("#BFBFBF")
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, border),
                ("BOX", (0, 0), (-1, -1), 0.75, border),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return table


def data_table(
    headers: list[str],
    rows: list[list[str]],
    st: dict,
    *,
    col_widths: list[float] | None = None,
    center_cols: set[int] | None = None,
    rating_col: int | None = None,
) -> Table:
    center_cols = center_cols or set()
    usable = PAGE_SIZE[0] - 2 * MARGIN
    if not col_widths:
        col_widths = [usable / len(headers)] * len(headers)
    table_data = [
        [Paragraph(f"<b>{para(h)}</b>", st["cell"]) for h in headers],
    ]
    for row in rows:
        cells: list = []
        for idx, cell in enumerate(row):
            if rating_col is not None and idx == rating_col:
                cells.append(rating_paragraph(str(cell), str(cell), st, center=idx in center_cols))
            else:
                style_key = "cell_center" if idx in center_cols else "cell"
                cells.append(Paragraph(para(str(cell)), st[style_key]))
        table_data.append(cells)
    table = Table(table_data, colWidths=col_widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(_baseline_table_style())
    return table


def issue_counts_table(
    rows: list[tuple[str, int, str]],
    st: dict,
    *,
    col_widths: list[float] | None = None,
) -> Table:
    """Two-column label/count table; count is colored only when greater than zero."""
    col_widths = col_widths or [2.5 * inch, 1.0 * inch]
    table_data = [
        [
            Paragraph("<b></b>", st["cell"]),
            Paragraph("<b>Count</b>", st["cell_center"]),
        ]
    ]
    for label, count, severity in rows:
        table_data.append(
            [
                Paragraph(para(label), st["cell"]),
                count_paragraph(str(count), severity if count > 0 else None, st),
            ]
        )
    table = Table(table_data, colWidths=col_widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(_baseline_table_style())
    return table


def audit_issue_table(
    rows: list[tuple[str, str, str]],
    st: dict,
    *,
    severity: str = "error",
) -> Table:
    """HeuristicsAI audit issue list: description | count | delta."""
    issue_style = {
        "error": "audit_issue_error",
        "warning": "audit_issue_warning",
        "notice": "audit_issue",
    }.get(severity.lower(), "audit_issue")
    usable = PAGE_SIZE[0] - 2 * MARGIN
    table_data = [
        [
            Paragraph("<b>Issue</b>", st["cell"]),
            Paragraph("<b>New</b>", st["cell_center"]),
            Paragraph("<b>Fixed</b>", st["cell_center"]),
        ]
    ]
    for label, new_count, fixed_count in rows:
        try:
            new_n = int(str(new_count).strip() or "0")
        except ValueError:
            new_n = 0
        label_style = issue_style if new_n > 0 else "cell"
        table_data.append(
            [
                Paragraph(para(label), st[label_style]),
                count_paragraph(new_count, severity if new_n > 0 else None, st),
                count_paragraph(fixed_count, None, st),
            ]
        )
    table = Table(
        table_data,
        colWidths=[usable * 0.78, usable * 0.11, usable * 0.11],
        hAlign="LEFT",
    )
    table.setStyle(
        TableStyle(
            [
                ("LINEBELOW", (0, 0), (-1, 0), 0.5, HEURISTICS_LINE),
                ("LINEBELOW", (0, 1), (-1, -1), 0.25, HEURISTICS_LINE),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


class BarCell(Flowable):
    """Inline horizontal bar for distribution tables."""

    def __init__(self, value: int, max_value: int, *, width: float = 1.8 * inch, height: float = 10):
        super().__init__()
        self.value = max(0, value)
        self.max_value = max(1, max_value)
        self.width = width
        self.height = height

    def wrap(self, availWidth, availHeight):
        return self.width, self.height

    def draw(self):
        canvas = self.canv
        canvas.setFillColor(colors.HexColor("#E8ECF0"))
        canvas.rect(0, 0, self.width, self.height, fill=1, stroke=0)
        bar_w = self.width * (self.value / self.max_value)
        if bar_w > 0:
            canvas.setFillColor(HEURISTICS_ORANGE)
            canvas.rect(0, 0, bar_w, self.height, fill=1, stroke=0)


def distribution_table(
    rows: list[tuple[str, int, str]],
    st: dict,
    *,
    max_pages: int,
) -> Table:
    """Internal link distribution: bucket label, count + bar, percentage."""
    usable = PAGE_SIZE[0] - 2 * MARGIN
    col_widths = [usable * 0.28, usable * 0.44, usable * 0.14]
    table_data: list[list] = [
        [
            Paragraph(f"<b>{para('Number of internal links')}</b>", st["cell"]),
            Paragraph(f"<b>{para('Number of pages')}</b>", st["cell"]),
            Paragraph(f"<b>{para('% of total pages')}</b>", st["cell_center"]),
        ]
    ]
    for label, pages, pct in rows:
        table_data.append(
            [
                Paragraph(para(label), st["cell"]),
                Table(
                    [
                        [
                            Paragraph(para(str(pages)), st["cell"]),
                            BarCell(pages, max_pages, width=col_widths[1] * 0.55),
                        ]
                    ],
                    colWidths=[col_widths[1] * 0.18, col_widths[1] * 0.82],
                    hAlign="LEFT",
                ),
                Paragraph(para(pct), st["cell_center"]),
            ]
        )
    table = Table(table_data, colWidths=col_widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(_baseline_table_style())
    return table


def executive_summary(
    st: dict,
    *,
    domain: str,
    report_label: str,
    score_badges: list[tuple[str, float, str | None]] | None = None,
    score_lines: list[str] | None = None,
    narrative: str,
    action_items: list[tuple[str, str, str]],
    badge_diameter: float = LARGE_BADGE_DIAMETER,
) -> list:
    """Client-facing summary: scores, narrative, and priority fixes."""
    flow: list = [
        Paragraph("Executive Summary", st["summary_title"]),
        Paragraph(para(f"{report_label} · {domain}"), st["muted"]),
    ]
    if score_badges:
        flow.append(Spacer(1, 0.08 * inch))
        flow.extend(score_badges_block(score_badges, st, diameter=badge_diameter))
    if score_lines:
        flow.append(Spacer(1, 0.04 * inch))
        flow.append(Paragraph(" · ".join(score_lines), st["summary_scores"]))
    if action_items:
        flow.append(Spacer(1, 0.08 * inch))
        flow.append(Paragraph("Overview — issues &amp; resolutions", st["subsection"]))
        flow.extend(issue_resolution_bullets(action_items, st))
    elif narrative:
        flow.append(Spacer(1, 0.08 * inch))
        flow.append(Paragraph("Overview", st["subsection"]))
        flow.append(Paragraph(para(narrative), st["body"]))
    elif not narrative:
        flow.append(
            Paragraph(
                para("No critical issues were identified. Continue monitoring the metrics in this report."),
                st["body"],
            )
        )
    return flow


def manual_appendix(
    rows: list[tuple[str, str, str]],
    st: dict,
    *,
    title: str = "Parameters Not Calculated (Manual)",
) -> list:
    """Manual-parameter appendix; returns nothing when there are no manual rows."""
    if not rows:
        return []
    return [
        Paragraph(title, st["appendix_title"]),
        Paragraph(
            para(
                "The metrics below could not be calculated automatically. "
                "Measure them manually or extend Connected Mode / crawl coverage."
            ),
            st["muted"],
        ),
        data_table(
            ["Parameter", "Section", "Reason"],
            [[a, b, c] for a, b, c in rows],
            st,
            col_widths=[2.0 * inch, 1.3 * inch, 3.2 * inch],
        ),
    ]


def _baseline_table_style() -> TableStyle:
    return TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F4F6F8")),
            ("TEXTCOLOR", (0, 0), (-1, 0), BASELINE_TITLE),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 8),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D9DEE7")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]
    )


def _draw_content_header(canvas, *, right_top: str, right_sub: str = "") -> None:
    """Brand header with rule drawn below text (not through it)."""
    canvas.saveState()
    width, height = PAGE_SIZE
    y_top = height - HEADER_TEXT_TOP
    y_sub = height - HEADER_TEXT_SECOND
    y_rule = height - HEADER_RULE_Y

    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(HEURISTICS_MUTED)
    canvas.drawString(MARGIN, y_top, HEURISTICS_BRAND)
    canvas.drawString(MARGIN, y_sub, HEURISTICS_WEB)
    canvas.drawRightString(width - MARGIN, y_top, right_top)
    if right_sub:
        canvas.drawRightString(width - MARGIN, y_sub, right_sub)

    canvas.setStrokeColor(HEURISTICS_LINE)
    canvas.setLineWidth(0.5)
    canvas.line(MARGIN, y_rule, width - MARGIN, y_rule)
    canvas.restoreState()


def draw_audit_page_decor(canvas, doc, *, domain: str, generated: str) -> None:
    """Heuristics AI header and footer on site audit content pages."""
    canvas.saveState()
    width, _ = PAGE_SIZE
    _draw_content_header(
        canvas,
        right_top=f"Heuristics AI Site Audit  {doc.page}",
        right_sub=generated,
    )

    canvas.setStrokeColor(HEURISTICS_LINE)
    canvas.setLineWidth(0.5)
    canvas.line(MARGIN, 12 * mm, width - MARGIN, 12 * mm)
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(HEURISTICS_MUTED)
    canvas.drawString(MARGIN, 7 * mm, domain)
    canvas.restoreState()


def chart_image(png_bytes: bytes, *, height_ratio: float = 0.24) -> Image:
    """Embed a matplotlib PNG in the baseline PDF."""
    usable = PAGE_SIZE[0] - 2 * MARGIN
    return Image(
        BytesIO(png_bytes),
        width=usable,
        height=usable * height_ratio,
    )


def draw_baseline_page_number(canvas, doc) -> None:
    canvas.saveState()
    width, _ = PAGE_SIZE
    if doc.page > 1:
        _draw_content_header(canvas, right_top=f"Performance Baseline  {doc.page}")
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(HEURISTICS_MUTED)
        canvas.drawRightString(width - MARGIN, 10 * mm, str(doc.page))
    canvas.restoreState()
