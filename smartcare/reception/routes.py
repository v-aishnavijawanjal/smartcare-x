import secrets
from datetime import date

from flask import Response, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user

from smartcare.emails.mailer import send_appointment_cancelled, send_appointment_confirmation
from smartcare.extensions import db
from smartcare.models.appointment import Appointment
from smartcare.models.billing import Bill
from smartcare.models.department import Department
from smartcare.models.doctor import Doctor
from smartcare.models.patient import Patient
from smartcare.models.user import RoleEnum, User
from smartcare.reception import reception_bp
from smartcare.reception.forms import BillForm, PaymentForm, WalkInPatientForm
from smartcare.services.appointment_service import (
    AppointmentConflictError,
    cancel_appointment,
    get_available_slots,
    register_walkin_appointment,
)
from smartcare.services.billing_service import create_bill, get_receptionist_unpaid_bills, mark_refund_pending, record_payment
from smartcare.services.search_service import search_patients
from smartcare.utils.decorators import role_required
from smartcare.utils.pagination import paginate_query
from smartcare.utils.pdf_generator import build_bill_receipt_pdf


@reception_bp.before_request
@role_required(RoleEnum.RECEPTIONIST)
def guard_reception_area():
    pass


@reception_bp.route("/dashboard")
def dashboard():
    todays_appointments = Appointment.query.filter_by(appointment_date=date.today()).count()
    walkins_today = Appointment.query.filter_by(appointment_date=date.today(), created_by="reception").count()
    unpaid_bills = get_receptionist_unpaid_bills()
    return render_template(
        "reception/dashboard.html",
        todays_appointments=todays_appointments,
        walkins_today=walkins_today,
        unpaid_bills_count=len(unpaid_bills),
    )


def _find_or_create_patient(full_name, email, phone, gender):
    user = User.query.filter_by(email=email.lower().strip()).first()
    if user and user.patient_profile:
        return user.patient_profile

    if user is None:
        user = User(
            full_name=full_name.strip(),
            email=email.lower().strip(),
            phone=phone,
            role=RoleEnum.PATIENT,
            is_email_verified=True,
        )
        user.set_password(secrets.token_urlsafe(16))
        db.session.add(user)
        db.session.flush()

    patient = Patient(user_id=user.id, gender=gender or None)
    db.session.add(patient)
    db.session.flush()
    return patient


@reception_bp.route("/patients/register", methods=["GET", "POST"])
def register_walkin():
    form = WalkInPatientForm()
    form.department_id.choices = [(d.id, d.name) for d in Department.query.order_by(Department.name).all()]

    doctors_query = Doctor.query
    if form.department_id.data:
        doctors_query = doctors_query.filter_by(department_id=form.department_id.data)
    form.doctor_id.choices = [(d.id, f"Dr. {d.full_name}") for d in doctors_query.all()]
    form.time_slot.choices = [(s, s) for s in request.form.getlist("time_slot")] or [("", "Select date & doctor first")]

    if form.validate_on_submit():
        patient = _find_or_create_patient(form.full_name.data, form.email.data, form.phone.data, form.gender.data)

        try:
            appointment = register_walkin_appointment(
                patient_id=patient.id,
                doctor_id=form.doctor_id.data,
                department_id=form.department_id.data,
                appointment_date=form.appointment_date.data,
                time_slot=form.time_slot.data,
                reason=form.reason.data,
            )
        except AppointmentConflictError as exc:
            db.session.rollback()
            flash(str(exc), "danger")
            return render_template("reception/walkin_register.html", form=form)

        # Create the consultation bill during registration.
        doctor = Doctor.query.get(form.doctor_id.data)
        if doctor.consultation_fee and doctor.consultation_fee > 0:
            create_bill(
                patient_id=patient.id,
                generated_by_user_id=current_user.id,
                line_items=[
                    {"description": f"Consultation Fee — Dr. {doctor.full_name}", "quantity": 1, "unit_price": doctor.consultation_fee}
                ],
                appointment_id=appointment.id,
                tax_rate=0,
                channel="counter",
            )

        send_appointment_confirmation(appointment)
        flash(f"Patient registered. Token number: {appointment.token_number}. A consultation fee bill has been added to Billing.", "success")
        return redirect(url_for("reception.token_board"))

    return render_template("reception/walkin_register.html", form=form)


