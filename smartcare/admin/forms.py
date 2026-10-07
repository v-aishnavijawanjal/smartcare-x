from flask_wtf import FlaskForm
from wtforms import DecimalField, IntegerField, PasswordField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Email, Length, NumberRange, Optional

from smartcare.utils.validators import strong_password, valid_phone_number


class DepartmentForm(FlaskForm):
    name = StringField("Department Name", validators=[DataRequired(), Length(max=100)])
    description = TextAreaField("Description", validators=[Optional(), Length(max=500)])
    icon = StringField("Bootstrap Icon Class", default="bi-hospital", validators=[Optional(), Length(max=50)])
    submit = SubmitField("Save Department")


class MedicineForm(FlaskForm):
    name = StringField("Medicine Name", validators=[DataRequired(), Length(max=150)])
    category = StringField("Category", validators=[Optional(), Length(max=80)])
    manufacturer = StringField("Manufacturer", validators=[Optional(), Length(max=120)])
    unit_price = DecimalField("Unit Price", places=2, validators=[DataRequired(), NumberRange(min=0)])
    initial_stock = IntegerField("Initial Stock", default=0, validators=[Optional(), NumberRange(min=0)])
    reorder_level = IntegerField("Reorder Level", default=10, validators=[Optional(), NumberRange(min=0)])
    submit = SubmitField("Save Medicine")


class RestockForm(FlaskForm):
    quantity = IntegerField("Quantity to Add", validators=[DataRequired(), NumberRange(min=1)])
    submit = SubmitField("Restock")


class CreateDoctorForm(FlaskForm):
    full_name = StringField("Full Name", validators=[DataRequired(), Length(max=120)])
    email = StringField("Email", validators=[DataRequired(), Email()])
    phone = StringField("Phone Number", validators=[Optional(), valid_phone_number])
    password = PasswordField("Temporary Password", validators=[DataRequired(), strong_password])
    department_id = SelectField("Department", coerce=int, validators=[DataRequired()])
    specialization = StringField("Specialization", validators=[Optional(), Length(max=120)])
    qualification = StringField("Qualification", validators=[Optional(), Length(max=150)])
    experience_years = IntegerField("Years of Experience", default=0, validators=[Optional(), NumberRange(min=0, max=70)])
    consultation_fee = DecimalField("Consultation Fee", places=2, default=0, validators=[Optional(), NumberRange(min=0)])
    submit = SubmitField("Create Doctor Account")


class CreateReceptionistForm(FlaskForm):
    full_name = StringField("Full Name", validators=[DataRequired(), Length(max=120)])
    email = StringField("Email", validators=[DataRequired(), Email()])
    phone = StringField("Phone Number", validators=[Optional(), valid_phone_number])
    password = PasswordField("Temporary Password", validators=[DataRequired(), strong_password])
    shift = SelectField(
        "Shift", choices=[("Morning", "Morning"), ("Evening", "Evening"), ("Night", "Night")], validators=[DataRequired()]
    )
    desk_number = StringField("Desk Number", validators=[Optional(), Length(max=10)])
    submit = SubmitField("Create Receptionist Account")
