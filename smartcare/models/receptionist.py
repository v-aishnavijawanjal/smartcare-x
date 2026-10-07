from smartcare.extensions import db


class Receptionist(db.Model):
    __tablename__ = "receptionists"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False)

    shift = db.Column(db.String(20))       # e.g. "Morning", "Evening", "Night"
    desk_number = db.Column(db.String(10))

    user = db.relationship("User", back_populates="receptionist_profile")

    @property
    def full_name(self):
        return self.user.full_name

    def __repr__(self):
        return f"<Receptionist {self.user.email}>"
