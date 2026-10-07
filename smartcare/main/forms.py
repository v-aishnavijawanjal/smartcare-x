from flask_wtf import FlaskForm
from wtforms import IntegerField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Email, Length, NumberRange, Optional


SUBJECT_CHOICES = [
    ("", "Select a subject..."),
    ("General Inquiry", "General Inquiry"),
    ("Partnership", "Partnership"),
    ("Complaint / Feedback", "Complaint / Feedback"),
    ("Other", "Other (please specify)"),
]


class ContactForm(FlaskForm):
    name = StringField("Full Name", validators=[DataRequired(), Length(max=120)])
    email = StringField("Email", validators=[DataRequired(), Email()])
    subject = SelectField("Subject", choices=SUBJECT_CHOICES, validators=[DataRequired()])
    subject_other = StringField("Please specify", validators=[Optional(), Length(max=200)])
    message = TextAreaField("Message", validators=[DataRequired(), Length(max=2000)])
    submit = SubmitField("Send Message")


class ReviewForm(FlaskForm):
    rating = IntegerField("Rating (1-5)", validators=[DataRequired(), NumberRange(min=1, max=5)])
    comment = TextAreaField("Your Experience", validators=[Length(max=1000)])
    submit = SubmitField("Submit Review")
