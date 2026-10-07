from flask import Response, flash, redirect, render_template, request, url_for
from flask_login import current_user

from smartcare.admin import admin_bp
from smartcare.admin.forms import (
    CreateDoctorForm,
    CreateReceptionistForm,
    DepartmentForm,
    MedicineForm,
    RestockForm,
)
from smartcare.extensions import db
from smartcare.models.billing import Bill
from smartcare.models.department import Department
from smartcare.models.doctor import Doctor
from smartcare.models.medicine import Medicine, MedicineInventory
from smartcare.models.receptionist import Receptionist
from smartcare.models.user import RoleEnum, User
from smartcare.services.analytics_service import (
    appointment_status_breakdown_chart,
    appointments_last_n_days_chart,
    dashboard_kpis,
    department_distribution_chart,
    revenue_last_n_months_chart,
)
from smartcare.services.audit_service import get_recent_activity_logs, get_recent_audit_logs, log_audit
from smartcare.services.billing_service import get_refund_pending_bills, mark_bill_refunded
from smartcare.services.inventory_service import get_low_stock_items, restock
from smartcare.services.report_service import (
    appointment_report,
    doctor_performance_report,
    patient_statistics_report,
    revenue_report,
)
from smartcare.services.search_service import global_search
from smartcare.utils.csv_export import csv_response
from smartcare.utils.decorators import role_required
from smartcare.utils.pagination import paginate_query
from smartcare.utils.pdf_generator import build_tabular_report_pdf


@admin_bp.before_request
@role_required(RoleEnum.ADMIN)
def guard_admin_area():
    pass


# ---------------------------------------------------------------- Dashboard
@admin_bp.route("/dashboard")
def dashboard():
    return render_template(
        "admin/dashboard.html",
        kpis=dashboard_kpis(),
        appointments_chart=appointments_last_n_days_chart(),
        status_chart=appointment_status_breakdown_chart(),
        revenue_chart=revenue_last_n_months_chart(),
        department_chart=department_distribution_chart(),
        low_stock_items=get_low_stock_items()[:5],
    )


# ---------------------------------------------------------------- Users
@admin_bp.route("/users")
def manage_users():
    role_filter = request.args.get("role")
    query = User.query
    if role_filter:
        query = query.filter_by(role=RoleEnum(role_filter))
    query = query.order_by(User.created_at.desc())

    pagination = paginate_query(query)
    return render_template("admin/manage_users.html", pagination=pagination, role_filter=role_filter)


@admin_bp.route("/users/<int:user_id>/toggle-active", methods=["POST"])
def toggle_user_active(user_id):
    user = User.query.get_or_404(user_id)
    user.is_active = not user.is_active
    db.session.commit()
    log_audit(user_id, "toggle_active", "User", user.id)
    flash(f"{user.full_name} is now {'active' if user.is_active else 'deactivated'}.", "info")
    return redirect(url_for("admin.manage_users"))


@admin_bp.route("/users/<int:user_id>/delete", methods=["POST"])
def delete_user(user_id):
    user = User.query.get_or_404(user_id)

    if user.id == current_user.id:
        flash("You can't delete your own account while logged in.", "danger")
        return redirect(url_for("admin.manage_users"))

    # Prevent deletion if the patient has pending financial records.
    # Use Deactivate instead to preserve billing history.
    if user.patient_profile:
        blocking_bills = Bill.query.filter(
            Bill.patient_id == user.patient_profile.id,
            Bill.status.in_(["unpaid", "partial", "refund_pending"]),
        ).count()
        if blocking_bills:
            flash(
                f"{user.full_name} has {blocking_bills} outstanding bill(s) (unpaid or awaiting refund). "
                "Settle or refund them first, or use Deactivate instead of Delete to preserve the financial record.",
                "danger",
            )
            return redirect(url_for("admin.manage_users"))

    full_name = user.full_name
    log_audit(current_user.id, "delete", "User", user.id)
    db.session.delete(user)
    db.session.commit()
    flash(f"{full_name}'s account has been permanently deleted.", "info")
    return redirect(url_for("admin.manage_users"))


# ---------------------------------------------------------------- Doctors
@admin_bp.route("/doctors")
def manage_doctors():
    doctors = Doctor.query.order_by(Doctor.id.desc()).all()
    return render_template("admin/manage_doctors.html", doctors=doctors)


