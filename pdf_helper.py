from io import BytesIO
from pathlib import Path
from pypdf import PdfReader
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib import colors
from xml.sax.saxutils import escape
import os


def extract_pdf_text(path):
    reader = PdfReader(str(path))
    chunks = []
    for page in reader.pages[:150]:
        chunks.append(page.extract_text() or "")
    return "\n\n".join(chunks)


def _register_unicode_font():
    candidates = [
        os.getenv("PDF_FONT_PATH", ""),
        "assets/NotoSansDevanagari-Regular.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            try:
                pdfmetrics.registerFont(TTFont("LastAiUnicode", candidate))
                return "LastAiUnicode"
            except Exception:
                pass
    return "Helvetica"


def create_history_pdf(rows, title="Last-Ai Chat & Notes"):
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=18*mm, leftMargin=18*mm,
        topMargin=18*mm, bottomMargin=18*mm,
        title=title,
    )
    font_name = _register_unicode_font()
    styles = getSampleStyleSheet()
    heading = ParagraphStyle(
        "LastAiHeading", parent=styles["Heading1"],
        fontName=font_name, fontSize=16, leading=21,
        textColor=colors.HexColor("#263b68"), spaceAfter=12,
    )
    body = ParagraphStyle(
        "LastAiBody", parent=styles["BodyText"],
        fontName=font_name, fontSize=9, leading=13, spaceAfter=8,
        wordWrap="CJK",
    )
    small = ParagraphStyle(
        "LastAiSmall", parent=body, fontSize=7, leading=9,
        textColor=colors.grey,
    )
    story = [Paragraph(escape(title), heading)]
    if font_name == "Helvetica":
        story.append(Paragraph(
            "Note: Add a Unicode font such as NotoSansDevanagari-Regular.ttf to assets/ "
            "for correct Hindi/Devanagari rendering.", small
        ))
    for row in rows:
        role = "You" if row["role"] == "user" else "Last-Ai"
        meta = f"{role} · {row.get('feature', 'chat')} · {row.get('created_at', '')}"
        story.append(Paragraph(escape(meta), small))
        content = (row.get("content") or "").replace("\n", "<br/>")
        story.append(Paragraph(escape(content).replace("&lt;br/&gt;", "<br/>"), body))
        story.append(Spacer(1, 3))
    doc.build(story)
    return buffer.getvalue()
