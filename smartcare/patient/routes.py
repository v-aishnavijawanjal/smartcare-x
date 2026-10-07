from datetime import date

from flask import Response, current_app, flash, jsonify, redirect, render_template, request, send_from_directory, url_for
from flask_login import current_user

from smartcare.emails.mailer import send_appointment_cancelled, send_appointment_confirmation
from smartcare.extensions import db
from smartcare.models.appointment import Appointment, AppointmentStatus
from smartcare.models.billing import Bill
from smartcare.models.department import Department
from smartcare.models.doctor import Doctor
from smartcare.models.medical_report import MedicalReport
from smartcare.models.prescription import Prescription
from smartcare.models.user import RoleEnum
from smartcare.patient import patient_bp
from smartcare.patient.forms import AppointmentForm, ProfileUpdateForm, RescheduleForm
from smartcare.services.appointment_service import (
    AppointmentConflictError,
    book_appointment,
    cancel_appointment,
    get_available_slots,
    is_slot_in_past,
    reschedule_appointment,
)
from smartcare.services.billing_service import create_bill, get_refund_pending_bills, get_unpaid_bills, mark_refund_pending, record_payment
from smartcare.services.notification_service import get_recent_notifications, get_unread_count, mark_all_as_read
from smartcare.services.payment_service import create_order, verify_payment_signature
from smartcare.services.symptom_service import suggest_department
from smartcare.utils.decorators import role_required
from smartcare.utils.file_upload import save_profile_photo
from smartcare.utils.pagination import paginate_query
from smartcare.utils.pdf_generator import build_generated_lab_report_pdf, build_prescription_pdf


def _current_patient():
    return current_user.patient_profile


@patient_bp.before_request
@role_required(RoleEnum.PATIENT)
def guard_patient_area():
    """Restrict access to authenticated patients."""
    pass


def _build_health_timeline(patient, limit=10):
    """Build a unified timeline of patient activities."""
    events = []

    appointments = (
        Appointment.query.filter_by(patient_id=patient.id).order_by(Appointment.appointment_date.desc()).limit(limit).all()
    )
    for appt in appointments:
        events.append(
            {
                "date": appt.appointment_date,
                "type": "appointment",
                "icon": "bi-calendar-event",
                "color": "var(--sc-primary)",
                "title": f"Appointment with Dr. {appt.doctor.full_name}",
                "subtitle": f"{appt.time_slot} — {appt.status.value.title()}",
                "link": url_for("patient.appointment_history"),
            }
        )

    prescriptions = (
        Prescription.query.filter_by(patient_id=patient.id).order_by(Prescription.created_at.desc()).limit(limit).all()
    )
    for p in prescriptions:
        events.append(
            {
                "date": p.created_at.date(),
                "type": "prescription",
                "icon": "bi-file-earmark-medical",
                "color": "var(--sc-cta)",
                "title": f"Prescription from Dr. {p.doctor.full_name}",
                "subtitle": p.diagnosis or "Prescription issued",
                "link": url_for("patient.download_prescription", prescription_id=p.id),
            }
        )

    reports = (
        MedicalReport.query.filter_by(patient_id=patient.id).order_by(MedicalReport.uploaded_at.desc()).limit(limit).all()
    )
    for r in reports:
        events.append(
            {
                "date": r.uploaded_at.date(),
                "type": "report",
                "icon": "bi-clipboard2-pulse",
                "color": "var(--sc-success)",
                "title": r.title,
                "subtitle": "Lab report available",
                "link": url_for("patient.download_lab_report", report_id=r.id),
            }
        )

    events.sort(key=lambda e: e["date"], reverse=True)
    return events[:limit]


@patient_bp.route("/dashboard")
def dashboard():
    patient = _current_patient()
    upcoming = (
        Appointment.query.filter_by(patient_id=patient.id)
        .filter(Appointment.appointment_date >= date.today())
        .filter(Appointment.status.in_([AppointmentStatus.PENDING, AppointmentStatus.APPROVED]))
        .order_by(Appointment.appointment_date.asc())
        .limit(5)
        .all()
    )
    recent_prescriptions = (
        Prescription.query.filter_by(patient_id=patient.id).order_by(Prescription.created_at.desc()).limit(3).all()
    )
    notifications = get_recent_notifications(current_user.id, limit=5)

    return render_template(
        "patient/dashboard.html",
        upcoming_appointments=upcoming,
        recent_prescriptions=recent_prescriptions,
        notifications=notifications,
        unread_count=get_unread_count(current_user.id),
        timeline_events=_build_health_timeline(patient),
        unpaid_bills=get_unpaid_bills(patient.id, channel="online"),
        refund_pending_bills=get_refund_pending_bills(patient.id),
    )


