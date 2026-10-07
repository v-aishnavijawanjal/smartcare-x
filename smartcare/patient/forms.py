from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField
from wtforms import DateField, SelectField, StringField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Length, Optional

from smartcare.utils.validators import max_file_size_mb, not_in_past, valid_phone_number


class AppointmentForm(FlaskForm):
    department_id = SelectField("Department", coerce=int, validators=[DataRequired()])
    doctor_id = SelectField("Doctor", coerce=int, validators=[DataRequired()])
    consultation_type = SelectField(
        "Consultation Type",
        choices=[("in_person", "In-Person Visit"), ("online", "Online (Video Call)")],
        default="in_person",
        validators=[DataRequired()],
    )
    appointment_date = DateField("Date", validators=[DataRequired(), not_in_past])
    time_slot = SelectField("Time Slot", validators=[DataRequired()])
    reason = TextAreaField("Reason for Visit", validators=[Optional(), Length(max=500)])
    submit = SubmitField("Book Appointment")


class RescheduleForm(FlaskForm):
    appointment_date = DateField("New Date", validators=[DataRequired(), not_in_past])
    time_slot = SelectField("New Time Slot", validators=[DataRequired()])
    submit = SubmitField("Reschedule")


class ProfileUpdateForm(FlaskForm):
    full_name = StringField("Full Name", validators=[DataRequired(), Length(min=2, max=120)])
    phone = StringField("Phone Number", validators=[Optional(), valid_phone_number])
    date_of_birth = DateField("Date of Birth", validators=[Optional()])
    gender = SelectField(
        "Gender",
        choices=[("", "Select..."), ("male", "Male"), ("female", "Female"), ("other", "Other")],
        validators=[Optional()],
    )
    blood_group = SelectField(
        "Blood Group",
        choices=[("", "Select...")] + [(bg, bg) for bg in ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]],
        validators=[Optional()],
    )
    address = TextAreaField("Address", validators=[Optional(), Length(max=255)])
    emergency_contact = StringField("Emergency Contact", validators=[Optional(), valid_phone_number])
    profile_photo = FileField(
        "Profile Photo",
        validators=[FileAllowed(["jpg", "jpeg", "png", "gif"], "Images only!"), max_file_size_mb(5)],
    )
    submit = SubmitField("Update Profile")