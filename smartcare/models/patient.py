from smartcare.extensions import db


class Patient(db.Model):
    __tablename__ = "patients"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False)

    date_of_birth = db.Column(db.Date)
    gender = db.Column(db.String(20))
    blood_group = db.Column(db.String(5))
    address = db.Column(db.String(255))
    emergency_contact = db.Column(db.String(20))

    user = db.relationship("User", back_populates="patient_profile")

    appointments = db.relationship("Appointment", back_populates="patient", cascade="all, delete-orphan")
    prescriptions = db.relationship("Prescription", back_populates="patient", cascade="all, delete-orphan")
    medical_reports = db.relationship("MedicalReport", back_populates="patient", cascade="all, delete-orphan")
    bills = db.relationship("Bill", back_populates="patient", cascade="all, delete-orphan")
    reviews = db.relationship("Review", back_populates="patient", cascade="all, delete-orphan")

    @property
    def full_name(self):
        return self.user.full_name

    def __repr__(self):
        return f"<Patient {self.user.email}>"
