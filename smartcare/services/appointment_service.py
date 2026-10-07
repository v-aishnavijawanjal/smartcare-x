"""
Appointment booking and scheduling utilities.
"""

import secrets
from datetime import date, datetime, timedelta

from sqlalchemy.exc import IntegrityError

from smartcare.extensions import db
from smartcare.models.appointment import Appointment, AppointmentStatus
from smartcare.models.doctor import DoctorAvailability


class AppointmentConflictError(Exception):
    """Raised when a requested slot is unavailable."""


def is_slot_in_past(appointment_date, time_slot):
    """Returns True if the selected appointment slot is in the past."""
    if appointment_date < date.today():
        return True
    if appointment_date > date.today():
        return False
    try:
        start_str = time_slot.split(" - ")[0].strip()
        start_time = datetime.strptime(start_str, "%I:%M %p").time()
    except (ValueError, AttributeError, IndexError):
        return False
    return datetime.combine(appointment_date, start_time) <= datetime.now()


def is_slot_taken(doctor_id, appointment_date, time_slot, exclude_appointment_id=None):
    query = Appointment.query.filter_by(
        doctor_id=doctor_id,
        appointment_date=appointment_date,
        time_slot=time_slot,
    ).filter(Appointment.status.in_([AppointmentStatus.PENDING, AppointmentStatus.APPROVED]))

    if exclude_appointment_id:
        query = query.filter(Appointment.id != exclude_appointment_id)

    return db.session.query(query.exists()).scalar()


def book_appointment(
    patient_id,
    doctor_id,
    department_id,
    appointment_date,
    time_slot,
    reason=None,
    created_by="self",
    consultation_type="in_person",
):
    if is_slot_in_past(appointment_date, time_slot):
        raise AppointmentConflictError("This date/time has already passed. Please choose a future slot.")

    # Check slot availability before creating the appointment.
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
        consultation_type=consultation_type,
        status=AppointmentStatus.PENDING,
    )
    db.session.add(appointment)

    try:
        db.session.commit()
    except IntegrityError:
        # Handle concurrent booking requests safely.
        db.session.rollback()
        raise AppointmentConflictError("This time slot is already booked. Please choose another.")

    return appointment


def cancel_appointment(appointment):
    appointment.status = AppointmentStatus.CANCELLED
    appointment.updated_at = datetime.utcnow()
    db.session.commit()
    return appointment


def reschedule_appointment(appointment, new_date, new_time_slot):
    if is_slot_in_past(new_date, new_time_slot):
        raise AppointmentConflictError("This date/time has already passed. Please choose a future slot.")

    if is_slot_taken(appointment.doctor_id, new_date, new_time_slot, exclude_appointment_id=appointment.id):
        raise AppointmentConflictError("The new time slot is already booked. Please choose another.")

    appointment.appointment_date = new_date
    appointment.time_slot = new_time_slot
    # Reset to pending so the doctor can review the new schedule.
    appointment.status = AppointmentStatus.PENDING
    # Clear the old meeting link for the previous appointment slot.
    appointment.meeting_link = None
    appointment.updated_at = datetime.utcnow()

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise AppointmentConflictError("The new time slot is already booked. Please choose another.")

    return appointment


def approve_appointment(appointment):
    appointment.status = AppointmentStatus.APPROVED
    appointment.updated_at = datetime.utcnow()

    # Generate a meeting link only for online consultations.
    if appointment.consultation_type == "online" and not appointment.meeting_link:
        appointment.meeting_link = generate_meeting_link(appointment.id)

    try:
        db.session.commit()
    except IntegrityError:
        # Handle slot conflicts caused by concurrent updates.
        db.session.rollback()
        raise AppointmentConflictError("This slot was booked by someone else in the meantime.")

    return appointment


def generate_meeting_link(appointment_id):
    """Generate a unique Jitsi Meet link for an online appointment."""
    token = secrets.token_urlsafe(8)
    return f"https://meet.jit.si/SmartCareX-{appointment_id}-{token}"


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
    """Return available appointment slots for the selected date."""
    day_of_week = appointment_date.weekday()  # 0=Monday ... 6=Sunday

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
            # Skip past time slots for today.
            already_passed = appointment_date == date.today() and current <= datetime.now()
            if slot_label not in taken_slots and not already_passed:
                slots.append(slot_label)
            current += step

    return slots


def get_todays_appointments(doctor_id):
    return (
        Appointment.query.filter_by(doctor_id=doctor_id, appointment_date=datetime.utcnow().date())
        .order_by(Appointment.time_slot.asc())
        .all()
    )