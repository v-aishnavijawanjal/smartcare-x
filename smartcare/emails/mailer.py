"""
Email sending. Templates live in smartcare/emails/templates/ (separate from
the main app templates) and are rendered through their own Jinja
Environment so email HTML never accidentally inherits app UI blocks.

Each public send_* function is the single place a given email type is
built and dispatched — routes/services call these, never Flask-Mail
directly, so subject lines and template names stay in one place.
"""

import os
import threading

from flask import current_app
from flask_mail import Message
from jinja2 import Environment, FileSystemLoader, select_autoescape

from smartcare.extensions import mail

_TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")
_env = Environment(
    loader=FileSystemLoader(_TEMPLATE_DIR),
    autoescape=select_autoescape(["html"]),
)


def _render(template_name, **context):
    template = _env.get_template(template_name)
    return template.render(app_name="SmartCare X", **context)


def _send_in_background(app, message):
    """Runs in a separate thread so the SMTP round-trip (which can take
    a couple of seconds, especially over a slow connection to Gmail)
    never blocks the request that triggered the email — the user gets
    redirected immediately while the email goes out a moment later."""
    with app.app_context():
        try:
            mail.send(message)
        except Exception as exc:  # noqa: BLE001 — email failures must never crash the request
            app.logger.error("Failed to send email to %s: %s", message.recipients, exc)


def _send(subject, recipient, template_name, **context):
    html_body = _render(template_name, **context)
    message = Message(subject=subject, recipients=[recipient], html=html_body)
    app = current_app._get_current_object()
    threading.Thread(target=_send_in_background, args=(app, message), daemon=True).start()


def send_registration_successful(user):
    _send(
        "Welcome to SmartCare X",
        user.email,
        "registration_successful.html",
        full_name=user.full_name,
    )


def send_welcome_and_verification(user, verification_url):
    """Combines the welcome message and the verification link into ONE email.
    Sending a single email is more reliable than two — it halves the chance
    that a real user's provider (Gmail, Outlook, etc.) flags or drops one
    of them, which matters a lot for real-world/demo signups."""
    _send(
        "Welcome to SmartCare X — Verify Your Email",
        user.email,
        "welcome_verify.html",
        full_name=user.full_name,
        verification_url=verification_url,
    )


def send_email_verification(user, verification_url):
    _send(
        "Verify your SmartCare X account",
        user.email,
        "email_verification.html",
        full_name=user.full_name,
        verification_url=verification_url,
    )


def send_password_reset(user, reset_url):
    _send(
        "Reset your SmartCare X password",
        user.email,
        "password_reset.html",
        full_name=user.full_name,
        reset_url=reset_url,
    )


def send_appointment_confirmation(appointment):
    _send(
        "Appointment Confirmed",
        appointment.patient.user.email,
        "appointment_confirmation.html",
        full_name=appointment.patient.full_name,
        doctor_name=appointment.doctor.full_name,
        department=appointment.department.name,
        appointment_date=appointment.appointment_date,
        time_slot=appointment.time_slot,
    )


def send_appointment_cancelled(appointment):
    _send(
        "Appointment Cancelled",
        appointment.patient.user.email,
        "appointment_cancelled.html",
        full_name=appointment.patient.full_name,
        doctor_name=appointment.doctor.full_name,
        appointment_date=appointment.appointment_date,
        time_slot=appointment.time_slot,
    )


def send_teleconsultation_link(appointment):
    """Sent right after a doctor approves an 'online' appointment — carries
    the auto-generated Jitsi Meet link (see approve_appointment() in
    appointment_service.py)."""
    _send(
        "Your Video Consultation Link is Ready",
        appointment.patient.user.email,
        "teleconsultation_link.html",
        full_name=appointment.patient.full_name,
        doctor_name=appointment.doctor.full_name,
        appointment_date=appointment.appointment_date,
        time_slot=appointment.time_slot,
        meeting_link=appointment.meeting_link,
    )


def send_prescription_ready(prescription):
    _send(
        "Your Prescription is Ready",
        prescription.patient.user.email,
        "prescription_ready.html",
        full_name=prescription.patient.full_name,
        doctor_name=prescription.doctor.full_name,
        diagnosis=prescription.diagnosis,
    )


def send_medicine_bill_ready(patient, doctor, bill):
    """Sent when an online-booked patient's prescription generates a
    medicine bill that still needs to be paid (see write_prescription()
    in doctor/routes.py)."""
    _send(
        "Medicine Payment Pending",
        patient.user.email,
        "medicine_bill_ready.html",
        full_name=patient.full_name,
        doctor_name=doctor.full_name,
        items=bill.items,
        total=bill.total,
    )


def send_bill_reminder(bill):
    """Sent by the scheduled reminder job (see scheduler_service.py) for
    medicine bills approaching or past their due date. Only fires once per
    bill — mark_reminder_sent() flips Bill.reminder_sent right after this
    is called, so the job never re-emails the same bill."""
    _send(
        "Reminder: Medicine Payment Overdue" if bill.is_overdue else "Reminder: Medicine Payment Due Soon",
        bill.patient.user.email,
        "bill_reminder.html",
        full_name=bill.patient.full_name,
        bill=bill,
        is_overdue=bill.is_overdue,
    )


def send_medicine_reminder(patient, medicine_name, dosage, reminder_time):
    _send(
        "Medicine Reminder",
        patient.user.email,
        "medicine_reminder.html",
        full_name=patient.full_name,
        medicine_name=medicine_name,
        dosage=dosage,
        reminder_time=reminder_time,
    )