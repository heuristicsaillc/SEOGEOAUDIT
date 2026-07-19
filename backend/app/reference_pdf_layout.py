"""Shared ReportLab layout primitives — Semrush-like HeuristicsAI LLC report chrome."""

from __future__ import annotations

import re
from datetime import date, timedelta
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch, mm
from reportlab.platypus import Flowable, Image, Paragraph, Spacer, Table, TableStyle

from app.scoring import grade_for_score

PAGE_SIZE = A4
MARGIN = 18 * mm

# Semrush-like HeuristicsAI palette
KPI_BLUE = colors.HexColor("#2AB3FF")
HEURISTICS_ORANGE = KPI_BLUE  # accent used by bars / links
HEURISTICS_TEXT = colors.HexColor("#222222")
HEURISTICS_MUTED = colors.HexColor("#767676")
HEURISTICS_LINE = colors.HexColor("#E5E7EB")
BASELINE_TITLE = colors.HexColor("#222222")
BASELINE_MUTED = colors.HexColor("#767676")
TABLE_HEADER_BG = colors.HexColor("#F7F8F8")
TABLE_HEADER_FG = colors.HexColor("#333333")
TABLE_ZEBRA = colors.HexColor("#FBFBFB")
TABLE_GRID = colors.HexColor("#E8E8E8")
TABLE_RULE = colors.HexColor("#E5E7EB")

HEURISTICS_BRAND = "HeuristicsAI LLC"
HEURISTICS_WEB = "WWW.HEURISTICSAISOLUTIONS.COM"
FOOTER_ATTRIBUTION = "The report data is prepared by HeuristicsAI LLC"

SEVERITY_ERROR = colors.HexColor("#DC2626")
SEVERITY_WARNING = colors.HexColor("#EA580C")
SEVERITY_NOTICE = colors.HexColor("#CA8A04")
SEVERITY_OK = colors.HexColor("#16A34A")

SCORE_GOOD = colors.HexColor("#2ECC71")
SCORE_WARN = colors.HexColor("#F1C40F")
SCORE_BAD = colors.HexColor("#E74C3C")
SCORE_WARN_TEXT = colors.HexColor("#222222")

_ASSETS = Path(__file__).resolve().parent / "assets"
LOGO_PATH = _ASSETS / "ha-brand-mark-256.png"
LOGO_HEADER_PATH = _ASSETS / "ha-brand-mark-96.png"
# Fall back to full-resolution mark if resized assets are missing
if not LOGO_PATH.exists():
    LOGO_PATH = _ASSETS / "ha-brand-mark.png"
if not LOGO_HEADER_PATH.exists():
    LOGO_HEADER_PATH = LOGO_PATH

HEADER_TEXT_TOP = 10 * mm
HEADER_TEXT_SECOND = 14 * mm
HEADER_RULE_Y = 20 * mm
CONTENT_TOP_MARGIN = 26 * mm
CONTENT_BOTTOM_MARGIN = 18 * mm


def para(text: str) -> str:
    return escape(text or "").replace("\n", "<br/>")


def styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "baseline_cover_title": ParagraphStyle(
            "baseline_cover_title",
            parent=base["Normal"],
            fontSize=26,
            leading=32,
            alignment=TA_CENTER,
            textColor=BASELINE_TITLE,
            spaceAfter=10,
            fontName="Helvetica",
        ),
        "baseline_cover_sub": ParagraphStyle(
            "baseline_cover_sub",
            parent=base["Normal"],
            fontSize=12,
            leading=16,
            alignment=TA_CENTER,
            textColor=BASELINE_MUTED,
            spaceAfter=6,
        ),
        "section_title": ParagraphStyle(
            "section_title",
            parent=base["Heading2"],
            fontSize=15,
            leading=19,
            textColor=BASELINE_TITLE,
            spaceBefore=8,
            spaceAfter=12,
            fontName="Helvetica",
        ),
        "subsection": ParagraphStyle(
            "subsection",
            parent=base["Heading3"],
            fontSize=11,
            leading=14,
            textColor=BASELINE_TITLE,
            spaceBefore=6,
            spaceAfter=6,
            fontName="Helvetica",
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
            fontSize=8.5,
            leading=11,
            alignment=TA_LEFT,
            textColor=BASELINE_TITLE,
        ),
        "cell_header": ParagraphStyle(
            "cell_header",
            parent=base["Normal"],
            fontSize=8,
            leading=11,
            alignment=TA_LEFT,
            textColor=TABLE_HEADER_FG,
            fontName="Helvetica-Bold",
        ),
        "cell_header_center": ParagraphStyle(
            "cell_header_center",
            parent=base["Normal"],
            fontSize=8,
            leading=11,
            alignment=TA_CENTER,
            textColor=TABLE_HEADER_FG,
            fontName="Helvetica-Bold",
        ),
        "cell_center": ParagraphStyle(
            "cell_center",
            parent=base["Normal"],
            fontSize=8.5,
            leading=11,
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
            spaceAfter=2,
        ),
        "kpi_value": ParagraphStyle(
            "kpi_value",
            parent=base["Normal"],
            fontSize=22,
            leading=26,
            alignment=TA_LEFT,
            textColor=KPI_BLUE,
            fontName="Helvetica",
        ),
        "score_label": ParagraphStyle(
            "score_label",
            parent=base["Normal"],
            fontSize=10,
            leading=13,
            textColor=BASELINE_MUTED,
            spaceAfter=2,
        ),
        "score_value": ParagraphStyle(
            "score_value",
            parent=base["Normal"],
            fontSize=36,
            leading=40,
            textColor=KPI_BLUE,
            fontName="Helvetica",
            spaceAfter=8,
        ),
        "issue_name": ParagraphStyle(
            "issue_name",
            parent=base["Normal"],
            fontSize=9.5,
            leading=13,
            textColor=HEURISTICS_TEXT,
            spaceAfter=2,
        ),
        "issue_name_ok": ParagraphStyle(
            "issue_name_ok",
            parent=base["Normal"],
            fontSize=9.5,
            leading=13,
            textColor=SEVERITY_OK,
            spaceAfter=2,
        ),
        "issue_count": ParagraphStyle(
            "issue_count",
            parent=base["Normal"],
            fontSize=14,
            leading=16,
            alignment=TA_RIGHT,
            textColor=HEURISTICS_TEXT,
            fontName="Helvetica",
        ),
        "issue_fix": ParagraphStyle(
            "issue_fix",
            parent=base["Normal"],
            fontSize=8,
            leading=11,
            textColor=BASELINE_MUTED,
            spaceBefore=2,
            spaceAfter=4,
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
            fontSize=13,
            leading=17,
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
            fontSize=16,
            leading=20,
            textColor=HEURISTICS_TEXT,
            spaceAfter=10,
            fontName="Helvetica",
        ),
        "audit_h2": ParagraphStyle(
            "audit_h2",
            parent=base["Heading2"],
            fontSize=12,
            leading=16,
            textColor=HEURISTICS_TEXT,
            spaceBefore=6,
            spaceAfter=8,
            fontName="Helvetica",
        ),
        "audit_h2_error": ParagraphStyle(
            "audit_h2_error",
            parent=base["Heading2"],
            fontSize=12,
            leading=16,
            textColor=SEVERITY_ERROR,
            spaceBefore=6,
            spaceAfter=8,
        ),
        "audit_h2_warning": ParagraphStyle(
            "audit_h2_warning",
            parent=base["Heading2"],
            fontSize=12,
            leading=16,
            textColor=SEVERITY_WARNING,
            spaceBefore=6,
            spaceAfter=8,
        ),
        "audit_h2_notice": ParagraphStyle(
            "audit_h2_notice",
            parent=base["Heading2"],
            fontSize=12,
            leading=16,
            textColor=SEVERITY_NOTICE,
            spaceBefore=6,
            spaceAfter=8,
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
            fontSize=9.5,
            leading=13,
            textColor=HEURISTICS_TEXT,
            spaceAfter=2,
        ),
        "audit_issue_error": ParagraphStyle(
            "audit_issue_error",
            parent=base["Normal"],
            fontSize=9.5,
            leading=13,
            textColor=SEVERITY_ERROR,
            spaceAfter=2,
        ),
        "audit_issue_warning": ParagraphStyle(
            "audit_issue_warning",
            parent=base["Normal"],
            fontSize=9.5,
            leading=13,
            textColor=SEVERITY_WARNING,
            spaceAfter=2,
        ),
        "cell_error": ParagraphStyle(
            "cell_error",
            parent=base["Normal"],
            fontSize=8.5,
            leading=11,
            alignment=TA_LEFT,
            textColor=SEVERITY_ERROR,
        ),
        "cell_warning": ParagraphStyle(
            "cell_warning",
            parent=base["Normal"],
            fontSize=8.5,
            leading=11,
            alignment=TA_LEFT,
            textColor=SEVERITY_WARNING,
        ),
        "cell_notice": ParagraphStyle(
            "cell_notice",
            parent=base["Normal"],
            fontSize=8.5,
            leading=11,
            alignment=TA_LEFT,
            textColor=SEVERITY_NOTICE,
        ),
        "cell_center_error": ParagraphStyle(
            "cell_center_error",
            parent=base["Normal"],
            fontSize=8.5,
            leading=11,
            alignment=TA_CENTER,
            textColor=SEVERITY_ERROR,
        ),
        "cell_center_warning": ParagraphStyle(
            "cell_center_warning",
            parent=base["Normal"],
            fontSize=8.5,
            leading=11,
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
            fontSize=8,
            leading=11,
            alignment=TA_CENTER,
            textColor=BASELINE_MUTED,
            spaceAfter=4,
        ),
        "appendix_title": ParagraphStyle(
            "appendix_title",
            parent=base["Heading2"],
            fontSize=12,
            leading=15,
            textColor=BASELINE_TITLE,
            spaceBefore=14,
            spaceAfter=8,
        ),
        "summary_title": ParagraphStyle(
            "summary_title",
            parent=base["Heading1"],
            fontSize=16,
            leading=20,
            textColor=BASELINE_TITLE,
            spaceAfter=6,
            fontName="Helvetica",
        ),
        "summary_scores": ParagraphStyle(
            "summary_scores",
            parent=base["Normal"],
            fontSize=10,
            leading=13,
            textColor=KPI_BLUE,
            spaceAfter=8,
        ),
        "key_metric": ParagraphStyle(
            "key_metric",
            parent=base["Normal"],
            fontSize=14,
            leading=19,
            textColor=HEURISTICS_TEXT,
            fontName="Helvetica-Bold",
            spaceAfter=4,
        ),
        "key_metric_label": ParagraphStyle(
            "key_metric_label",
            parent=base["Normal"],
            fontSize=11,
            leading=14,
            textColor=HEURISTICS_TEXT,
            fontName="Helvetica-Bold",
            spaceAfter=3,
        ),
    }


