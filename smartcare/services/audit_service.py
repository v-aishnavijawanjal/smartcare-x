"""Audit and activity logging helpers."""

from smartcare.extensions import db
from smartcare.models.audit_log import ActivityLog, AuditLog


def log_audit(user_id, action, entity_type, entity_id):
    entry = AuditLog(user_id=user_id, action=action, entity_type=entity_type, entity_id=entity_id)
    db.session.add(entry)
    db.session.commit()
    return entry


def log_activity(user_id, description, ip_address=None):
    entry = ActivityLog(user_id=user_id, description=description, ip_address=ip_address)
    db.session.add(entry)
    db.session.commit()
    return entry


def get_recent_audit_logs(limit=50):
    return AuditLog.query.order_by(AuditLog.timestamp.desc()).limit(limit).all()


def get_recent_activity_logs(limit=50):
    return ActivityLog.query.order_by(ActivityLog.timestamp.desc()).limit(limit).all()