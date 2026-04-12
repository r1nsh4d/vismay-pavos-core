import io
from datetime import datetime
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_CENTER
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side


# ── Excel ──────────────────────────────────────────────────────────────────────

def generate_excel(rows: list[dict], sheet_name: str = "Report") -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet_name[:31]  # Excel sheet name max 31 chars

    if not rows:
        ws.append(["No data available"])
        buf = io.BytesIO()
        wb.save(buf)
        return buf.getvalue()

    headers = list(rows[0].keys())

    header_fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF", size=11)
    header_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    thin_border = Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        top=Side(style="thin"),
        bottom=Side(style="thin"),
    )

    # Write headers
    for col_idx, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = header_alignment
        cell.border = thin_border

    # Write data rows
    for row_idx, row in enumerate(rows, 2):
        fill = PatternFill(
            start_color="EBF3FB" if row_idx % 2 == 0 else "FFFFFF",
            end_color="EBF3FB" if row_idx % 2 == 0 else "FFFFFF",
            fill_type="solid",
        )
        for col_idx, header in enumerate(headers, 1):
            value = row.get(header, "")
            # Convert None to empty string
            if value is None:
                value = ""
            cell = ws.cell(row=row_idx, column=col_idx, value=value)
            cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=False)
            cell.border = thin_border
            cell.fill = fill

    # Auto column width
    for col in ws.columns:
        max_length = max((len(str(cell.value or "")) for cell in col), default=10)
        ws.column_dimensions[col[0].column_letter].width = min(max_length + 4, 45)

    # Row height for header
    ws.row_dimensions[1].height = 25

    # Freeze header row
    ws.freeze_panes = "A2"

    # Add generated timestamp in a metadata sheet
    meta_ws = wb.create_sheet("Info")
    meta_ws.append(["Generated At", datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
    meta_ws.append(["Total Rows", len(rows)])
    meta_ws.append(["Sheet", sheet_name])

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ── PDF ────────────────────────────────────────────────────────────────────────

def generate_pdf(rows: list[dict], title: str = "Report") -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=landscape(A4),
        rightMargin=1 * cm,
        leftMargin=1 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
    )

    styles = getSampleStyleSheet()
    subtitle_style = ParagraphStyle(
        "Subtitle",
        parent=styles["Normal"],
        fontSize=8,
        textColor=colors.HexColor("#666666"),
        alignment=TA_CENTER,
    )
    cell_style = ParagraphStyle(
        "Cell",
        parent=styles["Normal"],
        fontSize=6.5,
        leading=8,
    )

    elements = []

    # Title + timestamp
    elements.append(Paragraph(title, styles["Title"]))
    elements.append(Paragraph(
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        subtitle_style,
    ))
    elements.append(Spacer(1, 0.5 * cm))

    if not rows:
        elements.append(Paragraph("No data available for the selected filters.", styles["Normal"]))
        doc.build(elements)
        return buf.getvalue()

    headers = list(rows[0].keys())
    page_width = landscape(A4)[0] - 2 * cm
    col_width = page_width / len(headers)

    # Wrap cell text using Paragraph for long content
    table_data = [[Paragraph(f"<b>{h}</b>", cell_style) for h in headers]]
    for row in rows:
        table_data.append([
            Paragraph(str(row.get(h, "") or ""), cell_style)
            for h in headers
        ])

    table = Table(
        table_data,
        colWidths=[col_width] * len(headers),
        repeatRows=1,
    )

    table.setStyle(TableStyle([
        # Header background
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E79")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        # Alternating row backgrounds
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [
            colors.white,
            colors.HexColor("#EBF3FB"),
        ]),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("ALIGN", (0, 1), (-1, -1), "LEFT"),
        # Grid
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CCCCCC")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))

    elements.append(table)

    # Footer with page numbers
    def add_page_number(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#999999"))
        page_text = f"Page {doc.page}"
        canvas.drawRightString(
            landscape(A4)[0] - 1 * cm,
            0.75 * cm,
            page_text,
        )
        canvas.drawString(
            1 * cm,
            0.75 * cm,
            f"{title} — {datetime.now().strftime('%Y-%m-%d')}",
        )
        canvas.restoreState()

    doc.build(elements, onFirstPage=add_page_number, onLaterPages=add_page_number)
    return buf.getvalue()