"""
Notes as a formatted PDF. ReportLab is the main library; fpdf2 is used if ReportLab is not there. If neither
is installed, one attempt is made to install ReportLab with the pip of the Python that is running the server
(so it lands in the same virtual environment), and a clear error is returned if that does not work.
"""
import importlib
import io
import subprocess
import sys
from pathlib import Path
from xml.sax.saxutils import escape

from ..core.errors import ApiError
from ..core.logging import log
from ..schemas.ai import GeneratedNotes

# a Unicode font if the machine has one; otherwise the built-in font with the text reduced to what it can print
FONTS = [
    ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ("/System/Library/Fonts/Supplemental/Arial.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
]
PLAIN = {"→": "->", "←": "<-", "—": "-", "–": "-", "•": "-", "“": '"', "”": '"', "‘": "'", "’": "'", "…": "...", "×": "x", "÷": "/", "≤": "<=", "≥": ">=", "≠": "!=", "−": "-"}
# characters the Unicode fonts above do not have either: arrows, and the special hyphens and spaces models like to use
ARROWS = {"→": "->", "←": "<-", "‑": "-", "‐": "-", " ": " ", " ": " ", "−": "-"}

INK, BROWN, SOFT, GOLD, RULE = (60, 45, 35), (122, 75, 34), (138, 117, 96), (251, 227, 161), (236, 213, 150)
_install_tried = False


def _fonts() -> tuple[str, str] | None:
    return next(((r, b) for r, b in FONTS if Path(r).exists() and Path(b).exists()), None)


def _text(text, unicode_font: bool) -> str:
    text = str(text)
    for a, b in (ARROWS if unicode_font else {**ARROWS, **PLAIN}).items():
        text = text.replace(a, b)
    return text if unicode_font else text.encode("latin-1", "replace").decode("latin-1")


def blocks(notes: GeneratedNotes, file_name: str) -> list[tuple]:
    """The notes as a flat list the renderers walk: ("title"|"meta"|"heading", text) and ("line", text, indent, bold)."""
    out: list[tuple] = [("title", notes.title), ("meta", f"Revision notes from {file_name}"), ("heading", "Headings & Subheadings")]
    for h in notes.outline:
        out.append(("line", h.heading, 0, True))
        out += [("line", f"- {s}", 1, False) for s in h.subheadings]
    out.append(("heading", "Definitions"))
    out += [("pair", d.term, d.definition) for d in notes.definitions]
    out += [("heading", "Summary"), ("line", notes.summary, 0, False), ("heading", "Must-Know Keywords")]
    out += [("pair", k.keyword, k.meaning) for k in notes.keywords]
    out.append(("heading", "Key Points"))
    out += [("line", f"- {p}", 0, False) for p in notes.key_points]
    out += [("heading", "Topic Weightage"), ("pair", notes.weightage.level, notes.weightage.reason), ("heading", "Concept Hierarchy")]
    for c in notes.hierarchy:
        out.append(("line", c.concept, 0, True))
        for s in c.children:
            out.append(("line", f"→ {s.concept}", 1, False))
            out += [("line", f"→ {d}", 2, False) for d in s.details]
    out.append(("heading", "Core Concepts"))
    out += [("pair", c.concept, c.explanation) for c in notes.core_concepts]
    out.append(("heading", "Potential Questions"))
    out += [("line", f"{i}. {q}", 0, False) for i, q in enumerate(notes.potential_questions, 1)]
    out.append(("heading", "Brief Summary"))
    out += [("line", f"- {b}", 0, False) for b in notes.brief_summary]
    return out


def _reportlab(items: list[tuple]) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer

    regular, bold = "Helvetica", "Helvetica-Bold"
    found = _fonts()
    if found:
        if "HamstarNotes" not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont("HamstarNotes", found[0]))
            pdfmetrics.registerFont(TTFont("HamstarNotes-Bold", found[1]))
        regular, bold = "HamstarNotes", "HamstarNotes-Bold"
    rgb = lambda c: colors.Color(*[v / 255 for v in c])  # noqa: E731
    t = lambda s: escape(_text(s, bool(found)))  # noqa: E731

    body = ParagraphStyle("body", fontName=regular, fontSize=10.5, leading=15, textColor=rgb(INK), spaceAfter=3)
    styles = {
        "title": ParagraphStyle("title", fontName=bold, fontSize=20, leading=25, textColor=rgb((70, 41, 27)), spaceAfter=2),
        "meta": ParagraphStyle("meta", fontName=regular, fontSize=9, leading=12, textColor=rgb(SOFT), spaceAfter=6),
        "heading": ParagraphStyle("heading", fontName=bold, fontSize=13, leading=17, textColor=rgb(BROWN), spaceBefore=10, spaceAfter=2, keepWithNext=True),
    }
    story = []
    for item in items:
        kind = item[0]
        if kind == "heading":
            story += [Paragraph(t(item[1]), styles["heading"]), HRFlowable(width="100%", thickness=0.8, color=rgb(RULE), spaceAfter=5)]
        elif kind in styles:
            story.append(Paragraph(t(item[1]), styles[kind]))
        elif kind == "pair":
            story.append(Paragraph(f'<font name="{bold}">{t(item[1])}:</font> {t(item[2])}', body))
        else:
            _, text, indent, strong = item
            story.append(Paragraph(t(text), ParagraphStyle("line", parent=body, fontName=bold if strong else regular, leftIndent=indent * 6 * mm)))
    story.append(Spacer(1, 4 * mm))

    def page(canvas, doc):
        w, h = A4
        canvas.saveState()
        if doc.page == 1:  # HamSTAR branding across the top of the first page
            canvas.setFillColor(rgb(GOLD))
            canvas.rect(0, h - 16 * mm, w, 16 * mm, stroke=0, fill=1)
            canvas.setFillColor(rgb((70, 41, 27)))
            canvas.setFont(bold, 13)
            canvas.drawString(18 * mm, h - 10.5 * mm, "HamSTAR")
            canvas.setFont(regular, 9)
            canvas.setFillColor(rgb(BROWN))
            canvas.drawRightString(w - 18 * mm, h - 10.5 * mm, _text("Think · Explain · Grow", bool(found)))
        canvas.setFont(regular, 8)
        canvas.setFillColor(rgb(SOFT))
        canvas.drawCentredString(w / 2, 10 * mm, f"HamSTAR notes · page {doc.page}")
        canvas.restoreState()

    buffer = io.BytesIO()
    SimpleDocTemplate(buffer, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=24 * mm, bottomMargin=18 * mm, title=items[0][1], author="HamSTAR").build(story, onFirstPage=page, onLaterPages=page)
    return buffer.getvalue()


