from smartcare.extensions import db


class Department(db.Model):
    __tablename__ = "departments"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text)
    icon = db.Column(db.String(50), default="bi-hospital")  # Bootstrap Icons class

    doctors = db.relationship("Doctor", back_populates="department")
    appointments = db.relationship("Appointment", back_populates="department")

    def __repr__(self):
        return f"<Department {self.name}>"
