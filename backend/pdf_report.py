"""Generate a clean, styled PDF review report using ReportLab."""
import io
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def _score_hex(val: int) -> colors.Color:
    if val >= 75:
        return colors.HexColor("#16a34a")
    if val >= 55:
        return colors.HexColor("#d97706")
    return colors.HexColor("#dc2626")


def build_pdf_report(report: dict, user_name: str = "") -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=f"DocReview Report - {report.get('filename', 'Document')}",
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Heading1"],
        fontSize=20,
        textColor=colors.HexColor("#1e1b4b"),
        spaceAfter=4,
    )
    sub_style = ParagraphStyle(
        "Sub",
        parent=styles["Normal"],
        fontSize=10,
        textColor=colors.HexColor("#6b7280"),
        spaceAfter=14,
    )
    h2_style = ParagraphStyle(
        "H2",
        parent=styles["Heading2"],
        fontSize=13,
        textColor=colors.HexColor("#312e81"),
        spaceBefore=12,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "Body",
        parent=styles["Normal"],
        fontSize=9.5,
        leading=13.5,
        textColor=colors.HexColor("#1f2937"),
        spaceAfter=6,
    )
    small_style = ParagraphStyle(
        "Small",
        parent=styles["Normal"],
        fontSize=8.5,
        leading=11.5,
        textColor=colors.HexColor("#4b5563"),
        spaceAfter=4,
    )

    story = []

    # Header
    story.append(Paragraph("DocReview AI — Quality &amp; Language Audit Report", title_style))
    meta_parts = [
        f"File: <b>{escape(report.get('filename', 'document'))}</b>",
        f"Pages: {report.get('pages', 1)}",
        f"Words: {report.get('wordCount', 0):,}",
        f"Overall Score: <b>{report.get('score', 0)}/100</b>",
    ]
    if report.get("ocrUsed"):
        meta_parts.append("OCR: Enabled (Scanned PDF)")
    if user_name:
        meta_parts.append(f"Reviewer: {escape(user_name)}")
    story.append(Paragraph(" &nbsp;|&nbsp; ".join(meta_parts), sub_style))

    # Breakdown Table
    story.append(Paragraph("1. Score Breakdown", h2_style))
    table_data = [["Metric", "Score (/100)", "Status"]]
    for item in report.get("breakdown", []):
        val = int(item.get("value", 0))
        status = "Strong" if val >= 75 else ("Needs Polish" if val >= 55 else "Needs Attention")
        table_data.append([item.get("label", ""), f"{val}", status])

    tbl = Table(table_data, colWidths=[75 * mm, 35 * mm, 60 * mm])
    tbl_style = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4f46e5")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f9fafb")]),
    ]
    for row_idx, item in enumerate(report.get("breakdown", []), start=1):
        tbl_style.append(("TEXTCOLOR", (2, row_idx), (2, row_idx), _score_hex(int(item.get("value", 0)))))
        tbl_style.append(("FONTNAME", (2, row_idx), (2, row_idx), "Helvetica-Bold"))
    tbl.setStyle(TableStyle(tbl_style))
    story.append(tbl)
    story.append(Spacer(1, 6))

    # Summary
    story.append(Paragraph("2. Executive Summary", h2_style))
    story.append(Paragraph(escape(report.get("summary") or "No summary available."), body_style))

    # Sections
    story.append(Paragraph("3. Structural Sections Check", h2_style))
    sec_text = ", ".join(
        f"{escape(s['name'])} ({'Found' if s['found'] else 'Missing'})"
        for s in report.get("sections", [])
    )
    story.append(Paragraph(sec_text or "None checked.", body_style))

    # Capitalization
    cap = report.get("capitalization", {})
    story.append(
        Paragraph(
            f"4. Capitalization Check (Score: {cap.get('score', 0)}/100 · {cap.get('totalIssues', 0)} issue(s))",
            h2_style,
        )
    )
    if not cap.get("issues"):
        story.append(Paragraph("No capitalization errors detected.", body_style))
    else:
        for iss in cap["issues"][:8]:
            story.append(
                Paragraph(
                    f"• <b>[{escape(iss['category'])}]</b> {escape(iss['snippet'])} — <i>{escape(iss['advice'])}</i>",
                    small_style,
                )
            )

    # Grammar
    gram = report.get("grammar", {})
    story.append(
        Paragraph(
            f"5. Grammar &amp; Style Check (Score: {gram.get('score', 0)}/100 · {gram.get('totalIssues', 0)} issue(s))",
            h2_style,
        )
    )
    if not gram.get("issues"):
        story.append(Paragraph("No major grammar issues detected.", body_style))
    else:
        for iss in gram["issues"][:10]:
            story.append(
                Paragraph(
                    f"• <b>[{escape(iss['category'])}]</b> {escape(iss['snippet'])} — <i>{escape(iss['advice'])}</i>",
                    small_style,
                )
            )

    # Citations
    cit = report.get("citations", {})
    story.append(
        Paragraph(
            f"6. Citation &amp; Reference Audit (Score: {cit.get('score', 0)}/100)",
            h2_style,
        )
    )
    story.append(
        Paragraph(
            f"Detected Style: <b>{escape(cit.get('style', 'None'))}</b> &nbsp;|&nbsp; "
            f"Inline Citations: <b>{cit.get('inlineCount', 0)}</b> &nbsp;|&nbsp; "
            f"Reference Entries: <b>{cit.get('referenceCount', 0)}</b>",
            body_style,
        )
    )
    if cit.get("unmatchedCitations"):
        story.append(
            Paragraph(
                f"Unmatched inline citations: <b>{escape(', '.join(cit['unmatchedCitations']))}</b>",
                small_style,
            )
        )

    # Suggestions
    story.append(Paragraph("7. Actionable Recommendations", h2_style))
    for s in report.get("suggestions", []):
        story.append(Paragraph(f"• {escape(s.get('text', ''))}", body_style))

    doc.build(story)
    return buf.getvalue()