def section_spacer() -> Spacer:
    """Gap between major report sections (avoids forced page breaks)."""
    return Spacer(1, 0.28 * inch)


def subsection_spacer() -> Spacer:
    """Gap between subsections within a report page."""
    return Spacer(1, 0.2 * inch)


DEFAULT_BADGE_DIAMETER = 0.68 * inch
LARGE_BADGE_DIAMETER = 0.92 * inch


def brand_logo_image(*, width: float = 0.95 * inch) -> Image:
    """Centered HeuristicsAI brand mark for covers."""
    img = Image(str(LOGO_PATH), width=width, height=width)
    img.hAlign = "CENTER"
    return img


def _draw_logo_on_canvas(canvas, *, x: float, y: float, size: float = 11 * mm) -> None:
    path = LOGO_HEADER_PATH if LOGO_HEADER_PATH.exists() else LOGO_PATH
    if path.exists():
        canvas.drawImage(
            str(path),
            x,
            y,
            width=size,
            height=size,
            mask="auto",
            preserveAspectRatio=True,
        )


def _grade_fill_and_text(grade: str) -> tuple[colors.Color, colors.Color]:
    if grade in ("A", "B"):
        return SCORE_GOOD, colors.white
    if grade in ("C", "D"):
        return SCORE_WARN, SCORE_WARN_TEXT
    return SCORE_BAD, colors.white


class ScoreBadge(Flowable):
    """Circular grade + score badge (legacy; supplementary PDFs use large % scores)."""

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
        score_text = f"{float(self.score):.2f}/100"
        score_w = canvas.stringWidth(score_text, "Helvetica", self.score_pt)
        canvas.drawString(radius - score_w / 2, radius - self.letter_pt * 0.55, score_text)


def score_display_block(
    badges: list[tuple[str, float, str | None]],
    st: dict,
) -> list:
    """Large Semrush-style score percentages (label + big number)."""
    flow: list = []
    for index, (label, score, _grade) in enumerate(badges):
        if index:
            flow.append(Spacer(1, 0.12 * inch))
        flow.append(Paragraph(para(label), st["score_label"]))
        flow.append(Paragraph(f"{float(score):.0f}%", st["score_value"]))
    return flow


