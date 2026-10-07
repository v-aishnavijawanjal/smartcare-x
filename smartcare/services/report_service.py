from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func

from smartcare.extensions import db
from smartcare.models.appointment import Appointment, AppointmentStatus
from smartcare.models.billing import Bill
from smartcare.models.doctor import Doctor
from smartcare.models.patient import Patient
from smartcare.models.user import User


def _date_range(period, reference_date=None):
    reference_date = reference_date or date.today()
    if period == "daily":
        return reference_date, reference_date
    if period == "weekly":
        start = reference_date - timedelta(days=reference_date.weekday())
        return start, start + timedelta(days=6)
    if period == "monthly":
        start = reference_date.replace(day=1)
        next_month = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
        return start, next_month - timedelta(days=1)
    raise ValueError("period must be 'daily', 'weekly', or 'monthly'")


def appointment_report(period="daily", reference_date=None):
    start, end = _date_range(period, reference_date)
    appointments = (
        Appointment.query.filter(Appointment.appointment_date.between(start, end))
        .order_by(Appointment.appointment_date.asc())
        .all()
    )
    summary = {
        "period": period,
        "start": start,
        "end": end,
        "total": len(appointments),
        "approved": sum(1 for a in appointments if a.status == AppointmentStatus.APPROVED),
        "cancelled": sum(1 for a in appointments if a.status == AppointmentStatus.CANCELLED),
        "completed": sum(1 for a in appointments if a.status == AppointmentStatus.COMPLETED),
    }
    return summary, appointments


def revenue_report(period="monthly", reference_date=None):
    start, end = _date_range(period, reference_date)

    # Exclude voided bills from revenue calculations.
    bills = (
        Bill.query.filter(func.date(Bill.created_at).between(start, end))
        .filter(Bill.status != "void")
        .all()
    )

    total_billed = sum((b.total for b in bills), start=Decimal("0.00"))
    total_collected = sum((b.amount_paid for b in bills), start=Decimal("0.00"))

    return {
        "period": period,
        "start": start,
        "end": end,
        "bill_count": len(bills),
        "total_billed": total_billed,
        "total_collected": total_collected,
        "outstanding": total_billed - total_collected,
    }, bills


def doctor_performance_report(start_date=None, end_date=None):
    completed_case = db.case((Appointment.status == AppointmentStatus.COMPLETED, 1), else_=0)

    query = (
        db.session.query(
            Doctor.id,
            User.full_name,
            func.count(Appointment.id).label("total_appointments"),
            func.sum(completed_case).label("completed"),
        )
        .join(User, Doctor.user_id == User.id)
        .outerjoin(Appointment, Appointment.doctor_id == Doctor.id)
    )

    if start_date and end_date:
        query = query.filter(Appointment.appointment_date.between(start_date, end_date))

    return query.group_by(Doctor.id, User.full_name).order_by(func.count(Appointment.id).desc()).all()


def patient_statistics_report():
    total_patients = Patient.query.count()
    new_this_month = (
        Patient.query.join(User)
        .filter(func.date(User.created_at) >= date.today().replace(day=1))
        .count()
    )
    return {
        "total_patients": total_patients,
        "new_this_month": new_this_month,
    }