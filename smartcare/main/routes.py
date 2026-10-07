from datetime import datetime
from flask import flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from smartcare.extensions import db
from smartcare.main import main_bp
from smartcare.main.forms import ContactForm, ReviewForm
from smartcare.models.appointment import Appointment, AppointmentStatus
from smartcare.models.contact import Contact
from smartcare.models.department import Department
from smartcare.models.doctor import Doctor
from smartcare.models.review import Review
from smartcare.models.user import RoleEnum
from smartcare.utils.decorators import role_required


@main_bp.route("/")
def home():
    departments = Department.query.limit(6).all()
    featured_doctors = Doctor.query.limit(6).all()
    recent_reviews = Review.query.order_by(Review.created_at.desc()).limit(6).all()
    return render_template(
        "home.html",
        departments=departments,
        featured_doctors=featured_doctors,
        recent_reviews=recent_reviews,
    )


@main_bp.route("/about")
def about():
    return render_template("about.html")


@main_bp.route("/doctors")
def doctors_directory():
    departments = Department.query.all()
    doctors = Doctor.query.order_by(Doctor.experience_years.desc()).all()
    return render_template("doctors_directory.html", doctors=doctors, departments=departments)


@main_bp.route("/contact", methods=["GET", "POST"])
def contact():
    form = ContactForm()
    if form.validate_on_submit():
        # Use custom subject when "Other" is selected.
        final_subject = (
            form.subject_other.data.strip()
            if form.subject.data == "Other" and form.subject_other.data
            else form.subject.data
        )
        db.session.add(
            Contact(
                name=form.name.data.strip(),
                email=form.email.data.lower().strip(),
                subject=final_subject,
                message=form.message.data.strip(),
            )
        )
        db.session.commit()
        flash("Thanks for reaching out — our team will get back to you shortly.", "success")
        return redirect(url_for("main.contact"))

    return render_template("contact.html", form=form)


@main_bp.route("/reviews/new", methods=["GET", "POST"])
@login_required
@role_required(RoleEnum.PATIENT)
def submit_review():
    form = ReviewForm()
    patient_id = current_user.patient_profile.id

    if form.validate_on_submit():
        # Allow one review per patient. Existing reviews are updated.
        existing_review = Review.query.filter_by(patient_id=patient_id).first()

        if existing_review:
            existing_review.rating = form.rating.data
            existing_review.comment = form.comment.data.strip() if form.comment.data else None
            existing_review.created_at = datetime.utcnow()
            db.session.commit()
            flash("Your review has been updated.", "success")
        else:
            db.session.add(
                Review(
                    patient_id=patient_id,
                    doctor_id=None,
                    rating=form.rating.data,
                    comment=form.comment.data.strip() if form.comment.data else None,
                )
            )
            db.session.commit()
            flash("Thank you for your feedback!", "success")

        return redirect(url_for("main.home"))

    return render_template("submit_review.html", form=form)