@patient_bp.route("/appointments/book", methods=["GET", "POST"])
def book():
    form = AppointmentForm()
    form.department_id.choices = [(d.id, d.name) for d in Department.query.order_by(Department.name).all()]

    doctors_query = Doctor.query
    if form.department_id.data:
        doctors_query = doctors_query.filter_by(department_id=form.department_id.data)
    form.doctor_id.choices = [(d.id, f"Dr. {d.full_name}") for d in doctors_query.all()]

    form.time_slot.choices = [(s, s) for s in request.form.getlist("time_slot")] or [("", "Select date & doctor first")]

    if form.validate_on_submit():
        order_id = request.form.get("razorpay_order_id")
        payment_id = request.form.get("razorpay_payment_id")
        signature = request.form.get("razorpay_signature")

        if not (order_id and payment_id and signature) or not verify_payment_signature(order_id, payment_id, signature):
            flash("Payment verification failed. Please try booking again.", "danger")
            return render_template("patient/book_appointment.html", form=form)

        doctor = Doctor.query.get(form.doctor_id.data)

        try:
            appointment = book_appointment(
                patient_id=_current_patient().id,
                doctor_id=form.doctor_id.data,
                department_id=form.department_id.data,
                appointment_date=form.appointment_date.data,
                time_slot=form.time_slot.data,
                reason=form.reason.data,
                created_by="self",
                consultation_type=form.consultation_type.data,
            )
        except AppointmentConflictError as exc:
            # Create a refund record if payment succeeds but the slot is no longer available.
            orphan_bill = create_bill(
                patient_id=_current_patient().id,
                generated_by_user_id=current_user.id,
                line_items=[
                    {"description": f"Consultation Fee — Dr. {doctor.full_name} (slot unavailable)", "quantity": 1, "unit_price": doctor.consultation_fee}
                ],
                tax_rate=0,
                channel="online",
            )
            record_payment(orphan_bill, orphan_bill.total, method="razorpay")
            orphan_bill.status = "refund_pending"
            db.session.commit()

            flash(
                f"{str(exc)} Your payment was received but the slot was taken — a refund has been initiated automatically.",
                "danger",
            )
            return render_template("patient/book_appointment.html", form=form)

        bill = create_bill(
            patient_id=_current_patient().id,
            generated_by_user_id=current_user.id,
            line_items=[
                {"description": f"Consultation Fee — Dr. {doctor.full_name}", "quantity": 1, "unit_price": doctor.consultation_fee}
            ],
            appointment_id=appointment.id,
            tax_rate=0,
            channel="online",
        )
        record_payment(bill, bill.total, method="razorpay")

        send_appointment_confirmation(appointment)
        flash("Payment successful — appointment booked! Awaiting doctor confirmation.", "success")
        return redirect(url_for("patient.appointment_history"))

    return render_template("patient/book_appointment.html", form=form)


@patient_bp.route("/appointments/create-payment-order", methods=["POST"])
def create_payment_order():
    doctor_id = request.form.get("doctor_id", type=int)
    doctor = Doctor.query.get_or_404(doctor_id)
    fee = doctor.consultation_fee or 0

    # Validate the selected slot before creating the payment order.
    appointment_date_str = request.form.get("appointment_date")
    time_slot = request.form.get("time_slot")
    if appointment_date_str and time_slot:
        try:
            appointment_date = date.fromisoformat(appointment_date_str)
        except ValueError:
            appointment_date = None
        if appointment_date and is_slot_in_past(appointment_date, time_slot):
            return jsonify({"error": "This date/time has already passed. Please choose a future slot."}), 400

    order = create_order(fee, receipt=f"appt-{current_user.id}-{doctor.id}")
    return jsonify(
        {
            "order_id": order["id"],
            "amount": order["amount"],
            "currency": order["currency"],
            "key": current_app.config["RAZORPAY_KEY_ID"],
            "fee": float(fee),
            "doctor_name": doctor.full_name,
            "patient_name": current_user.full_name,
            "patient_email": current_user.email,
            "patient_phone": current_user.phone or "",
        }
    )


