"""
forms.py
--------
Flask-WTF form definitions with server-side validation.
"""

from flask_wtf import FlaskForm
from wtforms import (BooleanField, IntegerField, PasswordField, SelectField,
                     StringField, SubmitField, TextAreaField)
from wtforms.validators import (DataRequired, Email, EqualTo, Length,
                                NumberRange, Optional)


class RegisterForm(FlaskForm):
    name = StringField("Full name", validators=[DataRequired(), Length(min=2, max=120)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=160)])
    age = IntegerField("Age", validators=[Optional(), NumberRange(min=1, max=120)])
    gender = SelectField(
        "Gender",
        choices=[("", "Prefer not to say"), ("Female", "Female"),
                 ("Male", "Male"), ("Other", "Other")],
        validators=[Optional()],
    )
    password = PasswordField(
        "Password",
        validators=[DataRequired(), Length(min=8, message="Use at least 8 characters.")],
    )
    confirm = PasswordField(
        "Confirm password",
        validators=[DataRequired(), EqualTo("password", message="Passwords do not match.")],
    )
    submit = SubmitField("Create account")


class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    remember = BooleanField("Keep me signed in")
    submit = SubmitField("Sign in")


class SymptomForm(FlaskForm):
    symptoms = TextAreaField(
        "Describe your symptoms",
        validators=[DataRequired(message="Describe what you are feeling."),
                    Length(min=8, max=2000)],
    )
    age = IntegerField("Age", validators=[Optional(), NumberRange(min=1, max=120)])
    gender = SelectField(
        "Gender",
        choices=[("", "Prefer not to say"), ("Female", "Female"),
                 ("Male", "Male"), ("Other", "Other")],
        validators=[Optional()],
    )
    severity = SelectField(
        "How bad is it?",
        choices=[("Mild", "Mild"), ("Moderate", "Moderate"), ("Severe", "Severe")],
        default="Moderate",
    )
    duration = StringField("How long has it been going on?",
                           validators=[Optional(), Length(max=60)])
    submit = SubmitField("Analyse symptoms")
