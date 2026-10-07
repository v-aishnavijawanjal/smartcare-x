from datetime import datetime

from smartcare.extensions import db


class AuditLog(db.Model):
    """Records data-changing actions (create/update/delete) on key entities."""

    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    action = db.Column(db.String(50), nullable=False)       # e.g. "create", "update", "delete"
    entity_type = db.Column(db.String(50), nullable=False)  # e.g. "Appointment", "Bill"
    entity_id = db.Column(db.Integer)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship("User", back_populates="audit_logs")

    def __repr__(self):
        return f"<AuditLog {self.action} {self.entity_type}#{self.entity_id}>"


class ActivityLog(db.Model):
    """Lighter-weight log of general user activity (logins, page visits, etc.)."""

    __tablename__ = "activity_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    description = db.Column(db.String(255), nullable=False)
    ip_address = db.Column(db.String(45))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship("User", back_populates="activity_logs")

    def __repr__(self):
        return f"<ActivityLog {self.description}>"