@admin_bp.route("/doctors/new", methods=["GET", "POST"])
def create_doctor():
    form = CreateDoctorForm()
    form.department_id.choices = [(d.id, d.name) for d in Department.query.order_by(Department.name).all()]

    if form.validate_on_submit():
        if User.query.filter_by(email=form.email.data.lower()).first():
            flash("An account with this email already exists.", "danger")
            return render_template("admin/manage_doctors.html", form=form, doctors=Doctor.query.all())

        user = User(
            full_name=form.full_name.data.strip(),
            email=form.email.data.lower().strip(),
            phone=form.phone.data,
            role=RoleEnum.DOCTOR,
            is_email_verified=True,
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.flush()

        db.session.add(
            Doctor(
                user_id=user.id,
                department_id=form.department_id.data,
                specialization=form.specialization.data,
                qualification=form.qualification.data,
                experience_years=form.experience_years.data,
                consultation_fee=form.consultation_fee.data,
            )
        )
        db.session.commit()
        log_audit(user.id, "create", "Doctor", user.id)
        flash(f"Doctor account created for {user.full_name}.", "success")
        return redirect(url_for("admin.manage_doctors"))

    return render_template("admin/manage_doctors.html", form=form, doctors=Doctor.query.all())


# ---------------------------------------------------------------- Receptionists
@admin_bp.route("/receptionists")
def manage_receptionists():
    receptionists = Receptionist.query.order_by(Receptionist.id.desc()).all()
    form = CreateReceptionistForm()
    return render_template("admin/manage_receptionists.html", receptionists=receptionists, form=form)


@admin_bp.route("/receptionists/new", methods=["POST"])
def create_receptionist():
    form = CreateReceptionistForm()
    if form.validate_on_submit():
        if User.query.filter_by(email=form.email.data.lower()).first():
            flash("An account with this email already exists.", "danger")
            return redirect(url_for("admin.manage_receptionists"))

        user = User(
            full_name=form.full_name.data.strip(),
            email=form.email.data.lower().strip(),
            phone=form.phone.data,
            role=RoleEnum.RECEPTIONIST,
            is_email_verified=True,
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.flush()

        db.session.add(Receptionist(user_id=user.id, shift=form.shift.data, desk_number=form.desk_number.data))
        db.session.commit()
        log_audit(user.id, "create", "Receptionist", user.id)
        flash(f"Receptionist account created for {user.full_name}.", "success")
    else:
        flash("Please correct the errors in the form.", "danger")

    return redirect(url_for("admin.manage_receptionists"))


# ---------------------------------------------------------------- Departments
@admin_bp.route("/departments", methods=["GET", "POST"])
def manage_departments():
    form = DepartmentForm()
    if form.validate_on_submit():
        db.session.add(Department(name=form.name.data.strip(), description=form.description.data, icon=form.icon.data))
        db.session.commit()
        flash("Department added.", "success")
        return redirect(url_for("admin.manage_departments"))

    departments = Department.query.order_by(Department.name).all()
    return render_template("admin/manage_departments.html", form=form, departments=departments)


@admin_bp.route("/departments/<int:department_id>/delete", methods=["POST"])
def delete_department(department_id):
    department = Department.query.get_or_404(department_id)
    if department.doctors:
        flash("Cannot delete a department that still has doctors assigned.", "danger")
    else:
        db.session.delete(department)
        db.session.commit()
        flash("Department deleted.", "info")
    return redirect(url_for("admin.manage_departments"))


# ---------------------------------------------------------------- Medicines
@admin_bp.route("/medicines", methods=["GET", "POST"])
def manage_medicines():
    form = MedicineForm()
    if form.validate_on_submit():
        medicine = Medicine(
            name=form.name.data.strip(),
            category=form.category.data,
            manufacturer=form.manufacturer.data,
            unit_price=form.unit_price.data,
        )
        db.session.add(medicine)
        db.session.flush()
        db.session.add(
            MedicineInventory(
                medicine_id=medicine.id,
                quantity_in_stock=form.initial_stock.data or 0,
                reorder_level=form.reorder_level.data or 10,
            )
        )
        db.session.commit()
        flash("Medicine added.", "success")
        return redirect(url_for("admin.manage_medicines"))

    medicines = Medicine.query.order_by(Medicine.name).all()
    restock_form = RestockForm()
    return render_template("admin/manage_medicines.html", form=form, medicines=medicines, restock_form=restock_form)


@admin_bp.route("/medicines/<int:medicine_id>/restock", methods=["POST"])
def restock_medicine(medicine_id):
    form = RestockForm()
    if form.validate_on_submit():
        restock(medicine_id, form.quantity.data)
        flash("Stock updated.", "success")
    else:
        flash("Enter a valid quantity.", "danger")
    return redirect(url_for("admin.manage_medicines"))


# ---------------------------------------------------------------- Reports
@admin_bp.route("/reports")
def reports():
    period = request.args.get("period", "daily")
    appt_summary, appt_rows = appointment_report(period=period)
    rev_summary, _ = revenue_report(period="monthly")
    doctor_perf = doctor_performance_report()
    patient_stats = patient_statistics_report()

    return render_template(
        "admin/reports.html",
        period=period,
        appt_summary=appt_summary,
        appt_rows=appt_rows,
        rev_summary=rev_summary,
        doctor_perf=doctor_perf,
        patient_stats=patient_stats,
    )


@admin_bp.route("/reports/appointments/export.csv")
def export_appointments_csv():
    period = request.args.get("period", "daily")
    _, appt_rows = appointment_report(period=period)
    headers = ["ID", "Patient", "Doctor", "Date", "Time Slot", "Status"]
    rows = [
        [a.id, a.patient.full_name, a.doctor.full_name, a.appointment_date, a.time_slot, a.status.value]
        for a in appt_rows
    ]
    return csv_response(f"appointments_{period}.csv", headers, rows)


@admin_bp.route("/reports/appointments/export.pdf")
def export_appointments_pdf():
    period = request.args.get("period", "daily")
    _, appt_rows = appointment_report(period=period)
    headers = ["ID", "Patient", "Doctor", "Date", "Time Slot", "Status"]
    rows = [
        [str(a.id), a.patient.full_name, a.doctor.full_name, a.appointment_date.strftime("%d %b %Y"), a.time_slot, a.status.value]
        for a in appt_rows
    ]
    pdf_bytes = build_tabular_report_pdf(f"Appointment Report ({period.title()})", headers, rows)
    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=appointments_{period}.pdf"},
    )


@admin_bp.route("/reports/doctor-performance/export.csv")
def export_doctor_performance_csv():
    rows_data = doctor_performance_report()
    headers = ["Doctor ID", "Doctor Name", "Total Appointments", "Completed"]
    rows = [[r[0], r[1], r[2], r[3]] for r in rows_data]
    return csv_response("doctor_performance.csv", headers, rows)


# ---------------------------------------------------------------- Search
@admin_bp.route("/search")
def search_everything():
    term = request.args.get("q", "").strip()
    results = global_search(term) if term else None
    return render_template("admin/search_results.html", term=term, results=results)


# ---------------------------------------------------------------- Audit Logs
@admin_bp.route("/audit-logs")
def audit_logs():
    audit_entries = get_recent_audit_logs(limit=100)
    activity_entries = get_recent_activity_logs(limit=100)
    return render_template("admin/audit_logs.html", audit_entries=audit_entries, activity_entries=activity_entries)


# ---------------------------------------------------------------- Contact Messages
@admin_bp.route("/contact-messages")
def contact_messages():
    from smartcare.models.contact import Contact

    pagination = paginate_query(Contact.query.order_by(Contact.submitted_at.desc()))
    return render_template("admin/contact_messages.html", pagination=pagination)


# ---------------------------------------------------------------- Refunds
@admin_bp.route("/refunds")
def refunds():
    pending_bills = get_refund_pending_bills()
    return render_template("admin/refunds.html", pending_bills=pending_bills)


@admin_bp.route("/refunds/<int:bill_id>/mark-refunded", methods=["POST"])
def mark_refunded(bill_id):
    bill = Bill.query.get_or_404(bill_id)
    if bill.status != "refund_pending":
        flash("This bill is not awaiting a refund.", "warning")
        return redirect(url_for("admin.refunds"))

    mark_bill_refunded(bill)
    log_audit(current_user.id, "mark_refunded", "Bill", bill.id)
    flash(f"Bill #{bill.id} marked as refunded.", "success")
    return redirect(url_for("admin.refunds"))