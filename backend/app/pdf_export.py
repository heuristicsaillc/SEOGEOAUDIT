"""Build a downloadable PDF for a single SEO or GEO report."""

from __future__ import annotations

from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Table,
    TableStyle,
)

from app.developer_fixes import developer_fix_text, enrich_report
from app.models import Rating, Report
from app.pdf_format import fmt_ms, fmt_num, fmt_score
from app.reference_pdf_layout import (
    CONTENT_BOTTOM_MARGIN,
    CONTENT_TOP_MARGIN,
    MARGIN,
    PAGE_SIZE,
    TABLE_HEADER_BG,
    TABLE_HEADER_FG,
    TABLE_RULE,
    TABLE_ZEBRA,
    audit_cover,
    audit_generated_label,
    draw_audit_page_decor,
    executive_summary,
    para,
    section_spacer,
    styles,
)


def build_report_pdf(
    report: Report,
    *,
    final_url: str,
    duration_seconds: float = 0.0,
    connected: bool = False,
) -> bytes:
    """Render `report` as a PDF and return the raw bytes."""
    enrich_report(report, page_url=final_url)
    st = styles()
    kind_label = "SEO" if report.kind == "seo" else "GEO"
    domain = _host(final_url)
    generated = audit_generated_label()
    action_items = _action_items(report, page_url=final_url)

    local = _local_styles()
    story: list = []

    # --- Cover (logo + title) ---
    story.extend(
        audit_cover(
            st,
            f"{kind_label} Audit Report",
            domain,
            generated,
        )
    )
    story.append(NextPageTemplate("content"))
    story.append(PageBreak())

    # --- Executive summary ---
    story.extend(
        executive_summary(
            st,
            domain=domain,
            report_label=f"{kind_label} Audit",
            score_badges=[(f"{kind_label} score", report.score, report.grade)],
            score_lines=_key_metric_lines(report),
            narrative=_short_overview(report, action_items, kind_label=kind_label),
            action_items=action_items,
        )
    )
    story.append(section_spacer())

    # --- Score overview ---
    story.append(Paragraph("Score overview", st["audit_h2"]))
    story.append(
        _make_table(
            ["Metric", "Value"],
            [
                ["Overall score", f"{fmt_score(report.score)} / 100"],
                ["Grade", report.grade or "—"],
                ["Audit duration", f"{fmt_num(duration_seconds)} s"],
                ["Mode", "Connected (GA4/GSC)" if connected else "Public crawl"],
                ["Manual / not measured", str(report.manual_count)],
            ],
            col_widths=[3.2 * inch, PAGE_SIZE[0] - 2 * MARGIN - 3.2 * inch],
            cell_style=local["cell"],
            header_style=local["cell_header"],
        )
    )

    # --- Category scores ---
    if report.categories:
        story.append(Paragraph("Category scores", st["audit_h2"]))
        cat_rows = [
            [c.title, f"{fmt_score(c.score)}", str(c.scored_count), str(c.manual_count)]
            for c in report.categories
        ]
        usable = PAGE_SIZE[0] - 2 * MARGIN
        story.append(
            _make_table(
                ["Category", "Score", "Scored params", "Manual"],
                cat_rows,
                col_widths=[usable * 0.50, usable * 0.16, usable * 0.18, usable * 0.16],
                cell_style=local["cell"],
                header_style=local["cell_header"],
                center_cols={1, 2, 3},
                header_center_style=local["cell_header_center"],
                cell_center_style=local["cell_center"],
            )
        )

    # --- Panel ---
    panel_rows = _panel_rows(report)
    if panel_rows:
        panel_title = (
            "Core Web Vitals (PageSpeed Insights · mobile)"
            if report.kind == "seo"
            else "AI Citation Appearance"
        )
        story.append(Paragraph(panel_title, st["audit_h2"]))
        story.append(
            _make_table(
                ["Metric", "Value"],
                panel_rows,
                col_widths=[2.4 * inch, PAGE_SIZE[0] - 2 * MARGIN - 2.4 * inch],
                cell_style=local["cell"],
                header_style=local["cell_header"],
            )
        )

    # --- Category parameter tables ---
    for category in report.categories:
        story.append(section_spacer())
        story.append(
            Paragraph(
                f"{para(category.title)} — {fmt_score(category.score)}/100",
                st["audit_h2"],
            )
        )
        table_rows = []
        for param in category.parameters:
            name = para(param.name)
            if param.method:
                name = (
                    f"{para(param.name)}<br/><font size='6' color='#767676'>"
                    f"{para(param.method.value)}"
                    f"{(' · ' + para(param.confidence.value)) if param.confidence else ''}"
                    f"</font>"
                )
            if param.rating.value == "Meeting":
                rec = param.detail or "Meeting — no change required."
            else:
                rec = developer_fix_text(param, page_url=final_url) or param.detail or ""
                if param.priority and param.rating.value not in ("Manual", "Not Measured"):
                    rec = f"[{param.priority.value}] {rec}"
            table_rows.append(
                [
                    name,
                    para(param.what_to_check),
                    para(param.rating.value),
                    para(rec),
                ]
            )
        usable = PAGE_SIZE[0] - 2 * MARGIN
        story.append(
            _make_table(
                ["Parameter", "What to check", "Rating", "Developer fix / Detail"],
                table_rows,
                col_widths=[usable * 0.22, usable * 0.22, usable * 0.12, usable * 0.44],
                cell_style=local["cell"],
                header_style=local["cell_header"],
                center_cols={2},
                header_center_style=local["cell_header_center"],
                cell_center_style=local["cell_center"],
                raw_html_cols={0},
            )
        )

    return _render(story, domain=domain, generated=generated, title=f"{kind_label} Audit Report")


