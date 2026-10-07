from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func

from smartcare.extensions import db
from smartcare.models.appointment import Appointment, AppointmentStatus
from smartcare.models.billing import Bill
from smartcare.models.department import Department
from smartcare.models.doctor import Doctor
from smartcare.models.patient import Patient


def dashboard_kpis():
    # Exclude voided bills from revenue.
    total_revenue = (
        db.session.query(func.coalesce(func.sum(Bill.total), 0))
        .filter(Bill.status != "void")
        .scalar()
    )
    return {
        "total_patients": Patient.query.count(),
        "total_doctors": Doctor.query.count(),
        "total_appointments": Appointment.query.count(),
        "total_revenue": Decimal(total_revenue or 0),
        "total_departments": Department.query.count(),
    }


def appointments_last_n_days_chart(n=14):
    start = date.today() - timedelta(days=n - 1)
    rows = (
        db.session.query(Appointment.appointment_date, func.count(Appointment.id))
        .filter(Appointment.appointment_date >= start)
        .group_by(Appointment.appointment_date)
        .order_by(Appointment.appointment_date.asc())
        .all()
    )
    counts_by_date = {d: int(c) for d, c in rows}

    labels, data = [], []
    for i in range(n):
        day = start + timedelta(days=i)
        labels.append(day.strftime("%d %b"))
        data.append(int(counts_by_date.get(day, 0)))

    return {"labels": labels, "data": data}


def appointment_status_breakdown_chart():
    rows = (
        db.session.query(Appointment.status, func.count(Appointment.id))
        .group_by(Appointment.status)
        .all()
    )
    return {
        "labels": [str(status.value).title() for status, _ in rows],
        "data": [int(count) for _, count in rows],
    }


def revenue_last_n_months_chart(n=6):
    today = date.today()
    labels, data = [], []
    for i in range(n - 1, -1, -1):
        year = today.year
        month = today.month - i
        while month <= 0:
            month += 12
            year -= 1
        month_total = (
            db.session.query(func.coalesce(func.sum(Bill.total), 0))
            .filter(func.extract("year", Bill.created_at) == year, func.extract("month", Bill.created_at) == month)
            .filter(Bill.status != "void")
            .scalar()
        )
        labels.append(date(year, month, 1).strftime("%b %Y"))
        data.append(float(month_total or 0))

    return {"labels": labels, "data": data}


def department_distribution_chart():
    rows = (
        db.session.query(Department.name, func.count(Doctor.id))
        .outerjoin(Doctor, Doctor.department_id == Department.id)
        .group_by(Department.name)
        .all()
    )
    return {"labels": [str(name) for name, _ in rows], "data": [int(count) for _, count in rows]}