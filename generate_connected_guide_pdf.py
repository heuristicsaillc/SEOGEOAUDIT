"""Generate professional portrait PDFs for Connected Mode setup guides.

Usage:
    python3 generate_connected_guide_pdf.py Connected_Mode_Site_Owner_Guide.md
    python3 generate_connected_guide_pdf.py Connected_Mode_Tool_Operator_Guide.md
"""

from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

from fpdf import FPDF
from fpdf.enums import XPos, YPos
from fpdf.fonts import FontFace

# Brand colours
NAVY = (15, 23, 42)
BLUE = (37, 99, 235)
SLATE = (71, 85, 105)
LIGHT_BG = (248, 250, 252)
CODE_BG = (241, 245, 249)
ACCENT = (14, 116, 144)

_REPL = {
    "\u2013": "-", "\u2014": "-", "\u2018": "'", "\u2019": "'",
    "\u201c": '"', "\u201d": '"', "\u2192": "->", "\u2022": "-",
}


def sanitize(text: str) -> str:
    for k, v in _REPL.items():
        text = text.replace(k, v)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = text.replace("`", "")
    return text.encode("latin-1", "replace").decode("latin-1")


class GuidePDF(FPDF):
    """Portrait A4 guide with cover band, header, and footer."""

    def __init__(self, doc_title: str, doc_subtitle: str, audience: str):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.doc_title = doc_title
        self.doc_subtitle = doc_subtitle
        self.audience = audience
        self.set_auto_page_break(auto=True, margin=18)
        self.set_margins(18, 16, 18)

    def header(self):
        if self.page_no() == 1:
            return
        self.set_fill_color(*NAVY)
        self.rect(0, 0, self.w, 11, style="F")
        self.set_xy(18, 3)
        self.set_font("Helvetica", "B", 8)
        self.set_text_color(255, 255, 255)
        self.cell(0, 5, sanitize(f"SEO & GEO Auditor  |  {self.audience}"), align="L")
        self.ln(12)

    def footer(self):
        self.set_y(-12)
        self.set_draw_color(220, 220, 220)
        self.line(18, self.get_y(), self.w - 18, self.get_y())
        self.set_font("Helvetica", "", 7)
        self.set_text_color(130, 130, 130)
        self.cell(0, 8, sanitize(f"{self.doc_title}  -  Page {self.page_no()}"), align="C")

    def cover_page(self):
        self.add_page()
        self.set_fill_color(*NAVY)
        self.rect(0, 0, self.w, 95, style="F")
        self.set_fill_color(*BLUE)
        self.rect(0, 95, self.w, 3, style="F")

        self.set_xy(18, 28)
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(147, 197, 253)
        self.cell(0, 6, "CONNECTED MODE SETUP", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        self.set_x(18)
        self.set_font("Helvetica", "B", 22)
        self.set_text_color(255, 255, 255)
        self.multi_cell(self.w - 36, 10, sanitize(self.doc_title), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        self.ln(4)
        self.set_x(18)
        self.set_font("Helvetica", "", 11)
        self.set_text_color(226, 232, 240)
        self.multi_cell(self.w - 36, 6, sanitize(self.doc_subtitle), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        self.set_xy(18, 108)
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(*NAVY)
        self.cell(0, 6, sanitize(f"Audience: {self.audience}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        self.set_x(18)
        self.set_font("Helvetica", "", 9)
        self.set_text_color(*SLATE)
        self.cell(0, 5, sanitize(f"Document date: {date.today():%B %d, %Y}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(8)

    def section_h2(self, text: str):
        if self.get_y() > 250:
            self.add_page()
        self.ln(4)
        self.set_fill_color(*LIGHT_BG)
        self.set_draw_color(*BLUE)
        y = self.get_y()
        self.rect(18, y, self.w - 36, 9, style="F")
        self.line(18, y, 18, y + 9)
        self.set_line_width(1.2)
        self.line(18, y, 18, y + 9)
        self.set_line_width(0.2)
        self.set_xy(22, y + 2)
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(*NAVY)
        self.cell(0, 5, sanitize(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(3)

    def section_h3(self, text: str):
        self.ln(2)
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(*ACCENT)
        self.multi_cell(0, 5, sanitize(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(1)

    def body(self, text: str):
        self.set_font("Helvetica", "", 9.5)
        self.set_text_color(31, 41, 55)
        self.multi_cell(0, 5, sanitize(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(1)

    def bullet(self, text: str, checked: bool = False):
        self.set_font("Helvetica", "", 9.5)
        self.set_text_color(31, 41, 55)
        prefix = "[x]" if checked else "[ ]" if text.strip().startswith("[ ]") else "-"
        clean = text.strip()
        if clean.startswith("[ ]"):
            clean = clean[3:].strip()
        elif clean.startswith("[x]"):
            clean = clean[3:].strip()
        self.set_x(22)
        self.set_font("Helvetica", "B" if prefix == "[ ]" else "", 9.5)
        self.cell(6, 5, prefix)
        self.set_font("Helvetica", "", 9.5)
        self.multi_cell(0, 5, sanitize(clean), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    def numbered(self, num: str, text: str):
        self.set_font("Helvetica", "B", 9.5)
        self.set_text_color(*BLUE)
        self.set_x(22)
        self.cell(8, 5, f"{num}.")
        self.set_font("Helvetica", "", 9.5)
        self.set_text_color(31, 41, 55)
        self.multi_cell(0, 5, sanitize(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    def code_block(self, lines: list[str]):
        self.ln(1)
        h = max(8, 4.5 * len(lines) + 4)
        if self.get_y() + h > 275:
            self.add_page()
        y = self.get_y()
        self.set_fill_color(*CODE_BG)
        self.set_draw_color(203, 213, 225)
        self.rect(22, y, self.w - 40, h, style="DF")
        self.set_xy(25, y + 2)
        self.set_font("Courier", "", 8.5)
        self.set_text_color(30, 41, 59)
        for line in lines:
            self.set_x(25)
            self.cell(0, 4.5, sanitize(line), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(3)

    def render_table(self, rows: list[list[str]]):
        if not rows:
            return
        ncols = len(rows[0])
        avail = self.w - 36
        if ncols == 2:
            widths = (avail * 0.38, avail * 0.62)
        elif ncols == 3:
            widths = (avail * 0.22, avail * 0.39, avail * 0.39)
        else:
            widths = tuple([avail / ncols] * ncols)
        self.set_font("Helvetica", "", 8.5)
        with self.table(
            col_widths=widths,
            text_align="LEFT",
            line_height=5,
            first_row_as_headings=True,
            headings_style=FontFace(emphasis="BOLD", color=255, fill_color=NAVY),
            cell_fill_color=LIGHT_BG,
            cell_fill_mode="ROWS",
        ) as table:
            for row in rows:
                r = table.row()
                for cell in row:
                    r.cell(sanitize(cell))
        self.ln(4)

    def draw_roles_diagram(self):
        if self.get_y() + 55 > 275:
            self.add_page()
        y = self.get_y() + 2
        w = (self.w - 36 - 10) / 2
        h = 38
        boxes = [
            ("Tool operator (you)", ["Your Google Cloud project", "APIs + OAuth client", "PageSpeed API key", "Auditor app + .env"], (239, 246, 255), BLUE),
            ("Site owner (client)", ["Google Search Console", "Google Analytics 4", "Website", "Signs in once (OAuth)"], (236, 253, 245), (5, 150, 105)),
        ]
        for i, (title, lines, fill, border) in enumerate(boxes):
            x = 18 + i * (w + 10)
            self.set_fill_color(*fill)
            self.set_draw_color(*border)
            self.set_line_width(0.4)
            self.rect(x, y, w, h, style="DF")
            self.set_xy(x + 3, y + 3)
            self.set_font("Helvetica", "B", 9)
            self.set_text_color(*NAVY)
            self.cell(w - 6, 5, sanitize(title))
            self.set_font("Helvetica", "", 8)
            self.set_text_color(51, 65, 85)
            yy = y + 10
            for line in lines:
                self.set_xy(x + 4, yy)
                self.cell(w - 8, 4, sanitize(f"- {line}"))
                yy += 5
        mid_y = y + h / 2
        self.set_draw_color(*SLATE)
        self.set_line_width(0.3)
        self.line(18 + w, mid_y, 18 + w + 10, mid_y)
        self.set_font("Helvetica", "I", 7)
        self.set_text_color(*SLATE)
        self.set_xy(18 + w + 1, mid_y - 8)
        self.cell(8, 4, "OAuth", align="C")
        self.set_xy(18, y + h + 6)

    def draw_oauth_flow(self):
        steps = [
            "Enable APIs",
            "OAuth client",
            "Sign in",
            "Map site",
            "Run audit",
        ]
        if self.get_y() + 28 > 275:
            self.add_page()
        y = self.get_y() + 2
        avail = self.w - 36
        n = len(steps)
        gap = 6
        bw = (avail - gap * (n - 1)) / n
        self.set_auto_page_break(False)
        for i, label in enumerate(steps):
            x = 18 + i * (bw + gap)
            self.set_fill_color(239, 246, 255)
            self.set_draw_color(*BLUE)
            self.rect(x, y, bw, 16, style="DF")
            self.set_xy(x + 1, y + 5)
            self.set_font("Helvetica", "B", 7.5)
            self.set_text_color(*NAVY)
            self.multi_cell(bw - 2, 3.5, sanitize(label), align="C", new_x=XPos.LMARGIN, new_y=YPos.TOP)
            if i < n - 1:
                ax = x + bw
                self.set_draw_color(150, 150, 150)
                self.line(ax, y + 8, ax + gap, y + 8)
                self.line(ax + gap, y + 8, ax + gap - 1.5, y + 7)
                self.line(ax + gap, y + 8, ax + gap - 1.5, y + 9)
        self.set_auto_page_break(True, margin=18)
        self.set_xy(18, y + 22)


def is_sep_row(line: str) -> bool:
    body = line.strip().strip("|")
    return bool(body) and all(set(c.strip()) <= set("-: ") for c in body.split("|"))


def parse_table_row(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def build_pdf(src: Path, out: Path) -> None:
    lines = src.read_text(encoding="utf-8").splitlines()
    title = next((l[2:].strip() for l in lines if l.startswith("# ")), "Guide")
    subtitle = next((l[3:].strip() for l in lines if l.startswith("## ")), "")
    audience = "Site Owner" if "Site_Owner" in src.name else "Tool Operator"

    pdf = GuidePDF(title, subtitle, audience)
    pdf.cover_page()

    in_code = False
    code_buf: list[str] = []
    table_buf: list[list[str]] = []
    skip_title = True

    def flush_code():
        nonlocal in_code, code_buf
        if code_buf:
            pdf.code_block(code_buf)
            code_buf = []
        in_code = False

    def flush_table():
        nonlocal table_buf
        if table_buf:
            pdf.render_table(table_buf)
            table_buf = []

    for raw in lines:
        line = raw.rstrip()

        if line.strip().startswith("```"):
            if in_code:
                flush_code()
            else:
                flush_table()
                in_code = True
            continue
        if in_code:
            code_buf.append(line)
            continue

        if line.strip() == "[[FLOW:auth]]":
            flush_table()
            pdf.draw_oauth_flow()
            continue
        if line.strip() == "[[FLOW:roles]]":
            flush_table()
            pdf.draw_roles_diagram()
            continue

        if line.lstrip().startswith("|") and "|" in line.strip("|"):
            if is_sep_row(line):
                continue
            table_buf.append(parse_table_row(line))
            continue
        flush_table()

        if not line.strip():
            continue

        if line.startswith("# "):
            if skip_title:
                skip_title = False
                continue
            pdf.add_page()
            pdf.section_h2(line[2:].strip())
        elif line.startswith("## "):
            if skip_title:
                skip_title = False
                continue
            if "Who owns what" in line:
                pdf.section_h2(line[3:].strip())
                continue
            pdf.section_h2(line[3:].strip())
        elif line.startswith("### "):
            pdf.section_h3(line[4:].strip())
        elif line.strip() == "---":
            pdf.ln(2)
        elif re.match(r"^\d+\.\s", line.lstrip()):
            m = re.match(r"^(\d+)\.\s+(.*)", line.lstrip())
            if m:
                pdf.numbered(m.group(1), m.group(2))
        elif line.lstrip().startswith("- "):
            pdf.bullet(line.lstrip()[2:])
        elif line.lstrip().startswith("- [ ]") or line.lstrip().startswith("- [x]"):
            pdf.bullet(line.lstrip()[2:])
        elif line.strip().startswith("│") or line.strip().startswith("└") or line.strip().startswith("├"):
            continue  # skip ascii diagram lines
        elif line.strip().startswith("*") and line.strip().endswith("*"):
            pdf.set_font("Helvetica", "I", 8.5)
            pdf.set_text_color(*SLATE)
            pdf.multi_cell(0, 5, sanitize(line.strip().strip("*")), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.ln(1)
        else:
            pdf.body(line.strip())

    flush_code()
    flush_table()
    pdf.output(str(out))
    print("Wrote", out)


def main():
    src = Path(sys.argv[1]).expanduser() if len(sys.argv) > 1 else Path("Connected_Mode_Site_Owner_Guide.md")
    out = src.with_suffix(".pdf") if len(sys.argv) <= 2 else Path(sys.argv[2]).expanduser()
    build_pdf(src, out)


if __name__ == "__main__":
    main()
