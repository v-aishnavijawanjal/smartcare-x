from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from smartcare.auth import auth_bp
from smartcare.auth.forms import ForgotPasswordForm, LoginForm, RegisterForm, ResetPasswordForm
from smartcare.emails.mailer import send_password_reset, send_welcome_and_verification
from smartcare.extensions import db
from smartcare.models.patient import Patient
from smartcare.models.user import RoleEnum, User
from smartcare.services.audit_service import log_activity
from smartcare.services.auth_service import (
    consume_password_reset_token,
    generate_email_verification_token,
    issue_password_reset_token,
    mark_email_verified,
    verify_email_verification_token,
)

ROLE_DASHBOARD_ENDPOINT = {
    RoleEnum.PATIENT: "patient.dashboard",
    RoleEnum.DOCTOR: "doctor.dashboard",
    RoleEnum.RECEPTIONIST: "reception.dashboard",
    RoleEnum.ADMIN: "admin.dashboard",
}


def _redirect_to_dashboard(user):
    return redirect(url_for(ROLE_DASHBOARD_ENDPOINT[user.role]))


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return _redirect_to_dashboard(current_user)

    form = RegisterForm()
    if form.validate_on_submit():
        if User.query.filter_by(email=form.email.data.lower()).first():
            flash("An account with this email already exists.", "danger")
            return render_template("auth/register.html", form=form)

        user = User(
            full_name=form.full_name.data.strip(),
            email=form.email.data.lower().strip(),
            phone=form.phone.data,
            role=RoleEnum.PATIENT,
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.flush()

        db.session.add(Patient(user_id=user.id))
        db.session.commit()

        token = generate_email_verification_token(user.email)
        verification_url = url_for("auth.verify_email", token=token, _external=True)
        send_welcome_and_verification(user, verification_url)

        flash("Account created! Please check your email to verify your address before logging in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/register.html", form=form)


@auth_bp.route("/verify-email/<token>")
def verify_email(token):
    email = verify_email_verification_token(token)
    if not email:
        flash("This verification link is invalid or has expired.", "danger")
        return redirect(url_for("auth.login"))

    mark_email_verified(email)
    flash("Your email has been verified. You can now log in.", "success")
    return redirect(url_for("auth.login"))


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return _redirect_to_dashboard(current_user)

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower().strip()).first()

        if user is None or not user.check_password(form.password.data):
            flash("Invalid email or password.", "danger")
            return render_template("auth/login.html", form=form)

        if not user.is_active:
            flash("Your account has been deactivated. Contact the hospital admin.", "danger")
            return render_template("auth/login.html", form=form)

        if not user.is_email_verified:
            flash("Please verify your email address before logging in.", "warning")
            return render_template("auth/login.html", form=form)

        login_user(user, remember=form.remember_me.data)
        log_activity(user.id, "Logged in", request.remote_addr)
        flash(f"Welcome back, {user.full_name}!", "success")
        return _redirect_to_dashboard(user)

    return render_template("auth/login.html", form=form)


@auth_bp.route("/logout")
@login_required
def logout():
    log_activity(current_user.id, "Logged out", request.remote_addr)
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("main.home"))


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    form = ForgotPasswordForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower().strip()).first()
        if user:
            reset_token = issue_password_reset_token(user)
            reset_url = url_for("auth.reset_password", token=reset_token.token, _external=True)
            send_password_reset(user, reset_url)

        flash("If that email is registered, a password reset link has been sent.", "info")
        return redirect(url_for("auth.login"))

    return render_template("auth/forgot_password.html", form=form)


@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    form = ResetPasswordForm()
    if form.validate_on_submit():
        success = consume_password_reset_token(token, form.password.data)
        if success:
            flash("Your password has been reset. Please log in.", "success")
            return redirect(url_for("auth.login"))
        flash("This reset link is invalid or has expired. Please request a new one.", "danger")
        return redirect(url_for("auth.forgot_password"))

    return render_template("auth/reset_password.html", form=form, token=token)