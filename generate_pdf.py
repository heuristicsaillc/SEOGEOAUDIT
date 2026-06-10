"""Convert a Markdown document into a styled, downloadable PDF.

Pure-Python (fpdf2) Markdown-subset renderer tuned for these docs:
headings, paragraphs, bullet lists, horizontal rules, pipe tables, and
boxes-and-arrows flow diagrams via [[FLOW:auth]] / [[FLOW:connected]] /
[[FLOW:architecture]] markers.

Usage:
    python3 generate_pdf.py [input.md] [output.pdf]
Defaults to SEO_GEO_Parameter_Reference.md -> SEO_GEO_Parameter_Reference.pdf
"""

import sys
from pathlib import Path
from fpdf import FPDF
from fpdf.enums import XPos, YPos
from fpdf.fonts import FontFace

SRC = Path(__file__).with_name("SEO_GEO_Parameter_Reference.md")
OUT = Path(__file__).with_name("SEO_GEO_Parameter_Reference.pdf")

# Relative widths for parameter tables (landscape A4).
TABLE5_WIDTHS = (38, 66, 64, 22, 47)
TABLE4_WIDTHS = (42, 14, 118, 83)
TABLE3_WIDTHS = (78, 32, 147)

_REPL = {
    "\u2013": "-", "\u2014": "-", "\u2018": "'", "\u2019": "'",
    "\u201c": '"', "\u201d": '"', "\u2265": ">=", "\u2264": "<=",
    "\u2192": "->", "\u2022": "-", "\u00d7": "x", "\u2026": "...",
    "\u2605": "*",
}


def sanitize(text: str) -> str:
    for k, v in _REPL.items():
        text = text.replace(k, v)
    return text.encode("latin-1", "replace").decode("latin-1")


class Doc(FPDF):
    def header(self):
        pass

    def footer(self):
        self.set_y(-10)
        self.set_font("Helvetica", "I", 7)
        self.set_text_color(130)
        title = getattr(self, "doc_title", "SEO & GEO")
        self.cell(0, 6, f"{title}  -  Page {self.page_no()}", align="C")


def split_table_row(line: str):
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    return [sanitize(c) for c in cells]


def is_separator_row(line: str) -> bool:
    body = line.strip().strip("|")
    return bool(body) and all(set(c.strip()) <= set("-: ") for c in body.split("|"))


OAUTH_STEPS = [
    "1. Operator: enable Search Console + GA4 Data + GA4 Admin APIs",
    "2. Operator: OAuth consent + Desktop client -> secrets/google-oauth-client.json",
    "3. Operator: python scripts/google_auth.py (browser sign-in from backend/)",
    "4. Operator: copy GSC URL + GA4 Property ID -> connected_properties.json",
    "5. Operator: restart backend; audits use saved OAuth token",
]


def draw_box(pdf, x, y, w, h, text, fill=(239, 246, 255), border=(37, 99, 235)):
    pdf.set_fill_color(*fill)
    pdf.set_draw_color(*border)
    pdf.set_line_width(0.3)
    pdf.rect(x, y, w, h, style="DF")
    pdf.set_font("Helvetica", "", 7)
    pdf.set_text_color(31, 41, 55)
    pdf.set_xy(x + 1.5, y + 1.5)
    pdf.multi_cell(w - 3, 3.3, sanitize(text), align="C",
                   new_x=XPos.LMARGIN, new_y=YPos.TOP)


def arrow_h(pdf, x1, y, x2):
    pdf.set_draw_color(110, 110, 110)
    pdf.set_line_width(0.3)
    pdf.line(x1, y, x2, y)
    pdf.line(x2, y, x2 - 2, y - 1.4)
    pdf.line(x2, y, x2 - 2, y + 1.4)


def draw_hflow(pdf, items, box_h=22):
    avail = pdf.w - pdf.l_margin - pdf.r_margin
    n = len(items)
    gap = 8
    box_w = (avail - gap * (n - 1)) / n
    if pdf.get_y() + box_h + 10 > pdf.h - pdf.b_margin:
        pdf.add_page()
    y = pdf.get_y() + 2
    pdf.set_auto_page_break(False)
    for i, t in enumerate(items):
        x = pdf.l_margin + i * (box_w + gap)
        draw_box(pdf, x, y, box_w, box_h, t)
        if i < n - 1:
            arrow_h(pdf, x + box_w, y + box_h / 2, x + box_w + gap)
    pdf.set_auto_page_break(True, margin=14)
    pdf.set_xy(pdf.l_margin, y + box_h + 6)


ARCH_STAGES = [
    "Input URL",
    "Fetch + render: httpx, Playwright/Firecrawl; robots, sitemap, llms.txt",
    "Analyze: SEO sections 01-07 + GEO sections 01-08",
    "Data sources: PSI/CrUX, GA4+GSC, SerpApi, Perplexity, OpenAI, Wikidata/KG, Serper/X, Gemini",
    "Scoring + recommendations",
    "Two reports: SEO + GEO",
]


def draw_architecture(pdf):
    draw_hflow(pdf, ARCH_STAGES, box_h=28)


