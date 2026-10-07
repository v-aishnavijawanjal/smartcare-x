from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from smartcare.extensions import db
from smartcare.models.billing import BILL_DUE_DAYS, Bill, BillItem, Payment

DEFAULT_TAX_RATE = Decimal("0.05")


def _round2(value):
    return Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def create_bill(patient_id, generated_by_user_id, line_items, appointment_id=None, prescription_id=None, tax_rate=DEFAULT_TAX_RATE, with_due_date=False, channel="counter"):
    bill = Bill(
        patient_id=patient_id,
        appointment_id=appointment_id,
        prescription_id=prescription_id,
        generated_by=generated_by_user_id,
        channel=channel,
    )
    if with_due_date:
        bill.due_date = datetime.utcnow() + timedelta(days=BILL_DUE_DAYS)

    subtotal = Decimal("0.00")
    for line in line_items:
        quantity = int(line["quantity"])
        unit_price = Decimal(str(line["unit_price"]))
        line_total = _round2(unit_price * quantity)
        subtotal += line_total

        bill.items.append(
            BillItem(
                description=line["description"],
                quantity=quantity,
                unit_price=unit_price,
                line_total=line_total,
            )
        )

    tax = _round2(subtotal * tax_rate)
    bill.subtotal = subtotal
    bill.tax = tax
    bill.total = subtotal + tax
    bill.status = "unpaid"

    db.session.add(bill)
    db.session.commit()
    return bill


def record_payment(bill, amount, method="cash"):
    payment = Payment(amount=_round2(amount), method=method)

    # Add payment through the relationship to keep the bill state in sync.
    bill.payments.append(payment)

    db.session.add(payment)
    db.session.flush()

    if bill.balance_due <= Decimal("0.00"):
        bill.status = "paid"
    elif bill.amount_paid > Decimal("0.00"):
        bill.status = "partial"

    db.session.commit()
    return payment


def mark_refund_pending(appointment):
    """Update the bill status when an appointment is cancelled or rejected."""
    bill = appointment.bill
    if not bill:
        return

    if bill.status == "paid":
        bill.status = "refund_pending"
    elif bill.status in ("unpaid", "partial"):
        bill.status = "void"

    db.session.commit()


def mark_bill_refunded(bill):
    """Mark a bill as refunded after manual confirmation."""
    bill.status = "refunded"
    db.session.commit()


def get_unpaid_bills(patient_id=None, channel=None):
    """Return unpaid or partially paid bills."""
    query = Bill.query.filter(Bill.status.in_(["unpaid", "partial"]))
    if patient_id:
        query = query.filter_by(patient_id=patient_id)
    if channel:
        query = query.filter_by(channel=channel)
    return query.order_by(Bill.created_at.desc()).all()


def get_receptionist_unpaid_bills():
    """Return unpaid counter bills for reception."""
    return (
        Bill.query.filter(Bill.status.in_(["unpaid", "partial"]))
        .filter_by(channel="counter")
        .order_by(Bill.created_at.desc())
        .all()
    )


def get_refund_pending_bills(patient_id=None):
    query = Bill.query.filter_by(status="refund_pending")
    if patient_id:
        query = query.filter_by(patient_id=patient_id)
    return query.order_by(Bill.created_at.desc()).all()


def get_bills_needing_reminder():
    """Return bills that are due for a payment reminder."""
    cutoff = datetime.utcnow() + timedelta(days=1)
    return (
        Bill.query.filter(Bill.status.in_(["unpaid", "partial"]))
        .filter(Bill.due_date.isnot(None))
        .filter(Bill.due_date <= cutoff)
        .filter(Bill.reminder_sent.is_(False))
        .all()
    )


def mark_reminder_sent(bill):
    bill.reminder_sent = True
    db.session.commit()