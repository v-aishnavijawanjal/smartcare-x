import io
import json
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

BRAND_PRIMARY = colors.HexColor("#789A99")   # Aqua Mist
BRAND_DARK = colors.HexColor("#233D4C")      # Charcoal

_styles = getSampleStyleSheet()
_title_style = ParagraphStyle(
    "SmartCareTitle", parent=_styles["Title"], textColor=BRAND_DARK, fontSize=20
)
_heading_style = ParagraphStyle(
    "SmartCareHeading", parent=_styles["Heading2"], textColor=BRAND_PRIMARY
)
_body_style = _styles["BodyText"]


def _document_header(elements, subtitle):
    elements.append(Paragraph("SmartCare X", _title_style))
    elements.append(Paragraph(subtitle, _heading_style))
    elements.append(
        Paragraph(
            f"Generated on {datetime.utcnow().strftime('%d %b %Y, %I:%M %p')} UTC",
            _body_style,
        )
    )
    elements.append(Spacer(1, 10 * mm))


def _base_table_style():
    return TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, 0), BRAND_DARK),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F5F5")]),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]
    )


def build_prescription_pdf(prescription):
    """Generate a prescription PDF."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=20 * mm, bottomMargin=20 * mm)
    elements = []

    _document_header(elements, "Prescription")

    patient_info = (
        f"<b>Patient:</b> {prescription.patient.full_name}<br/>"
        f"<b>Doctor:</b> Dr. {prescription.doctor.full_name} "
        f"({prescription.doctor.specialization or 'General'})<br/>"
        f"<b>Date:</b> {prescription.created_at.strftime('%d %b %Y')}"
    )
    elements.append(Paragraph(patient_info, _body_style))
    elements.append(Spacer(1, 6 * mm))

    if prescription.diagnosis:
        elements.append(Paragraph(f"<b>Diagnosis:</b> {prescription.diagnosis}", _body_style))
        elements.append(Spacer(1, 4 * mm))

    table_data = [["Medicine", "Dosage", "Frequency", "Duration"]]
    for item in prescription.items:
        table_data.append(
            [
                item.medicine.name,
                item.dosage or "-",
                item.frequency or "-",
                f"{item.duration_days} day(s)",
            ]
        )

    table = Table(table_data, colWidths=[55 * mm, 35 * mm, 55 * mm, 30 * mm])
    table.setStyle(_base_table_style())
    elements.append(table)

    if prescription.notes:
        elements.append(Spacer(1, 6 * mm))
        elements.append(Paragraph(f"<b>Notes:</b> {prescription.notes}", _body_style))

    doc.build(elements)
    return buffer.getvalue()


def build_bill_receipt_pdf(bill):
    """Generate a bill receipt PDF."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=20 * mm, bottomMargin=20 * mm)
    elements = []

    _document_header(elements, f"Payment Receipt — Bill #{bill.id}")

    elements.append(
        Paragraph(
            f"<b>Patient:</b> {bill.patient.full_name}<br/>"
            f"<b>Date:</b> {bill.created_at.strftime('%d %b %Y')}<br/>"
            f"<b>Status:</b> {bill.status.upper()}",
            _body_style,
        )
    )
    elements.append(Spacer(1, 6 * mm))

    table_data = [["Description", "Qty", "Unit Price", "Line Total"]]
    for item in bill.items:
        table_data.append(
            [item.description, str(item.quantity), f"₹{item.unit_price:.2f}", f"₹{item.line_total:.2f}"]
        )
    table = Table(table_data, colWidths=[75 * mm, 20 * mm, 35 * mm, 35 * mm])
    table.setStyle(_base_table_style())
    elements.append(table)
    elements.append(Spacer(1, 6 * mm))

    totals = (
        f"Subtotal: ₹{bill.subtotal:.2f}<br/>"
        f"Tax: ₹{bill.tax:.2f}<br/>"
        f"<b>Total: ₹{bill.total:.2f}</b><br/>"
        f"Paid: ₹{bill.amount_paid:.2f}<br/>"
        f"Balance Due: ₹{bill.balance_due:.2f}"
    )
    elements.append(Paragraph(totals, _body_style))

    doc.build(elements)
    return buffer.getvalue()


def build_tabular_report_pdf(title, headers, rows):
    """Generate a tabular PDF report."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=20 * mm, bottomMargin=20 * mm)
    elements = []

    _document_header(elements, title)

    table_data = [headers] + list(rows)
    table = Table(table_data, repeatRows=1)
    table.setStyle(_base_table_style())
    elements.append(table)

    doc.build(elements)
    return buffer.getvalue()


def build_generated_lab_report_pdf(report):
    """Generate a PDF from the report data stored in the database."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=20 * mm, bottomMargin=20 * mm)
    elements = []

    _document_header(elements, report.title)

    doctor_line = f"Dr. {report.doctor.full_name}" if report.doctor else "—"
    patient_info = (
        f"<b>Patient:</b> {report.patient.full_name}<br/>"
        f"<b>Ordered by:</b> {doctor_line}<br/>"
        f"<b>Report Date:</b> {report.uploaded_at.strftime('%d %b %Y')}"
    )
    elements.append(Paragraph(patient_info, _body_style))
    elements.append(Spacer(1, 6 * mm))

    payload = json.loads(report.results_json) if report.results_json else {}
    parameters = payload.get("parameters", [])
    interpretation = payload.get("interpretation")

    table_data = [["Parameter", "Result", "Reference Range", "Unit"]]
    for param in parameters:
        table_data.append(
            [
                param.get("parameter_name", "-"),
                param.get("result_value", "-"),
                param.get("reference_range") or "-",
                param.get("unit_label") or "-",
            ]
        )

    table = Table(table_data, colWidths=[55 * mm, 35 * mm, 45 * mm, 25 * mm], repeatRows=1)
    table.setStyle(_base_table_style())
    elements.append(table)

    if interpretation:
        elements.append(Spacer(1, 6 * mm))
        elements.append(Paragraph(f"<b>Interpretation:</b> {interpretation}", _body_style))

    elements.append(Spacer(1, 10 * mm))
    elements.append(
        Paragraph(
            "This report is generated from the patient's recorded test results.",
            ParagraphStyle("Small", parent=_body_style, fontSize=8, textColor=colors.grey),
        )
    )

    doc.build(elements)
    return buffer.getvalue()