def draw_decision(pdf):
    if pdf.get_y() + 42 > pdf.h - pdf.b_margin:
        pdf.add_page()
    y = pdf.get_y() + 2
    lm = pdf.l_margin
    pdf.set_auto_page_break(False)
    draw_box(pdf, lm, y + 12, 45, 12, "Audit domain")
    draw_box(pdf, lm + 55, y + 11, 60, 14, "Domain in connected_properties.json ?",
             fill=(255, 247, 237), border=(217, 119, 6))
    draw_box(pdf, lm + 130, y + 2, 115, 11,
             "Yes: OAuth + registry -> GSC/GA4 -> up to 6 first-party params scored",
             fill=(236, 253, 245), border=(5, 150, 105))
    draw_box(pdf, lm + 130, y + 23, 115, 11,
             "No: 6 params = Manual (excluded from score)",
             fill=(254, 242, 242), border=(220, 38, 38))
    arrow_h(pdf, lm + 45, y + 18, lm + 55)
    pdf.set_draw_color(110, 110, 110)
    pdf.set_line_width(0.3)
    pdf.line(lm + 115, y + 18, lm + 125, y + 18)
    pdf.line(lm + 125, y + 7, lm + 125, y + 28)
    arrow_h(pdf, lm + 125, y + 7, lm + 130)
    arrow_h(pdf, lm + 125, y + 28, lm + 130)
    pdf.set_auto_page_break(True, margin=14)
    pdf.set_xy(pdf.l_margin, y + 38)


def render_table(pdf: Doc, rows):
    if not rows:
        return
    ncols = len(rows[0])
    widths = {5: TABLE5_WIDTHS, 4: TABLE4_WIDTHS, 3: TABLE3_WIDTHS}.get(ncols)
    pdf.set_font("Helvetica", "", 6.5 if ncols == 4 else 7)
    line_h = 3.8 if ncols == 4 else 4.2
    pdf.set_draw_color(200)
    with pdf.table(
        col_widths=widths,
        text_align="LEFT",
        line_height=line_h,
        first_row_as_headings=True,
        headings_style=FontFace(emphasis="BOLD", color=255, fill_color=(37, 99, 235)),
        cell_fill_color=(244, 247, 252),
        cell_fill_mode="ROWS",
    ) as table:
        for r in rows:
            row = table.row()
            for cell in r:
                row.cell(cell)
    pdf.ln(3)


def main():
    src = Path(sys.argv[1]).expanduser() if len(sys.argv) > 1 else SRC
    out = Path(sys.argv[2]).expanduser() if len(sys.argv) > 2 else OUT
    text = src.read_text(encoding="utf-8")
    lines = text.splitlines()

    pdf = Doc(orientation="L", unit="mm", format="A4")
    first_heading = next((l[2:].strip() for l in lines if l.startswith("# ")), "SEO & GEO")
    pdf.doc_title = first_heading
    pdf.set_auto_page_break(auto=True, margin=14)
    pdf.set_margins(10, 12, 10)
    pdf.add_page()

    table_buf = []

    def flush_table():
        nonlocal table_buf
        if table_buf:
            render_table(pdf, table_buf)
            table_buf = []

    for raw in lines:
        line = raw.rstrip()

        if line.strip() in ("[[FLOW:auth]]", "[[FLOW:connected]]", "[[FLOW:architecture]]"):
            flush_table()
            marker = line.strip()
            if marker.endswith("auth]]"):
                draw_hflow(pdf, OAUTH_STEPS)
            elif marker.endswith("architecture]]"):
                draw_architecture(pdf)
            else:
                draw_decision(pdf)
            continue

        if line.lstrip().startswith("|") and "|" in line.strip("|"):
            if is_separator_row(line):
                continue
            table_buf.append(split_table_row(line))
            continue
        else:
            flush_table()

        if not line.strip():
            continue

        if line.startswith("# "):
            pdf.set_font("Helvetica", "B", 16)
            pdf.set_text_color(17, 24, 39)
            pdf.multi_cell(0, 8, sanitize(line[2:].strip()),
                           new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.ln(1)
        elif line.startswith("## "):
            pdf.ln(1)
            pdf.set_font("Helvetica", "B", 12)
            pdf.set_text_color(37, 99, 235)
            pdf.multi_cell(0, 6, sanitize(line[3:].strip()),
                           new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.ln(1)
        elif line.startswith("### "):
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(31, 41, 55)
            pdf.multi_cell(0, 5, sanitize(line[4:].strip()),
                           new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        elif line.strip() == "---":
            pdf.set_draw_color(210)
            y = pdf.get_y() + 1
            pdf.line(pdf.l_margin, y, pdf.w - pdf.r_margin, y)
            pdf.set_xy(pdf.l_margin, y)
            pdf.ln(3)
        elif line.lstrip().startswith("- "):
            pdf.set_font("Helvetica", "", 8.5)
            pdf.set_text_color(31, 41, 55)
            pdf.set_x(pdf.l_margin + 3)
            pdf.multi_cell(0, 4.6, sanitize("- " + line.lstrip()[2:].strip()),
                           new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        else:
            pdf.set_font("Helvetica", "", 8.5)
            pdf.set_text_color(31, 41, 55)
            pdf.multi_cell(0, 4.6, sanitize(line.strip()),
                           new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    flush_table()
    pdf.output(str(out))
    print("Wrote", out)


if __name__ == "__main__":
    main()
