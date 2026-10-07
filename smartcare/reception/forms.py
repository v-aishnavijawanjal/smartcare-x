from flask_wtf import FlaskForm
from wtforms import (
    DateField,
    DecimalField,
    FieldList,
    FormField,
    IntegerField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import DataRequired, Email, Length, NumberRange, Optional

from smartcare.utils.validators import not_in_past, valid_phone_number


class WalkInPatientForm(FlaskForm):
    full_name = StringField("Full Name", validators=[DataRequired(), Length(min=2, max=120)])
    email = StringField("Email", validators=[DataRequired(), Email()])
    phone = StringField("Phone Number", validators=[DataRequired(), valid_phone_number])
    gender = SelectField(
        "Gender",
        choices=[("", "Select..."), ("male", "Male"), ("female", "Female"), ("other", "Other")],
        validators=[Optional()],
    )

    department_id = SelectField("Department", coerce=int, validators=[DataRequired()])
    doctor_id = SelectField("Doctor", coerce=int, validators=[DataRequired()])
    appointment_date = DateField("Date", validators=[DataRequired(), not_in_past])
    time_slot = SelectField("Time Slot", validators=[DataRequired()])
    reason = TextAreaField("Reason for Visit", validators=[Optional(), Length(max=500)])

    submit = SubmitField("Register & Book")


class BillItemForm(FlaskForm):
    class Meta:
        csrf = False

    item_description = StringField("Description", validators=[DataRequired(), Length(max=255)])
    quantity = IntegerField("Qty", default=1, validators=[DataRequired(), NumberRange(min=1)])
    unit_price = DecimalField("Unit Price", places=2, validators=[DataRequired(), NumberRange(min=0)])


class BillForm(FlaskForm):
    items = FieldList(FormField(BillItemForm), min_entries=1)
    submit = SubmitField("Generate Bill")


class PaymentForm(FlaskForm):
    amount = DecimalField("Amount", places=2, validators=[DataRequired(), NumberRange(min=0.01)])
    method = SelectField("Method", choices=[("cash", "Cash"), ("card", "Card"), ("upi", "UPI")], validators=[DataRequired()])
    submit = SubmitField("Record Payment")