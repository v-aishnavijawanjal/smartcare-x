import enum
from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from smartcare.extensions import db


class RoleEnum(enum.Enum):
    PATIENT = "patient"
    DOCTOR = "doctor"
    RECEPTIONIST = "receptionist"
    ADMIN = "admin"


class User(db.Model, UserMixin):
    """User model with role-specific profile relationships."""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(20))
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.Enum(RoleEnum), nullable=False, index=True)

    is_email_verified = db.Column(db.Boolean, default=False, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    profile_photo = db.Column(db.String(255), default="default_avatar.png")

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Role-specific profiles
    patient_profile = db.relationship("Patient", back_populates="user", uselist=False, cascade="all, delete-orphan")
    doctor_profile = db.relationship("Doctor", back_populates="user", uselist=False, cascade="all, delete-orphan")
    receptionist_profile = db.relationship("Receptionist", back_populates="user", uselist=False, cascade="all, delete-orphan")

    notifications = db.relationship("Notification", back_populates="user", cascade="all, delete-orphan")
    audit_logs = db.relationship("AuditLog", back_populates="user")
    activity_logs = db.relationship("ActivityLog", back_populates="user")
    password_reset_tokens = db.relationship("PasswordResetToken", back_populates="user", cascade="all, delete-orphan")

    # Password helpers
    def set_password(self, raw_password):
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        return check_password_hash(self.password_hash, raw_password)

    # Role checks
    @property
    def is_patient(self):
        return self.role == RoleEnum.PATIENT

    @property
    def is_doctor(self):
        return self.role == RoleEnum.DOCTOR

    @property
    def is_receptionist(self):
        return self.role == RoleEnum.RECEPTIONIST

    @property
    def is_admin(self):
        return self.role == RoleEnum.ADMIN

    def get_id(self):
        # Explicit implementation for Flask-Login.
        return str(self.id)

    def __repr__(self):
        return f"<User {self.email} ({self.role.value})>"