def score_badge_inline(
    label: str,
    score: float,
    st: dict,
    *,
    grade: str | None = None,
    diameter: float = LARGE_BADGE_DIAMETER,
) -> Table:
    """Label left-aligned beside a score badge (legacy layout helper)."""
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
    """Prefer large % display for supplementary Semrush-like PDFs."""
    return score_display_block(badges, st)


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
    """Bulleted issue + developer resolution list for executive overview."""
    flow: list = []
    for issue, severity, fix in action_items:
        color = "#DC2626"
        if severity.lower() in ("partial", "warning", "warnings"):
            color = "#EA580C"
        elif severity.lower() in ("notice", "notices"):
            color = "#CA8A04"
        fix_label = "Developer fix" if "Where:" in (fix or "") else "Resolution"
        flow.append(
            Paragraph(
                f"<bullet>&bull;</bullet> "
                f'<font color="{color}"><b>{para(issue)}</b> ({para(severity)})</font><br/>'
                f"&nbsp;&nbsp;&nbsp;&nbsp;<b>{fix_label}:</b><br/>"
                f"&nbsp;&nbsp;&nbsp;&nbsp;{para(fix)}",
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


def semrush_cover(
    st: dict,
    *,
    title: str,
    lines: list[str],
    generated_label: str,
) -> list:
    """Centered Semrush-like cover: logo, title, meta lines, generated date."""
    flow: list = [
        Spacer(1, 1.35 * inch),
        brand_logo_image(width=1.05 * inch),
        Spacer(1, 0.55 * inch),
        Paragraph(para(title), st["baseline_cover_title"]),
        Spacer(1, 0.15 * inch),
    ]
    for line in lines:
        if line:
            flow.append(Paragraph(para(line), st["baseline_cover_sub"]))
    flow.append(Spacer(1, 2.2 * inch))
    flow.append(Paragraph(para(generated_label), st["baseline_cover_brand"]))
    flow.append(Paragraph(para(f"{HEURISTICS_BRAND} · {HEURISTICS_WEB}"), st["baseline_cover_brand"]))
    return flow


def baseline_cover(st: dict, range_label: str, generated_label: str, *, domain: str = "") -> list:
    lines = [
        "Traffic, Engagement, SEO & Web Vitals",
        f"Prepared for {domain}" if domain else "Client Performance Report",
        range_label,
    ]
    return semrush_cover(
        st,
        title="Performance Baseline",
        lines=lines,
        generated_label=generated_label,
    )


def audit_cover(st: dict, title: str, domain: str, generated_label: str) -> list:
    return semrush_cover(
        st,
        title=title,
        lines=[domain, "Prepared for client review"],
        generated_label=generated_label,
    )


def kpi_grid(items: list[tuple[str, str]], st: dict, cols: int = 3) -> Table:
    """Unboxed Semrush-style KPI grid: muted labels + large blue values."""
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
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
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
    header_cells = []
    for idx, h in enumerate(headers):
        style_key = "cell_header_center" if idx in center_cols else "cell_header"
        header_cells.append(Paragraph(para(h), st[style_key]))
    table_data = [header_cells]
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
    table.setStyle(_professional_table_style(len(table_data)))
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
            Paragraph("", st["cell_header"]),
            Paragraph("Count", st["cell_header_center"]),
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
    table.setStyle(_professional_table_style(len(table_data)))
    return table


def _format_developer_fix_html(fix: str) -> str:
    """Render Where/Change/Evidence lines with muted labels for readability."""
    if not (fix or "").strip():
        return ""
    parts: list[str] = []
    for line in fix.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        for prefix in ("Where:", "Change:", "Evidence:", "Affected URLs:", "Effort:"):
            if line.startswith(prefix):
                rest = line[len(prefix) :].strip()
                parts.append(f"<b>{escape(prefix)}</b> {escape(rest)}")
                break
        else:
            parts.append(escape(line))
    return "<br/>".join(parts)


def audit_issue_table(
    rows: list[tuple],
    st: dict,
    *,
    severity: str = "error",
) -> Table:
    """Semrush-like hairline issue list with full Where / Change under each actionable row."""
    usable = PAGE_SIZE[0] - 2 * MARGIN
    table_data: list = []
    for row in rows:
        label = row[0]
        new_count = row[1] if len(row) > 1 else "0"
        fix = row[3] if len(row) > 3 else ""
        try:
            new_n = int(str(new_count).strip() or "0")
        except ValueError:
            new_n = 0

        sev_hex = {
            "error": "#DC2626",
            "warning": "#EA580C",
            "notice": "#CA8A04",
        }.get(severity.lower(), "#222222")
        if new_n > 0:
            fix_html = _format_developer_fix_html(str(fix))
            left_html = f'<font color="{sev_hex}"><b>{para(label)}</b></font>'
            if fix_html:
                left_html += f'<br/><font color="#767676">{fix_html}</font>'
            left = Paragraph(left_html, st["issue_name"])
        else:
            left = Paragraph(para(label), st["issue_name_ok"])
        right = Paragraph(para(str(new_count)), st["issue_count"])
        table_data.append([left, right])

    if not table_data:
        return Table([[Paragraph("—", st["cell"])]], colWidths=[usable])

    table = Table(
        table_data,
        colWidths=[usable * 0.86, usable * 0.14],
        hAlign="LEFT",
    )
    commands = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LINEBELOW", (0, 0), (-1, -2), 0.4, TABLE_RULE),
    ]
    table.setStyle(TableStyle(commands))
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
            canvas.setFillColor(KPI_BLUE)
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
            Paragraph(para("Number of internal links"), st["cell_header"]),
            Paragraph(para("Number of pages"), st["cell_header"]),
            Paragraph(para("% of total pages"), st["cell_header_center"]),
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
    table.setStyle(_professional_table_style(len(table_data)))
    return table


_SEVERITY_HEX = {
    "not meeting": "#DC2626",
    "error": "#DC2626",
    "errors": "#DC2626",
    "partial": "#EA580C",
    "warning": "#EA580C",
    "warnings": "#EA580C",
    "notice": "#CA8A04",
    "notices": "#CA8A04",
}


def _colorize_key_metric(line: str) -> str:
    """Bold + color-code 'N errors / N warnings / N notices' counts in a metric line."""
    html = escape(line or "")
    for pattern, hex_color in (
        (r"(\d[\d,\.]*\s*errors?)", "#DC2626"),
        (r"(\d[\d,\.]*\s*warnings?)", "#EA580C"),
        (r"(\d[\d,\.]*\s*notices?)", "#CA8A04"),
    ):
        html = re.sub(pattern, rf'<font color="{hex_color}">\1</font>', html, flags=re.IGNORECASE)
    return html


def key_metric_block(score_lines: list[str], st: dict) -> list:
    """Key metric as a bold, larger, color-coded line with a muted label."""
    flow: list = [Paragraph("Key metric", st["key_metric_label"])]
    for line in score_lines:
        flow.append(Paragraph(_colorize_key_metric(line), st["key_metric"]))
    return flow


def priority_issues_table(action_items: list[tuple[str, str, str]], st: dict) -> Table:
    """Tabular priority issues: Issue | Severity | Developer fix (where & what)."""
    usable = PAGE_SIZE[0] - 2 * MARGIN
    table_data: list = [
        [
            Paragraph("Issue", st["cell_header"]),
            Paragraph("Severity", st["cell_header_center"]),
            Paragraph("Developer fix (where &amp; what)", st["cell_header"]),
        ]
    ]
    for issue, severity, fix in action_items:
        sev_hex = _SEVERITY_HEX.get(severity.lower(), "#222222")
        fix_html = _format_developer_fix_html(fix) or "—"
        table_data.append(
            [
                Paragraph(f'<font color="{sev_hex}"><b>{para(issue)}</b></font>', st["cell"]),
                Paragraph(f'<font color="{sev_hex}">{para(severity)}</font>', st["cell_center"]),
                Paragraph(fix_html, st["cell"]),
            ]
        )
    table = Table(
        table_data,
        colWidths=[usable * 0.24, usable * 0.13, usable * 0.63],
        repeatRows=1,
        hAlign="LEFT",
    )
    table.setStyle(_professional_table_style(len(table_data)))
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
    """Client-facing summary: large scores, narrative, and priority fixes with Where/Change."""
    del badge_diameter  # unused; large % display replaces circular badges
    flow: list = [
        Paragraph("Executive Summary", st["summary_title"]),
        Paragraph(para(f"{report_label} · {domain}"), st["muted"]),
    ]
    if score_badges:
        flow.append(Spacer(1, 0.08 * inch))
        flow.extend(score_display_block(score_badges, st))
    if score_lines:
        flow.append(Spacer(1, 0.06 * inch))
        flow.extend(key_metric_block(score_lines, st))
    if narrative:
        flow.append(Spacer(1, 0.08 * inch))
        flow.append(Paragraph("Overview", st["subsection"]))
        flow.append(Paragraph(para(narrative), st["body"]))
    if action_items:
        flow.append(Spacer(1, 0.12 * inch))
        flow.append(Paragraph("Priority issues &amp; developer fixes", st["subsection"]))
        flow.append(priority_issues_table(action_items, st))
    elif not narrative and not action_items:
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
    """Backward-compatible alias for the professional table style."""
    return _professional_table_style(2)


def _professional_table_style(row_count: int) -> TableStyle:
    """Soft Semrush-like table: light header, hairline rules, airy rows."""
    commands = [
        ("BACKGROUND", (0, 0), (-1, 0), TABLE_HEADER_BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), TABLE_HEADER_FG),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("LINEBELOW", (0, 0), (-1, 0), 0.6, TABLE_RULE),
        ("LINEBELOW", (0, 1), (-1, -2), 0.35, TABLE_RULE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]
    for row in range(1, max(row_count, 1)):
        if row % 2 == 0:
            commands.append(("BACKGROUND", (0, row), (-1, row), TABLE_ZEBRA))
    return TableStyle(commands)


def draw_semrush_header(canvas) -> None:
    """Logo left + web URL right + hairline (Semrush content header)."""
    canvas.saveState()
    width, height = PAGE_SIZE
    logo_size = 10 * mm
    _draw_logo_on_canvas(canvas, x=MARGIN, y=height - 16 * mm, size=logo_size)
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(HEURISTICS_MUTED)
    canvas.drawRightString(width - MARGIN, height - 12 * mm, HEURISTICS_WEB)
    canvas.setStrokeColor(HEURISTICS_LINE)
    canvas.setLineWidth(0.5)
    canvas.line(MARGIN, height - HEADER_RULE_Y, width - MARGIN, height - HEADER_RULE_Y)
    canvas.restoreState()


def draw_semrush_footer(canvas, doc, *, generated: str = "") -> None:
    """Hairline footer: generated | attribution | page number."""
    canvas.saveState()
    width, _ = PAGE_SIZE
    y_rule = 12 * mm
    y_text = 7 * mm
    canvas.setStrokeColor(HEURISTICS_LINE)
    canvas.setLineWidth(0.5)
    canvas.line(MARGIN, y_rule, width - MARGIN, y_rule)
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(HEURISTICS_MUTED)
    if generated:
        canvas.drawString(MARGIN, y_text, generated)
    canvas.drawCentredString(width / 2, y_text, FOOTER_ATTRIBUTION)
    canvas.drawRightString(width - MARGIN, y_text, str(doc.page))
    canvas.restoreState()


def draw_audit_page_decor(canvas, doc, *, domain: str, generated: str) -> None:
    """HeuristicsAI Semrush-like header and footer on site audit content pages."""
    del domain  # domain kept for call-site compatibility; footer uses brand attribution
    draw_semrush_header(canvas)
    draw_semrush_footer(canvas, doc, generated=generated)


def chart_image(
    png_bytes: bytes,
    *,
    width: float | None = None,
    height_ratio: float | None = None,
) -> Image:
    """Embed a matplotlib PNG, preserving its native aspect ratio.

    `height_ratio` is ignored for sizing (kept for call-site compatibility).
    Pass `width` to fit a column; defaults to the full content width.
    """
    usable = PAGE_SIZE[0] - 2 * MARGIN
    target_w = width if width is not None else usable
    img = Image(BytesIO(png_bytes))
    native_w = float(getattr(img, "imageWidth", 0) or 0)
    native_h = float(getattr(img, "imageHeight", 0) or 0)
    aspect = (native_h / native_w) if native_w > 0 else (height_ratio or 0.42)
    img.drawWidth = target_w
    img.drawHeight = target_w * aspect
    return img


def draw_baseline_page_number(canvas, doc) -> None:
    canvas.saveState()
    if doc.page > 1:
        draw_semrush_header(canvas)
        draw_semrush_footer(canvas, doc, generated=audit_generated_label())
    canvas.restoreState()
