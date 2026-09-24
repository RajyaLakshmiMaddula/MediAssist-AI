"""
report.py
---------
Builds the downloadable consultation report with ReportLab.

The PDF is generated in memory and streamed to the browser, so nothing is
written to disk unless the user saves it.
"""

from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (HRFlowable, ListFlowable, ListItem, PageBreak,
                                Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

INK = colors.HexColor("#0E2A33")
PULSE = colors.HexColor("#0F8F72")
MUTED = colors.HexColor("#5C7078")
RULE = colors.HexColor("#C9D6D3")
ALERT = colors.HexColor("#A6332B")


def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("t", parent=base["Title"], fontName="Helvetica-Bold",
                                fontSize=20, textColor=INK, spaceAfter=2, alignment=0),
        "tagline": ParagraphStyle("tg", parent=base["Normal"], fontSize=9,
                                  textColor=MUTED, spaceAfter=10),
        "h2": ParagraphStyle("h2", parent=base["Heading2"], fontName="Helvetica-Bold",
                             fontSize=11.5, textColor=INK, spaceBefore=14, spaceAfter=6),
        "body": ParagraphStyle("b", parent=base["Normal"], fontSize=9.5,
                               leading=14, textColor=INK),
        "muted": ParagraphStyle("m", parent=base["Normal"], fontSize=8.5,
                                leading=12, textColor=MUTED),
        "bullet": ParagraphStyle("bu", parent=base["Normal"], fontSize=9.5,
                                 leading=13.5, textColor=INK),
        "alert": ParagraphStyle("al", parent=base["Normal"], fontSize=9.5,
                                leading=13.5, textColor=ALERT),
        "footer": ParagraphStyle("f", parent=base["Normal"], fontSize=7.5,
                                 textColor=MUTED, alignment=TA_CENTER, leading=10),
    }


def _bullets(items, style, marker="•"):
    if not items:
        items = ["Not applicable"]
    return ListFlowable(
        [ListItem(Paragraph(str(i), style), leftIndent=10) for i in items],
        bulletType="bullet", start=marker, leftIndent=12,
        # bulletOffsetY nudges the glyph down onto the text baseline; without it
        # ReportLab hangs small bullets off the ascender line.
        bulletFontSize=9, bulletColor=PULSE, bulletOffsetY=-1.5,
    )


def _rule(space_before=4, space_after=4):
    return HRFlowable(width="100%", thickness=0.6, color=RULE,
                      spaceBefore=space_before, spaceAfter=space_after)


def build_report(consultation, user) -> BytesIO:
    """Render a consultation to a PDF and return the buffer."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=16 * mm, bottomMargin=16 * mm,
        title=f"MediAssist Report {consultation.reference}",
        author="MediAssist AI",
    )
    s = _styles()
    story = []

    # -- Header ------------------------------------------------------------
    story.append(Paragraph("MediAssist AI", s["title"]))
    story.append(Paragraph("Consultation summary &mdash; symptom analysis for guidance, "
                           "not a medical diagnosis", s["tagline"]))
    story.append(_rule(0, 10))

    meta = [
        ["Patient", user.name, "Reference", consultation.reference],
        ["Age", str(consultation.age or "—"), "Date",
         consultation.created_at.strftime("%d %b %Y, %H:%M")],
        ["Gender", consultation.gender or "—", "Reported severity",
         consultation.severity or "—"],
        ["Duration", consultation.duration or "—", "Department",
         consultation.department or "—"],
    ]
    table = Table(meta, colWidths=[26 * mm, 52 * mm, 32 * mm, 54 * mm])
    table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (0, -1), MUTED),
        ("TEXTCOLOR", (2, 0), (2, -1), MUTED),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica-Bold"),
        ("FONTNAME", (3, 0), (3, -1), "Helvetica-Bold"),
        ("TEXTCOLOR", (1, 0), (1, -1), INK),
        ("TEXTCOLOR", (3, 0), (3, -1), INK),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(table)
    story.append(_rule(10, 2))

    # -- Reported complaint ------------------------------------------------
    story.append(Paragraph("Reported complaint", s["h2"]))
    story.append(Paragraph(consultation.symptoms_text, s["body"]))

    if consultation.symptom_list:
        story.append(Spacer(1, 6))
        story.append(Paragraph(
            "<b>Symptoms identified:</b> " + ", ".join(consultation.symptom_list), s["muted"]))
    if consultation.denied_list:
        story.append(Paragraph(
            "<b>Ruled out by the patient:</b> " + ", ".join(consultation.denied_list), s["muted"]))

    # -- Assessment --------------------------------------------------------
    story.append(Paragraph("Assessment", s["h2"]))
    conf = consultation.confidence or 0
    assess = Table(
        [[Paragraph(f"<b>{consultation.disease or 'No clear match'}</b>", s["body"]),
          Paragraph(f"<b>{conf:.0f}%</b> match", s["body"])]],
        colWidths=[118 * mm, 46 * mm],
    )
    assess.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#EEF5F3")),
        ("BOX", (0, 0), (-1, -1), 0.6, RULE),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
    ]))
    story.append(assess)

    if consultation.urgency:
        story.append(Spacer(1, 7))
        story.append(Paragraph(f"<b>Suggested next step:</b> {consultation.urgency}", s["body"]))

    differentials = consultation.differential_list
    if len(differentials) > 1:
        story.append(Spacer(1, 8))
        story.append(Paragraph("Other conditions considered", s["h2"]))
        rows = [[d.get("name", ""), f"{d.get('confidence', 0):.0f}%"] for d in differentials[1:]]
        alt = Table(rows, colWidths=[134 * mm, 30 * mm])
        alt.setStyle(TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("TEXTCOLOR", (0, 0), (-1, -1), INK),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("LINEBELOW", (0, 0), (-1, -2), 0.4, RULE),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(alt)

    # -- Care plan ---------------------------------------------------------
    story.append(Paragraph("Over-the-counter guidance", s["h2"]))
    story.append(_bullets(consultation.medication_list, s["bullet"]))

    story.append(Paragraph("Foods to include", s["h2"]))
    story.append(_bullets(consultation.eat_list, s["bullet"]))

    story.append(Paragraph("Foods to avoid", s["h2"]))
    story.append(_bullets(consultation.avoid_list, s["bullet"]))

    story.append(Paragraph("Precautions", s["h2"]))
    story.append(_bullets(consultation.precaution_list, s["bullet"]))

    story.append(Paragraph("See a doctor immediately if", s["h2"]))
    story.append(_bullets(consultation.warning_list, s["alert"]))

    # -- Disclaimer --------------------------------------------------------
    story.append(Spacer(1, 14))
    story.append(_rule(0, 8))
    story.append(Paragraph(
        "This report was produced by an automated symptom-matching program for educational "
        "purposes. It is not a medical diagnosis and it has not been reviewed by a clinician. "
        "It cannot examine you, order tests, or account for your medical history and current "
        "medication. Use it to prepare for a consultation, never to replace one. If your "
        "symptoms are severe, worsening, or you are worried, contact a doctor or your local "
        "emergency service.", s["muted"]))

    def footer(canvas, document):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawCentredString(
            A4[0] / 2, 10 * mm,
            f"MediAssist AI  ·  {consultation.reference}  ·  Page {document.page}  ·  "
            f"Not a substitute for professional medical advice")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    buffer.seek(0)
    return buffer
