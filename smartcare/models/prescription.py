from datetime import datetime

from smartcare.extensions import db


class Prescription(db.Model):
    __tablename__ = "prescriptions"

    id = db.Column(db.Integer, primary_key=True)
    appointment_id = db.Column(db.Integer, db.ForeignKey("appointments.id"), unique=True, nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey("doctors.id"), nullable=False)
    patient_id = db.Column(db.Integer, db.ForeignKey("patients.id"), nullable=False)

    diagnosis = db.Column(db.Text)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    appointment = db.relationship("Appointment", back_populates="prescription")
    doctor = db.relationship("Doctor", back_populates="prescriptions")
    patient = db.relationship("Patient", back_populates="prescriptions")
    items = db.relationship("PrescriptionItem", back_populates="prescription", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Prescription #{self.id} for patient={self.patient_id}>"


class PrescriptionItem(db.Model):
    __tablename__ = "prescription_items"

    id = db.Column(db.Integer, primary_key=True)
    prescription_id = db.Column(db.Integer, db.ForeignKey("prescriptions.id"), nullable=False)
    medicine_id = db.Column(db.Integer, db.ForeignKey("medicines.id"), nullable=False)

    dosage = db.Column(db.String(100))          # e.g. "500mg"
    frequency = db.Column(db.String(100))        # e.g. "Twice a day after food"
    duration_days = db.Column(db.Integer, default=1)

    prescription = db.relationship("Prescription", back_populates="items")
    medicine = db.relationship("Medicine", back_populates="prescription_items")

    def __repr__(self):
        return f"<PrescriptionItem medicine={self.medicine_id}>"