@patient_bp.route("/appointments/suggest-department")
def suggest_department_api():
    symptom_text = request.args.get("symptoms", "")
    department_name = suggest_department(symptom_text)
    if not department_name:
        return jsonify({"matched": False})

    department = Department.query.filter_by(name=department_name).first()
    if not department:
        return jsonify({"matched": False})

    return jsonify({"matched": True, "department_id": department.id, "department_name": department.name})


@patient_bp.route("/appointments/available-slots")
def available_slots_api():
    """Return available slots for the selected doctor and date."""
    doctor_id = request.args.get("doctor_id", type=int)
    appointment_date = request.args.get("date", type=date.fromisoformat)
    if not doctor_id or not appointment_date:
        return jsonify([])
    return jsonify(get_available_slots(doctor_id, appointment_date))


@patient_bp.route("/appointments/doctors-by-department")
def doctors_by_department_api():
    department_id = request.args.get("department_id", type=int)
    doctors = Doctor.query.filter_by(department_id=department_id).all() if department_id else []
    return jsonify(
        [{"id": d.id, "name": f"Dr. {d.full_name}", "fee": float(d.consultation_fee or 0)} for d in doctors]
    )


@patient_bp.route("/appointments/<int:appointment_id>/cancel", methods=["POST"])
def cancel(appointment_id):
    appointment = Appointment.query.filter_by(id=appointment_id, patient_id=_current_patient().id).first_or_404()
    cancel_appointment(appointment)

    # Mark paid appointments for refund.
    mark_refund_pending(appointment)

    send_appointment_cancelled(appointment)
    flash("Appointment cancelled. If payment was already made, a refund has been initiated.", "info")
    return redirect(url_for("patient.dashboard"))


@patient_bp.route("/appointments/<int:appointment_id>/reschedule", methods=["GET", "POST"])
def reschedule(appointment_id):
    appointment = Appointment.query.filter_by(id=appointment_id, patient_id=_current_patient().id).first_or_404()
    form = RescheduleForm()
    form.time_slot.choices = [(s, s) for s in request.form.getlist("time_slot")] or [("", "Select a new date first")]

    if form.validate_on_submit():
        try:
            reschedule_appointment(appointment, form.appointment_date.data, form.time_slot.data)
        except AppointmentConflictError as exc:
            flash(str(exc), "danger")
            return render_template("patient/book_appointment.html", form=form, reschedule=True, appointment=appointment)

        flash("Appointment rescheduled — awaiting the doctor's confirmation for the new time.", "success")
        return redirect(url_for("patient.appointment_history"))

    return render_template("patient/book_appointment.html", form=form, reschedule=True, appointment=appointment)


@patient_bp.route("/appointments/history")
def appointment_history():
    query = (
        Appointment.query.filter_by(patient_id=_current_patient().id)
        .order_by(Appointment.appointment_date.desc())
    )
    pagination = paginate_query(query)
    return render_template("patient/appointment_history.html", pagination=pagination)


@patient_bp.route("/medical-history")
def medical_history():
    patient = _current_patient()
    prescriptions = Prescription.query.filter_by(patient_id=patient.id).order_by(Prescription.created_at.desc()).all()
    reports = MedicalReport.query.filter_by(patient_id=patient.id).order_by(MedicalReport.uploaded_at.desc()).all()
    return render_template("patient/medical_history.html", prescriptions=prescriptions, reports=reports)


@patient_bp.route("/prescriptions")
def prescriptions():
    query = (
        Prescription.query.filter_by(patient_id=_current_patient().id)
        .order_by(Prescription.created_at.desc())
    )
    pagination = paginate_query(query)
    return render_template("patient/prescriptions.html", pagination=pagination)


@patient_bp.route("/prescriptions/<int:prescription_id>/download")
def download_prescription(prescription_id):
    prescription = Prescription.query.filter_by(
        id=prescription_id, patient_id=_current_patient().id
    ).first_or_404()

    # Prevent prescription download until the related medicine bill is paid.
    pending_bill = Bill.query.filter_by(prescription_id=prescription.id).filter(
        Bill.status.in_(["unpaid", "partial"])
    ).first()
    if pending_bill:
        flash("Please complete your medicine payment before downloading this prescription.", "warning")
        return redirect(url_for("patient.dashboard"))

    pdf_bytes = build_prescription_pdf(prescription)
    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=prescription_{prescription.id}.pdf"},
    )