@reception_bp.route("/appointments/doctors-by-department")
def doctors_by_department_api():
    department_id = request.args.get("department_id", type=int)
    doctors = Doctor.query.filter_by(department_id=department_id).all() if department_id else []
    return jsonify([{"id": d.id, "name": f"Dr. {d.full_name}"} for d in doctors])


@reception_bp.route("/appointments/available-slots")
def available_slots_api():
    doctor_id = request.args.get("doctor_id", type=int)
    appointment_date = request.args.get("date", type=date.fromisoformat)
    if not doctor_id or not appointment_date:
        return jsonify([])
    return jsonify(get_available_slots(doctor_id, appointment_date))


@reception_bp.route("/tokens")
def token_board():
    selected_doctor_id = request.args.get("doctor_id", type=int)
    doctors = Doctor.query.all()

    query = Appointment.query.filter_by(appointment_date=date.today())
    if selected_doctor_id:
        query = query.filter_by(doctor_id=selected_doctor_id)

    appointments = query.filter(Appointment.token_number.isnot(None)).order_by(Appointment.token_number.asc()).all()
    return render_template(
        "reception/token_board.html", appointments=appointments, doctors=doctors, selected_doctor_id=selected_doctor_id
    )


@reception_bp.route("/appointments")
def manage_appointments():
    query = Appointment.query.order_by(Appointment.appointment_date.desc())
    pagination = paginate_query(query)
    return render_template("reception/manage_appointments.html", pagination=pagination)


@reception_bp.route("/appointments/<int:appointment_id>/cancel", methods=["POST"])
def cancel_appointment_route(appointment_id):
    appointment = Appointment.query.get_or_404(appointment_id)
    cancel_appointment(appointment)
    # Update billing after appointment cancellation.
    mark_refund_pending(appointment)
    send_appointment_cancelled(appointment)
    flash("Appointment cancelled.", "info")
    return redirect(url_for("reception.manage_appointments"))


@reception_bp.route("/patients/search")
def patient_search():
    term = request.args.get("q", "").strip()
    results = search_patients(term) if term else []
    return render_template("reception/patient_search.html", results=results, term=term)


@reception_bp.route("/billing")
def billing_list():
    unpaid_bills = get_receptionist_unpaid_bills()
    return render_template("reception/billing.html", unpaid_bills=unpaid_bills)


@reception_bp.route("/billing/new/<int:patient_id>", methods=["GET", "POST"])
def create_bill_route(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    form = BillForm()

    if form.validate_on_submit():
        line_items = [
            {"description": item.item_description.data, "quantity": item.quantity.data, "unit_price": item.unit_price.data}
            for item in form.items
        ]
        bill = create_bill(patient_id=patient.id, generated_by_user_id=current_user.id, line_items=line_items, channel="counter")
        flash(f"Bill #{bill.id} generated — total ₹{bill.total:.2f}", "success")
        return redirect(url_for("reception.billing_list"))

    return render_template("reception/billing.html", form=form, patient=patient, unpaid_bills=get_receptionist_unpaid_bills())


@reception_bp.route("/billing/<int:bill_id>/payment", methods=["POST"])
def record_payment_route(bill_id):
    bill = Bill.query.get_or_404(bill_id)
    form = PaymentForm()
    if form.validate_on_submit():
        record_payment(bill, form.amount.data, form.method.data)
        flash("Payment recorded.", "success")
    else:
        flash("Invalid payment amount.", "danger")
    return redirect(url_for("reception.billing_list"))


@reception_bp.route("/billing/<int:bill_id>/receipt")
def download_receipt(bill_id):
    bill = Bill.query.get_or_404(bill_id)
    pdf_bytes = build_bill_receipt_pdf(bill)
    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=receipt_{bill.id}.pdf"},
    )