"""Appointment booking and scheduling services."""

from datetime import datetime, timedelta

from smartcare.extensions import db
from smartcare.models.appointment import Appointment, AppointmentStatus
from smartcare.models.doctor import DoctorAvailability


class AppointmentConflictError(Exception):
    """Raised when the selected slot is unavailable."""


def is_slot_taken(doctor_id, appointment_date, time_slot, exclude_appointment_id=None):
    query = Appointment.query.filter_by(
        doctor_id=doctor_id,
        appointment_date=appointment_date,
        time_slot=time_slot,
    ).filter(Appointment.status.in_([AppointmentStatus.PENDING, AppointmentStatus.APPROVED]))

    if exclude_appointment_id:
        query = query.filter(Appointment.id != exclude_appointment_id)

    return db.session.query(query.exists()).scalar()


def book_appointment(patient_id, doctor_id, department_id, appointment_date, time_slot, reason=None, created_by="self"):
    if is_slot_taken(doctor_id, appointment_date, time_slot):
        raise AppointmentConflictError("This time slot is already booked. Please choose another.")

    appointment = Appointment(
        patient_id=patient_id,
        doctor_id=doctor_id,
        department_id=department_id,
        appointment_date=appointment_date,
        time_slot=time_slot,
        reason=reason,
        created_by=created_by,
        status=AppointmentStatus.PENDING,
    )
    db.session.add(appointment)
    db.session.commit()
    return appointment


def cancel_appointment(appointment):
    appointment.status = AppointmentStatus.CANCELLED
    appointment.updated_at = datetime.utcnow()
    db.session.commit()
    return appointment


def reschedule_appointment(appointment, new_date, new_time_slot):
    if is_slot_taken(appointment.doctor_id, new_date, new_time_slot, exclude_appointment_id=appointment.id):
        raise AppointmentConflictError("The new time slot is already booked. Please choose another.")

    appointment.appointment_date = new_date
    appointment.time_slot = new_time_slot
    appointment.status = AppointmentStatus.RESCHEDULED
    appointment.updated_at = datetime.utcnow()
    db.session.commit()
    return appointment


def approve_appointment(appointment):
    appointment.status = AppointmentStatus.APPROVED
    appointment.updated_at = datetime.utcnow()
    db.session.commit()
    return appointment


def reject_appointment(appointment):
    appointment.status = AppointmentStatus.REJECTED
    appointment.updated_at = datetime.utcnow()
    db.session.commit()
    return appointment


def mark_completed(appointment):
    appointment.status = AppointmentStatus.COMPLETED
    appointment.updated_at = datetime.utcnow()
    db.session.commit()
    return appointment


def next_token_number(doctor_id, appointment_date):
    """Return the next token number for the doctor's queue."""
    last_token = (
        db.session.query(db.func.max(Appointment.token_number))
        .filter_by(doctor_id=doctor_id, appointment_date=appointment_date)
        .scalar()
    )
    return (last_token or 0) + 1


def register_walkin_appointment(patient_id, doctor_id, department_id, appointment_date, time_slot, reason=None):
    appointment = book_appointment(
        patient_id, doctor_id, department_id, appointment_date, time_slot, reason, created_by="reception"
    )
    appointment.token_number = next_token_number(doctor_id, appointment_date)
    db.session.commit()
    return appointment


def get_available_slots(doctor_id, appointment_date):
    """Return available time slots for the selected date."""
    day_of_week = appointment_date.weekday()

    windows = DoctorAvailability.query.filter_by(
        doctor_id=doctor_id, day_of_week=day_of_week, is_active=True
    ).all()

    if not windows:
        return []

    taken_slots = {
        a.time_slot
        for a in Appointment.query.filter_by(doctor_id=doctor_id, appointment_date=appointment_date)
        .filter(Appointment.status.in_([AppointmentStatus.PENDING, AppointmentStatus.APPROVED]))
        .all()
    }

    slots = []
    for window in windows:
        current = datetime.combine(appointment_date, window.start_time)
        end = datetime.combine(appointment_date, window.end_time)
        step = timedelta(minutes=window.slot_duration_minutes)

        while current + step <= end:
            slot_label = f"{current.strftime('%I:%M %p')} - {(current + step).strftime('%I:%M %p')}"
            if slot_label not in taken_slots:
                slots.append(slot_label)
            current += step

    return slots


def get_todays_appointments(doctor_id):
    return (
        Appointment.query.filter_by(doctor_id=doctor_id, appointment_date=datetime.utcnow().date())
        .order_by(Appointment.time_slot.asc())
        .all()
    )