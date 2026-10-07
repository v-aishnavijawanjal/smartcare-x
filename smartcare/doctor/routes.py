import json
from datetime import date

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user

from smartcare.doctor import doctor_bp
from smartcare.doctor.forms import AvailabilityForm, DoctorProfileForm, LabResultForm, PrescriptionForm, ReportUploadForm
from smartcare.emails.mailer import (
    send_appointment_cancelled,
    send_medicine_bill_ready,
    send_prescription_ready,
    send_teleconsultation_link,
)
from smartcare.extensions import db
from smartcare.models.billing import Bill
from smartcare.models.appointment import Appointment, AppointmentStatus
from smartcare.models.doctor import DoctorAvailability
from smartcare.models.medical_report import MedicalReport
from smartcare.models.medicine import Medicine
from smartcare.models.patient import Patient
from smartcare.models.prescription import Prescription
from smartcare.models.user import RoleEnum, User
from smartcare.services.appointment_service import approve_appointment, get_todays_appointments, mark_completed, reject_appointment
from smartcare.services.billing_service import create_bill, mark_refund_pending
from smartcare.services.inventory_service import InsufficientStockError
from smartcare.services.notification_service import notify
from smartcare.services.prescription_service import create_prescription
from smartcare.services.search_service import search_patients
from smartcare.utils.decorators import role_required
from smartcare.utils.file_upload import save_medical_report
from smartcare.utils.pagination import paginate_query


def _current_doctor():
    return current_user.doctor_profile


@doctor_bp.before_request
@role_required(RoleEnum.DOCTOR)
def guard_doctor_area():
    pass


@doctor_bp.route("/dashboard")
def dashboard():
    doctor = _current_doctor()
    todays_appointments = get_todays_appointments(doctor.id)
    pending_count = Appointment.query.filter_by(doctor_id=doctor.id, status=AppointmentStatus.PENDING).count()

    return render_template(
        "doctor/dashboard.html",
        todays_appointments=todays_appointments,
        pending_count=pending_count,
    )


@doctor_bp.route("/appointments/today")
def today_appointments():
    doctor = _current_doctor()
    appointments = get_todays_appointments(doctor.id)
    return render_template("doctor/today_appointments.html", appointments=appointments)


@doctor_bp.route("/appointments/<int:appointment_id>/approve", methods=["POST"])
def approve(appointment_id):
    appointment = Appointment.query.filter_by(id=appointment_id, doctor_id=_current_doctor().id).first_or_404()

    # Only a PENDING appointment can be approved. Without this guard, a
    # stale page (browser back button, double-click, or a direct POST)
    # could re-approve an already-completed/cancelled appointment.
    if appointment.status != AppointmentStatus.PENDING:
        flash(f"This appointment is already {appointment.status.value} — it can't be approved again.", "warning")
        return redirect(request.referrer or url_for("doctor.today_appointments"))

    approve_appointment(appointment)

    if appointment.consultation_type == "online":
        # meeting_link was just generated inside approve_appointment() —
        # send it to the patient by email and drop an in-app notification too.
        send_teleconsultation_link(appointment)
        notify(
            appointment.patient.user_id,
            "Video Consultation Link Ready",
            f"Your online appointment with Dr. {appointment.doctor.full_name} on "
            f"{appointment.appointment_date.strftime('%d %b %Y')} is confirmed. Your video call link is ready.",
        )
        flash("Appointment approved — video call link generated and sent to patient.", "success")
    else:
        flash("Appointment approved.", "success")

    return redirect(request.referrer or url_for("doctor.today_appointments"))


@doctor_bp.route("/appointments/<int:appointment_id>/reject", methods=["POST"])
def reject(appointment_id):
    appointment = Appointment.query.filter_by(id=appointment_id, doctor_id=_current_doctor().id).first_or_404()

    # Only a PENDING appointment can be rejected — an already-approved or
    # completed visit shouldn't be reject-able through this route (use
    # cancellation flows for those instead). Prevents a stale/duplicate
    # POST from voiding/refunding a bill that's already been settled.
    if appointment.status != AppointmentStatus.PENDING:
        flash(f"This appointment is already {appointment.status.value} — it can't be rejected.", "warning")
        return redirect(request.referrer or url_for("doctor.today_appointments"))

    reject_appointment(appointment)
    # If the consultation fee was already paid, flag it for refund instead
    # of silently keeping the patient's money for a visit that won't happen.
    mark_refund_pending(appointment)
    send_appointment_cancelled(appointment)
    flash("Appointment rejected.", "info")
    return redirect(request.referrer or url_for("doctor.today_appointments"))


