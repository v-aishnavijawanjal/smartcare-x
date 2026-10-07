from smartcare.extensions import db


class Doctor(db.Model):
    __tablename__ = "doctors"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"), nullable=False)

    specialization = db.Column(db.String(120))
    qualification = db.Column(db.String(150))
    experience_years = db.Column(db.Integer, default=0)
    consultation_fee = db.Column(db.Numeric(10, 2), default=0)
    bio = db.Column(db.Text)

    user = db.relationship("User", back_populates="doctor_profile")
    department = db.relationship("Department", back_populates="doctors")

    appointments = db.relationship("Appointment", back_populates="doctor", cascade="all, delete-orphan")
    prescriptions = db.relationship("Prescription", back_populates="doctor", cascade="all, delete-orphan")
    availability_slots = db.relationship("DoctorAvailability", back_populates="doctor", cascade="all, delete-orphan")
    reviews = db.relationship("Review", back_populates="doctor")

    @property
    def full_name(self):
        return self.user.full_name

    def __repr__(self):
        return f"<Doctor {self.user.email} ({self.specialization})>"


class DoctorAvailability(db.Model):
    """Doctor's weekly availability."""

    __tablename__ = "doctor_availability"

    id = db.Column(db.Integer, primary_key=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey("doctors.id"), nullable=False)

    day_of_week = db.Column(db.SmallInteger, nullable=False)  # Monday=0, Sunday=6
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    slot_duration_minutes = db.Column(db.Integer, default=15, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    doctor = db.relationship("Doctor", back_populates="availability_slots")

    def __repr__(self):
        return f"<Availability doctor={self.doctor_id} day={self.day_of_week}>"