def _render(story: list, *, domain: str, generated: str, title: str) -> bytes:
    buffer = BytesIO()
    doc = BaseDocTemplate(
        buffer,
        pagesize=PAGE_SIZE or A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=CONTENT_TOP_MARGIN,
        bottomMargin=CONTENT_BOTTOM_MARGIN,
        title=title,
    )
    frame = Frame(
        MARGIN,
        CONTENT_BOTTOM_MARGIN,
        PAGE_SIZE[0] - 2 * MARGIN,
        PAGE_SIZE[1] - CONTENT_TOP_MARGIN - CONTENT_BOTTOM_MARGIN,
        id="normal",
    )

    def _on_cover(canvas, _doc):
        pass

    def _on_content(canvas, _doc):
        if _doc.page > 1:
            draw_audit_page_decor(canvas, _doc, domain=domain, generated=generated)

    doc.addPageTemplates(
        [
            PageTemplate(id="cover", frames=[frame], onPage=_on_cover),
            PageTemplate(id="content", frames=[frame], onPage=_on_content),
        ]
    )
    doc.build(story)
    return buffer.getvalue()


def _local_styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    cell = ParagraphStyle(
        "SeoGeoCell",
        parent=base["Normal"],
        fontSize=8,
        leading=11,
        alignment=TA_LEFT,
        textColor=TABLE_HEADER_FG,
    )
    return {
        "cell": cell,
        "cell_center": ParagraphStyle(
            "SeoGeoCellCenter",
            parent=cell,
            alignment=TA_CENTER,
        ),
        "cell_header": ParagraphStyle(
            "SeoGeoCellHeader",
            parent=base["Normal"],
            fontSize=8,
            leading=11,
            alignment=TA_LEFT,
            textColor=TABLE_HEADER_FG,
            fontName="Helvetica-Bold",
        ),
        "cell_header_center": ParagraphStyle(
            "SeoGeoCellHeaderCenter",
            parent=base["Normal"],
            fontSize=8,
            leading=11,
            alignment=TA_CENTER,
            textColor=TABLE_HEADER_FG,
            fontName="Helvetica-Bold",
        ),
    }