@doctor_bp.route("/appointments/<int:appointment_id>/complete", methods=["POST"])
def complete(appointment_id):
    appointment = Appointment.query.filter_by(id=appointment_id, doctor_id=_current_doctor().id).first_or_404()

    # Only an APPROVED appointment can be marked completed — blocks
    # completing a pending/cancelled/already-completed appointment via a
    # stale page or duplicate submit.
    if appointment.status != AppointmentStatus.APPROVED:
        flash(f"This appointment is {appointment.status.value} — it can't be marked completed.", "warning")
        return redirect(request.referrer or url_for("doctor.today_appointments"))

    # A visit isn't truly "done" while ANY bill tied to it is still
    # unpaid — this covers both:
    #   1. The consultation-fee bill (appointment.bill) — for walk-ins,
    #      this is a counter bill reception is expected to collect at the
    #      desk before/after the visit. Without this check, a doctor could
    #      complete a walk-in that reception never actually billed.
    #   2. The medicine bill from the written prescription, if any.
    # Either bill sitting unpaid means the visit isn't financially closed.
    if appointment.bill and appointment.bill.status in ("unpaid", "partial"):
        pending_bill = appointment.bill
        flash(
            f"Can't mark this appointment completed — the consultation fee is still unpaid "
            f"(₹{pending_bill.balance_due} due, {pending_bill.channel} payment). "
            "Reception must collect payment first.",
            "danger",
        )
        return redirect(request.referrer or url_for("doctor.today_appointments"))

    if appointment.prescription:
        pending_medicine_bill = Bill.query.filter_by(
            prescription_id=appointment.prescription.id
        ).filter(Bill.status.in_(["unpaid", "partial"])).first()
        if pending_medicine_bill:
            flash(
                f"Can't mark this appointment completed — the patient still has a pending medicine bill of "
                f"₹{pending_medicine_bill.balance_due} ({pending_medicine_bill.channel} payment).",
                "danger",
            )
            return redirect(request.referrer or url_for("doctor.today_appointments"))

    mark_completed(appointment)
    flash("Appointment marked as completed.", "success")
    return redirect(request.referrer or url_for("doctor.today_appointments"))


@doctor_bp.route("/patients")
def patient_search():
    term = request.args.get("q", "").strip()
    results = search_patients(term) if term else []

    last_visit_map = {}
    if results:
        doctor_id = _current_doctor().id
        patient_ids = [p.id for p in results]
        rows = (
            db.session.query(Appointment.patient_id, db.func.max(Appointment.appointment_date))
            .filter(Appointment.doctor_id == doctor_id, Appointment.patient_id.in_(patient_ids))
            .group_by(Appointment.patient_id)
            .all()
        )
        last_visit_map = {patient_id: last_date for patient_id, last_date in rows}

    return render_template(
        "doctor/patient_records.html",
        results=results,
        term=term,
        single_patient=None,
        last_visit_map=last_visit_map,
    )


