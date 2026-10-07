import secrets
from datetime import datetime, timedelta

from smartcare.extensions import db


class PasswordResetToken(db.Model):
    __tablename__ = "password_reset_tokens"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    token = db.Column(db.String(100), unique=True, nullable=False, index=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Boolean, default=False, nullable=False)

    user = db.relationship("User", back_populates="password_reset_tokens")

    @staticmethod
    def generate(user_id, ttl: timedelta):
        return PasswordResetToken(
            user_id=user_id,
            token=secrets.token_urlsafe(48),
            expires_at=datetime.utcnow() + ttl,
        )

    @property
    def is_valid(self):
        return (not self.used) and datetime.utcnow() < self.expires_at

    def __repr__(self):
        return f"<PasswordResetToken user={self.user_id} used={self.used}>"
