from datetime import datetime

from smartcare.extensions import db


class MedicalReport(db.Model):
    __tablename__ = "medical_reports"

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patients.id"), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey("doctors.id"), nullable=True)

    title = db.Column(db.String(150), nullable=False)

    # Uploaded report path (if available).
    # Generated reports use results_json to create the PDF when needed.
    file_path = db.Column(db.String(255), nullable=True)
    results_json = db.Column(db.Text, nullable=True)
    report_type = db.Column(db.String(30), default="lab")  # lab / scan / other
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    patient = db.relationship("Patient", back_populates="medical_reports")
    doctor = db.relationship("Doctor")

    @property
    def is_generated(self):
        """Returns True for reports generated from stored results."""
        return self.file_path is None and self.results_json is not None

    def __repr__(self):
        return f"<MedicalReport {self.title} patient={self.patient_id}>"