def _make_table(
    headers: list[str],
    rows: list[list[str]],
    *,
    col_widths: list,
    cell_style: ParagraphStyle,
    header_style: ParagraphStyle,
    center_cols: set[int] | None = None,
    header_center_style: ParagraphStyle | None = None,
    cell_center_style: ParagraphStyle | None = None,
    raw_html_cols: set[int] | None = None,
) -> Table:
    center_cols = center_cols or set()
    raw_html_cols = raw_html_cols or set()
    header_center_style = header_center_style or header_style
    cell_center_style = cell_center_style or cell_style
    data = []
    header_row = []
    for idx, h in enumerate(headers):
        style = header_center_style if idx in center_cols else header_style
        header_row.append(Paragraph(escape(h), style))
    data.append(header_row)
    for row in rows:
        cells = []
        for idx, cell in enumerate(row):
            style = cell_center_style if idx in center_cols else cell_style
            text = cell if idx in raw_html_cols else escape(str(cell or "")).replace("\n", "<br/>")
            cells.append(Paragraph(text, style))
        data.append(cells)
    table = Table(data, colWidths=col_widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(_soft_table_style(len(data)))
    return table


def _soft_table_style(row_count: int) -> TableStyle:
    """Match supplementary Semrush-like soft table chrome."""
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


def _key_metric_lines(report: Report) -> list[str]:
    errors = sum(
        1
        for category in report.categories
        for param in category.parameters
        if param.rating == Rating.NOT_MEETING
    )
    warnings = sum(
        1
        for category in report.categories
        for param in category.parameters
        if param.rating == Rating.PARTIAL
    )
    return [f"{errors} errors · {warnings} warnings · 0 notices"]


def _short_overview(
    report: Report,
    action_items: list[tuple[str, str, str]],
    *,
    kind_label: str,
) -> str:
    high = sum(1 for _, severity, _ in action_items if severity.lower() in ("not meeting", "error", "errors"))
    moderate = sum(1 for _, severity, _ in action_items if severity.lower() in ("partial", "warning", "warnings"))
    total = len(action_items)
    grade_bit = f" (grade {report.grade})" if report.grade else ""
    parts = [f"{kind_label} score is {float(report.score):.0f}%{grade_bit}."]
    if total == 0:
        parts.append(
            f"No critical {kind_label} issues were identified in this run. "
            "Continue monitoring the detailed parameter tables below."
        )
        return " ".join(parts)
    buckets: list[str] = []
    if high:
        buckets.append(f"{high} high-priority")
    if moderate:
        buckets.append(f"{moderate} moderate")
    if not buckets:
        buckets.append(str(total))
    parts.append(
        f"This report highlights {total} priority area{'s' if total != 1 else ''} "
        f"({', '.join(buckets)}) that need attention. "
        "Specific findings and developer fixes are listed below."
    )
    return " ".join(parts)


def _action_items(
    report: Report,
    *,
    limit: int = 10,
    page_url: str = "",
) -> list[tuple[str, str, str]]:
    order = {Rating.NOT_MEETING: 0, Rating.PARTIAL: 1}
    candidates: list[tuple[int, str, str, str]] = []
    for category in report.categories:
        for param in category.parameters:
            if param.rating not in order:
                continue
            fix = developer_fix_text(param, page_url=page_url) or param.recommendation or param.detail
            candidates.append((order[param.rating], param.name, param.rating.value, fix))
    candidates.sort(key=lambda item: item[0])
    return [(name, rating, fix) for _, name, rating, fix in candidates[:limit]]


def _host(final_url: str) -> str:
    return (
        final_url.replace("https://", "")
        .replace("http://", "")
        .split("/")[0]
        .replace("www.", "")
        or "site"
    )


def _panel_rows(report: Report) -> list[list[str]]:
    panel = report.panel or {}
    if not panel:
        return []

    rows: list[list[str]] = []
    if report.kind == "seo":
        for label, key, as_ms in (
            ("LCP", "lcp_ms", True),
            ("CLS", "cls", False),
            ("INP", "inp_ms", True),
            ("TTFB", "ttfb_ms", True),
        ):
            value = panel.get(key)
            if value is None:
                continue
            if as_ms:
                rows.append([label, fmt_ms(value)])
            else:
                rows.append([label, fmt_num(value)])
        lighthouse = panel.get("lighthouse") or {}
        for cat, score in lighthouse.items():
            rows.append([f"Lighthouse · {cat}", fmt_score(score)])
    else:
        if panel.get("query"):
            rows.append(["Query tested", str(panel["query"])])
        cited = panel.get("cited_by") or []
        rows.append(
            [
                "Cited by",
                ", ".join(cited) if cited else "Not currently cited by tested engines",
            ]
        )
        for label, key in (
            ("Perplexity sources", "perplexity_sources"),
            ("Google AI Overview sources", "ai_overview_sources"),
        ):
            sources = panel.get(key) or []
            if sources:
                rows.append([label, "; ".join(str(s) for s in sources[:8])])
        health = (panel.get("ai_search_health") or {}).get("score")
        if health is not None:
            rows.append(["AI Search Health", f"{fmt_score(health)} / 100"])
    return rows