def _fpdf(items: list[tuple]) -> bytes:
    from fpdf import FPDF

    doc = FPDF(format="A4")
    doc.set_auto_page_break(True, margin=18)
    doc.set_margins(18, 18, 18)
    family, found = "Helvetica", _fonts()
    if found:
        doc.add_font("Notes", "", found[0])
        doc.add_font("Notes", "B", found[1])
        family = "Notes"
    t = lambda s: _text(s, bool(found))  # noqa: E731

    def line(text: str, size: float = 10.5, bold: bool = False, indent: float = 0, gap: float = 1.5, color=INK):
        doc.set_font(family, "B" if bold else "", size)
        doc.set_text_color(*color)
        doc.set_x(doc.l_margin + indent)
        doc.multi_cell(doc.w - doc.l_margin - doc.r_margin - indent, size * 0.5, t(text), new_x="LMARGIN", new_y="NEXT")
        doc.ln(gap)

    doc.add_page()
    doc.set_fill_color(*GOLD)
    doc.rect(0, 0, doc.w, 16, style="F")
    doc.set_xy(doc.l_margin, 4.5)
    doc.set_font(family, "B", 13)
    doc.set_text_color(70, 41, 27)
    doc.cell(60, 7, "HamSTAR")
    doc.set_font(family, "", 9)
    doc.set_text_color(*BROWN)
    doc.cell(doc.w - doc.l_margin - doc.r_margin - 60, 7, t("Think · Explain · Grow"), align="R")
    doc.set_xy(doc.l_margin, 24)
    for item in items:
        kind = item[0]
        if kind == "title":
            line(item[1], 20, bold=True, gap=1, color=(70, 41, 27))
        elif kind == "meta":
            line(item[1], 9, gap=3, color=SOFT)
        elif kind == "heading":
            doc.ln(3)
            line(item[1], 13, bold=True, gap=1, color=BROWN)
            doc.set_draw_color(*RULE)
            doc.line(doc.l_margin, doc.get_y(), doc.w - doc.r_margin, doc.get_y())
            doc.ln(2.5)
        elif kind == "pair":
            line(f"{item[1]}: {item[2]}")
        else:
            line(item[1], bold=item[3], indent=item[2] * 6, gap=0.5 if item[2] or item[3] else 1.5)
    return bytes(doc.output())


def _available() -> str | None:
    for module, name in (("reportlab", "reportlab"), ("fpdf", "fpdf2")):
        try:
            importlib.import_module(module)
            return name
        except ImportError:
            continue
    return None


def _install() -> None:
    """One attempt, with the running interpreter's own pip, so the package goes into this virtual environment."""
    global _install_tried
    if _install_tried:
        return
    _install_tried = True
    log.warning("No PDF library found; installing reportlab with %s -m pip", sys.executable)
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "reportlab>=4.0"], check=True, timeout=180, capture_output=True)
        importlib.invalidate_caches()
    except (subprocess.SubprocessError, OSError) as e:
        log.error("Installing reportlab failed: %s", type(e).__name__)


def library() -> str | None:
    """Which PDF library will be used: "reportlab", "fpdf2", or None if neither can be loaded."""
    return _available()


def render(notes: GeneratedNotes, file_name: str) -> bytes:
    name = _available()
    if name is None:
        _install()
        name = _available()
    if name is None:
        raise ApiError("PDF_UNAVAILABLE", f'PDF export could not be set up automatically. In the backend\'s virtual environment run: "{sys.executable}" -m pip install reportlab', 503)
    items = blocks(notes, file_name)
    try:
        return _reportlab(items) if name == "reportlab" else _fpdf(items)
    except ImportError:
        return _fpdf(items)
