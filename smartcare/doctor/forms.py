from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField, FileRequired
from wtforms import (
    FieldList,
    FormField,
    IntegerField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
    TimeField,
)
from wtforms.validators import DataRequired, InputRequired, Length, NumberRange, Optional

from smartcare.utils.validators import max_file_size_mb

DAY_CHOICES = [
    (0, "Monday"), (1, "Tuesday"), (2, "Wednesday"), (3, "Thursday"),
    (4, "Friday"), (5, "Saturday"), (6, "Sunday"),
]

# Common dosage options.
DOSAGE_CHOICES = [
    ("", "Select dosage..."),
    ("250mg", "250mg"),
    ("500mg", "500mg"),
    ("650mg", "650mg"),
    ("1g (1000mg)", "1g (1000mg)"),
    ("5mg", "5mg"),
    ("10mg", "10mg"),
    ("20mg", "20mg"),
    ("1 tablet", "1 tablet"),
    ("2 tablets", "2 tablets"),
    ("½ tablet", "½ tablet"),
    ("5ml (1 teaspoon)", "5ml (1 teaspoon)"),
    ("10ml", "10ml"),
    ("15ml", "15ml"),
    ("2.5ml (½ teaspoon)", "2.5ml (½ teaspoon)"),
    ("20ml", "20ml"),
    ("other", "Other (specify)"),
]

# Common frequency options.
FREQUENCY_CHOICES = [
    ("", "Select frequency..."),
    ("Once daily (OD)", "Once daily (OD)"),
    ("Twice daily (BD)", "Twice daily (BD)"),
    ("Thrice daily (TDS)", "Thrice daily (TDS)"),
    ("Four times daily (QID)", "Four times daily (QID)"),
    ("Before breakfast", "Before breakfast"),
    ("After breakfast", "After breakfast"),
    ("Before meals", "Before meals"),
    ("After meals", "After meals"),
    ("At bedtime (HS)", "At bedtime (HS)"),
    ("Every 6 hours", "Every 6 hours"),
    ("Every 8 hours", "Every 8 hours"),
    ("As needed (SOS)", "As needed (SOS)"),
    ("other", "Other (specify)"),
]


class PrescriptionItemForm(FlaskForm):
    """Prescription item form."""

    class Meta:
        csrf = False

    medicine_id = SelectField("Medicine", coerce=int, validators=[DataRequired()])
    dosage = SelectField("Dosage", choices=DOSAGE_CHOICES, validators=[DataRequired()])
    dosage_other = StringField("Custom Dosage", validators=[Optional(), Length(max=100)])
    frequency = SelectField("Frequency", choices=FREQUENCY_CHOICES, validators=[DataRequired()])
    frequency_other = StringField("Custom Frequency", validators=[Optional(), Length(max=100)])
    duration_days = IntegerField("Duration (days)", default=1, validators=[DataRequired(), NumberRange(min=1)])
    quantity_to_deduct = IntegerField("Quantity", default=1, validators=[DataRequired(), NumberRange(min=1)])


class PrescriptionForm(FlaskForm):
    diagnosis = TextAreaField("Diagnosis", validators=[Optional(), Length(max=1000)])
    notes = TextAreaField("Additional Notes", validators=[Optional(), Length(max=1000)])
    items = FieldList(FormField(PrescriptionItemForm), min_entries=1)
    submit = SubmitField("Save Prescription")


class AvailabilityForm(FlaskForm):
    day_of_week = SelectField("Day of Week", choices=DAY_CHOICES, coerce=int, validators=[InputRequired()])
    start_time = TimeField("Start Time", validators=[DataRequired()])
    end_time = TimeField("End Time", validators=[DataRequired()])
    slot_duration_minutes = IntegerField(
        "Slot Duration (minutes)", default=15, validators=[DataRequired(), NumberRange(min=5, max=120)]
    )
    submit = SubmitField("Add Availability")


class ReportUploadForm(FlaskForm):
    patient_id = SelectField("Patient", coerce=int, validators=[DataRequired()])
    title = StringField("Report Title", validators=[DataRequired(), Length(max=150)])
    report_type = SelectField(
        "Report Type",
        choices=[("lab", "Lab Report"), ("scan", "Scan"), ("other", "Other")],
        validators=[DataRequired()],
    )
    file = FileField(
        "Report File",
        validators=[FileRequired(), FileAllowed(["pdf", "png", "jpg", "jpeg"], "PDF or image only!"), max_file_size_mb(10)],
    )
    submit = SubmitField("Upload Report")


class TestParameterForm(FlaskForm):
    """Generated lab report parameter."""

    class Meta:
        csrf = False

    parameter_name = StringField("Parameter", validators=[DataRequired(), Length(max=100)])
    result_value = StringField("Result", validators=[DataRequired(), Length(max=50)])
    reference_range = StringField("Reference Range", validators=[Optional(), Length(max=50)])
    unit_label = StringField("Unit", validators=[Optional(), Length(max=20)])


class LabResultForm(FlaskForm):
    patient_id = SelectField("Patient", coerce=int, validators=[DataRequired()])
    title = StringField("Test Name", validators=[DataRequired(), Length(max=150)], render_kw={"placeholder": "e.g. Complete Blood Count (CBC)"})
    interpretation = TextAreaField("Interpretation / Remarks", validators=[Optional(), Length(max=1000)])
    parameters = FieldList(FormField(TestParameterForm), min_entries=1)
    submit = SubmitField("Generate Report")


class DoctorProfileForm(FlaskForm):
    specialization = StringField("Specialization", validators=[Optional(), Length(max=120)])
    qualification = StringField("Qualification", validators=[Optional(), Length(max=150)])
    experience_years = IntegerField("Years of Experience", validators=[Optional(), NumberRange(min=0, max=70)])
    consultation_fee = IntegerField("Consultation Fee", validators=[Optional(), NumberRange(min=0)])
    bio = TextAreaField("Bio", validators=[Optional(), Length(max=1000)])
    submit = SubmitField("Update Profile")