@doctor_bp.route("/patients/<int:patient_id>")
def patient_records(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    doctor_id = _current_doctor().id

    appointments = (
        Appointment.query.filter_by(patient_id=patient.id, doctor_id=doctor_id)
        .order_by(Appointment.appointment_date.desc())
        .all()
    )

    # A doctor may only view a patient's chart if they've actually treated
    # that patient (at least one appointment together, any status). Without
    # this, patient_id in the URL alone would expose any patient's full
    # prescription and lab report history to a doctor who has never seen
    # them — a real patient-privacy leak, not just an appointments issue.
    if not appointments:
        flash("You don't have access to this patient's records — they've never had an appointment with you.", "danger")
        return redirect(url_for("doctor.patient_search"))

    # Also scope the medical history itself to records THIS doctor
    # created — a patient's history with other doctors stays private
    # between them and their own doctors.
    prescriptions = (
        Prescription.query.filter_by(patient_id=patient.id, doctor_id=doctor_id)
        .order_by(Prescription.created_at.desc())
        .all()
    )
    reports = (
        MedicalReport.query.filter_by(patient_id=patient.id, doctor_id=doctor_id)
        .order_by(MedicalReport.uploaded_at.desc())
        .all()
    )

    return render_template(
        "doctor/patient_records.html",
        single_patient=patient,
        prescriptions=prescriptions,
        reports=reports,
        appointments=appointments,
        results=[],
        term="",
    )


@doctor_bp.route("/prescriptions/write/<int:appointment_id>", methods=["GET", "POST"])
def write_prescription(appointment_id):
    appointment = Appointment.query.filter_by(id=appointment_id, doctor_id=_current_doctor().id).first_or_404()

    # Only one prescription is allowed per appointment.
    if appointment.prescription:
        flash("A prescription has already been written for this appointment.", "info")
        return redirect(url_for("doctor.patient_records", patient_id=appointment.patient_id))

    form = PrescriptionForm()

    # Default option for medicine selection.
    medicine_choices = [(0, "Select Medicine...")] + [
        (m.id, m.name) for m in Medicine.query.order_by(Medicine.name).all()
    ]
    for item_form in form.items:
        item_form.medicine_id.choices = medicine_choices
    if request.method == "GET" and len(form.items) == 0:
        form.items.append_entry()

    if form.validate_on_submit():
        items = [
            {
                "medicine_id": item.medicine_id.data,
                # Use custom value when "Other" is selected.
                "dosage": item.dosage_other.data.strip() if item.dosage.data == "other" and item.dosage_other.data else item.dosage.data,
                "frequency": item.frequency_other.data.strip() if item.frequency.data == "other" and item.frequency_other.data else item.frequency.data,
                "duration_days": item.duration_days.data,
                "quantity_to_deduct": item.quantity_to_deduct.data,
            }
            for item in form.items
        ]
        try:
            prescription = create_prescription(
                appointment=appointment,
                doctor_id=_current_doctor().id,
                patient_id=appointment.patient_id,
                diagnosis=form.diagnosis.data,
                notes=form.notes.data,
                items=items,
            )
        except InsufficientStockError as exc:
            flash(str(exc), "danger")
            return render_template("doctor/write_prescription.html", form=form, appointment=appointment)

        send_prescription_ready(prescription)
        flash("Prescription saved and shared with the patient.", "success")

        # Generate a medicine bill when prescribed medicines have a price.
        medicine_line_items = []
        for item in items:
            medicine = Medicine.query.get(item["medicine_id"])
            if medicine and medicine.unit_price and medicine.unit_price > 0:
                medicine_line_items.append(
                    {
                        "description": medicine.name,
                        "quantity": item["quantity_to_deduct"],
                        "unit_price": medicine.unit_price,
                    }
                )

        if medicine_line_items:
            is_online_booking = appointment.created_by == "self"
            medicine_bill = create_bill(
                patient_id=appointment.patient_id,
                generated_by_user_id=current_user.id,
                line_items=medicine_line_items,
                prescription_id=prescription.id,
                with_due_date=is_online_booking,
                channel="online" if is_online_booking else "counter",
            )

            if is_online_booking:
                send_medicine_bill_ready(appointment.patient, _current_doctor(), medicine_bill)
                notify(
                    appointment.patient.user_id,
                    "Medicine Payment Pending",
                    f"Dr. {_current_doctor().full_name} prescribed medicines totaling ₹{medicine_bill.total}. "
                    f"Please complete the payment from your dashboard within {3} days.",
                )
                flash(f"A medicine bill of ₹{medicine_bill.total} has been generated for online payment.", "info")
            else:
                flash(f"A medicine bill of ₹{medicine_bill.total} has been sent to Reception for counter payment.", "info")

        return redirect(url_for("doctor.patient_records", patient_id=appointment.patient_id))

    return render_template("doctor/write_prescription.html", form=form, appointment=appointment)


@doctor_bp.route("/reports/upload", methods=["GET", "POST"])
def upload_report():
    form = ReportUploadForm()
    form.patient_id.choices = [
        (p.id, p.full_name)
        for p in Patient.query.join(User, Patient.user_id == User.id).order_by(User.full_name).all()
    ]

    if form.validate_on_submit():
        try:
            relative_path = save_medical_report(form.file.data)
        except ValueError as exc:
            flash(str(exc), "danger")
            return render_template("doctor/upload_report.html", form=form)

        db.session.add(
            MedicalReport(
                patient_id=form.patient_id.data,
                doctor_id=_current_doctor().id,
                title=form.title.data.strip(),
                file_path=relative_path,
                report_type=form.report_type.data,
            )
        )
        db.session.commit()
        flash("Report uploaded successfully.", "success")
        return redirect(url_for("doctor.patient_records", patient_id=form.patient_id.data))

    return render_template("doctor/upload_report.html", form=form)


@doctor_bp.route("/reports/generate", methods=["GET", "POST"])
def generate_report():
    """Generate a lab report from the submitted test results."""
    form = LabResultForm()
    form.patient_id.choices = [
        (p.id, p.full_name)
        for p in Patient.query.join(User, Patient.user_id == User.id).order_by(User.full_name).all()
    ]
    if request.method == "GET" and len(form.parameters) == 0:
        form.parameters.append_entry()

    if form.validate_on_submit():
        payload = {
            "parameters": [
                {
                    "parameter_name": p.parameter_name.data,
                    "result_value": p.result_value.data,
                    "reference_range": p.reference_range.data,
                    "unit_label": p.unit_label.data,
                }
                for p in form.parameters
            ],
            "interpretation": form.interpretation.data,
        }

        db.session.add(
            MedicalReport(
                patient_id=form.patient_id.data,
                doctor_id=_current_doctor().id,
                title=form.title.data.strip(),
                file_path=None,
                results_json=json.dumps(payload),
                report_type="lab",
            )
        )
        db.session.commit()
        flash("Lab report generated and shared with the patient.", "success")
        return redirect(url_for("doctor.patient_records", patient_id=form.patient_id.data))

    return render_template("doctor/generate_report.html", form=form)


@doctor_bp.route("/availability", methods=["GET", "POST"])
def availability():
    doctor = _current_doctor()
    form = AvailabilityForm()

    if form.validate_on_submit():
        db.session.add(
            DoctorAvailability(
                doctor_id=doctor.id,
                day_of_week=form.day_of_week.data,
                start_time=form.start_time.data,
                end_time=form.end_time.data,
                slot_duration_minutes=form.slot_duration_minutes.data,
            )
        )
        db.session.commit()
        flash("Availability window added.", "success")
        return redirect(url_for("doctor.availability"))
    elif request.method == "POST":
        for field_name, errors in form.errors.items():
            for error in errors:
                flash(f"{field_name}: {error}", "danger")

    slots = DoctorAvailability.query.filter_by(doctor_id=doctor.id).order_by(DoctorAvailability.day_of_week).all()
    return render_template("doctor/availability.html", form=form, slots=slots)


@doctor_bp.route("/availability/<int:slot_id>/delete", methods=["POST"])
def delete_availability(slot_id):
    slot = DoctorAvailability.query.filter_by(id=slot_id, doctor_id=_current_doctor().id).first_or_404()

    # Prevent removing availability that has upcoming bookings.
    upcoming_same_weekday = (
        Appointment.query.filter_by(doctor_id=slot.doctor_id)
        .filter(Appointment.status.in_([AppointmentStatus.PENDING, AppointmentStatus.APPROVED]))
        .filter(Appointment.appointment_date >= date.today())
        .all()
    )
    conflicting_count = sum(1 for a in upcoming_same_weekday if a.appointment_date.weekday() == slot.day_of_week)

    if conflicting_count:
        flash(
            f"Can't remove this availability window — {conflicting_count} upcoming appointment(s) fall on this day. "
            "Cancel or reschedule those appointments first.",
            "danger",
        )
        return redirect(url_for("doctor.availability"))

    db.session.delete(slot)
    db.session.commit()
    flash("Availability window removed.", "info")
    return redirect(url_for("doctor.availability"))


@doctor_bp.route("/profile", methods=["GET", "POST"])
def profile():
    doctor = _current_doctor()
    form = DoctorProfileForm(obj=doctor)

    if form.validate_on_submit():
        doctor.specialization = form.specialization.data
        doctor.qualification = form.qualification.data
        doctor.experience_years = form.experience_years.data
        doctor.consultation_fee = form.consultation_fee.data
        doctor.bio = form.bio.data
        db.session.commit()
        flash("Profile updated successfully.", "success")
        return redirect(url_for("doctor.profile"))

    return render_template("doctor/profile.html", form=form, doctor=doctor)