"""Authentication helper functions."""

from datetime import datetime

from flask import current_app
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from smartcare.extensions import db
from smartcare.models.password_reset import PasswordResetToken
from smartcare.models.user import User


def _serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"])


def generate_email_verification_token(user_email):
    return _serializer().dumps(user_email, salt="email-verification")


def verify_email_verification_token(token, max_age_seconds=None):
    max_age = max_age_seconds or int(
        current_app.config["EMAIL_VERIFICATION_TOKEN_TTL"].total_seconds()
    )
    try:
        return _serializer().loads(token, salt="email-verification", max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None


def issue_password_reset_token(user):
    ttl = current_app.config["PASSWORD_RESET_TOKEN_TTL"]
    reset_token = PasswordResetToken.generate(user.id, ttl)
    db.session.add(reset_token)
    db.session.commit()
    return reset_token


def consume_password_reset_token(raw_token, new_password):
    """Return True if the password is reset successfully."""
    reset_token = PasswordResetToken.query.filter_by(token=raw_token).first()
    if not reset_token or not reset_token.is_valid:
        return False

    user = User.query.get(reset_token.user_id)
    user.set_password(new_password)
    reset_token.used = True
    db.session.commit()
    return True


def mark_email_verified(user_email):
    user = User.query.filter_by(email=user_email).first()
    if user:
        user.is_email_verified = True
        user.updated_at = datetime.utcnow()
        db.session.commit()
    return user