@patient_bp.route("/lab-reports")
def lab_reports():
    query = (
        MedicalReport.query.filter_by(patient_id=_current_patient().id)
        .order_by(MedicalReport.uploaded_at.desc())
    )
    pagination = paginate_query(query)
    return render_template("patient/lab_reports.html", pagination=pagination)


@patient_bp.route("/lab-reports/<int:report_id>/download")
def download_lab_report(report_id):
    report = MedicalReport.query.filter_by(id=report_id, patient_id=_current_patient().id).first_or_404()

    if report.is_generated:
        pdf_bytes = build_generated_lab_report_pdf(report)
        return Response(
            pdf_bytes,
            mimetype="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=lab_report_{report.id}.pdf"},
        )

    directory = current_app.config["UPLOAD_FOLDER"]
    return send_from_directory(directory, report.file_path, as_attachment=True)


@patient_bp.route("/profile", methods=["GET", "POST"])
def profile():
    patient = _current_patient()
    form = ProfileUpdateForm(obj=current_user)
    form.profile_photo.data = None  # Clear the stored filename; the file field expects a new upload.

    if request.method == "GET":
        form.date_of_birth.data = patient.date_of_birth
        form.gender.data = patient.gender
        form.blood_group.data = patient.blood_group
        form.address.data = patient.address
        form.emergency_contact.data = patient.emergency_contact

    if form.validate_on_submit():
        current_user.full_name = form.full_name.data.strip()
        current_user.phone = form.phone.data

        if form.profile_photo.data:
            try:
                filename = save_profile_photo(form.profile_photo.data)
                if filename:
                    current_user.profile_photo = filename
            except ValueError as exc:
                flash(str(exc), "danger")
                return render_template("patient/profile.html", form=form)

        patient.date_of_birth = form.date_of_birth.data
        patient.gender = form.gender.data or None
        patient.blood_group = form.blood_group.data or None
        patient.address = form.address.data
        patient.emergency_contact = form.emergency_contact.data

        db.session.commit()
        flash("Profile updated successfully.", "success")
        return redirect(url_for("patient.profile"))

    return render_template("patient/profile.html", form=form)


@patient_bp.route("/bills/<int:bill_id>/pay")
def pay_bill(bill_id):
    bill = Bill.query.filter_by(id=bill_id, patient_id=_current_patient().id).first_or_404()
    if bill.status == "paid":
        flash("This bill has already been paid.", "info")
        return redirect(url_for("patient.dashboard"))
    return render_template("patient/pay_bill.html", bill=bill)


@patient_bp.route("/bills/<int:bill_id>/create-payment-order", methods=["POST"])
def create_bill_payment_order(bill_id):
    bill = Bill.query.filter_by(id=bill_id, patient_id=_current_patient().id).first_or_404()
    amount = bill.balance_due

    order = create_order(amount, receipt=f"bill-{bill.id}-{current_user.id}")
    return jsonify(
        {
            "order_id": order["id"],
            "amount": order["amount"],
            "currency": order["currency"],
            "key": current_app.config["RAZORPAY_KEY_ID"],
            "patient_name": current_user.full_name,
            "patient_email": current_user.email,
            "patient_phone": current_user.phone or "",
        }
    )


@patient_bp.route("/bills/<int:bill_id>/confirm-payment", methods=["POST"])
def confirm_bill_payment(bill_id):
    bill = Bill.query.filter_by(id=bill_id, patient_id=_current_patient().id).first_or_404()

    order_id = request.form.get("razorpay_order_id")
    payment_id = request.form.get("razorpay_payment_id")
    signature = request.form.get("razorpay_signature")

    if not (order_id and payment_id and signature) or not verify_payment_signature(order_id, payment_id, signature):
        flash("Payment verification failed. Please try again.", "danger")
        return redirect(url_for("patient.pay_bill", bill_id=bill.id))

    record_payment(bill, bill.balance_due, method="razorpay")
    flash("Payment successful — your medicines are now paid for.", "success")
    return redirect(url_for("patient.dashboard"))


@patient_bp.route("/notifications/mark-all-read")
def notifications_mark_all_read():
    mark_all_as_read(current_user.id)
    return redirect(url_for("patient.dashboard"))